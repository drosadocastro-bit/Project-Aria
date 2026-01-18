"""
Model Validator - Drift detection, reference set validation, and rollback management
Monitors CNN accuracy on held-out reference dataset to detect model degradation
"""

import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import numpy as np
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ValidationMetrics:
    """Store validation results with timestamp"""
    timestamp: str
    accuracy: float
    total_tracks: int
    drift_detected: bool
    model_path: str
    reference_set_size: int
    notes: str = ""

    def to_dict(self):
        return asdict(self)


class ReferenceSet:
    """Manage ground-truth validation dataset"""
    
    def __init__(self, reference_file: Path):
        """
        Load reference validation set from JSON
        
        Expected format:
        {
            "tracks": [
                {
                    "filename": "metal_track_001.wav",
                    "genre": "metal",
                    "confidence": 0.95,
                    "reason": "Classic thrash metal - consistent baseline"
                },
                ...
            ],
            "metadata": {
                "created": "2026-01-18",
                "purpose": "Model drift detection",
                "locked": true
            }
        }
        """
        self.reference_file = reference_file
        self.tracks: List[Dict] = []
        self.metadata: Dict = {}
        
        if reference_file.exists():
            self.load()
        else:
            logger.warning(f"Reference set not found at {reference_file}")
    
    def load(self):
        """Load reference set from JSON"""
        try:
            with open(self.reference_file, 'r') as f:
                data = json.load(f)
            self.tracks = data.get('tracks', [])
            self.metadata = data.get('metadata', {})
            logger.info(f"Loaded {len(self.tracks)} reference tracks")
        except Exception as e:
            logger.error(f"Failed to load reference set: {e}")
    
    def save(self):
        """Persist reference set"""
        try:
            data = {
                'tracks': self.tracks,
                'metadata': self.metadata
            }
            self.reference_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.reference_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved reference set with {len(self.tracks)} tracks")
        except Exception as e:
            logger.error(f"Failed to save reference set: {e}")
    
    def add_track(self, filename: str, genre: str, confidence: float = 0.95, reason: str = ""):
        """Add reference track (before deployment)"""
        track = {
            "filename": filename,
            "genre": genre,
            "confidence": confidence,
            "reason": reason
        }
        self.tracks.append(track)
        logger.info(f"Added reference track: {filename} ({genre})")
    
    def get_ground_truth(self) -> Dict[str, str]:
        """Return {filename: genre} mapping for validation"""
        return {t['filename']: t['genre'] for t in self.tracks}
    
    def size(self) -> int:
        return len(self.tracks)


class ModelValidator:
    """Validate CNN on reference set, detect drift, manage rollbacks"""
    
    def __init__(self, config):
        """
        Args:
            config: Configuration dict with validation settings
                - validation_reference_file: Path to reference set JSON
                - validation_models_dir: Directory for model checkpoints
                - drift_threshold: Accuracy drop % to trigger alert (default 5.0)
                - min_reference_accuracy: Minimum acceptable accuracy (default 75.0)
        """
        self.config = config
        
        # Paths
        self.models_dir = Path(config.get('validation_models_dir', 'models'))
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.reference_file = Path(config.get('validation_reference_file', 
                                              'config/reference_validation_set.json'))
        self.validation_log = Path(config.get('validation_log_file',
                                             'state/validation_history.json'))
        self.validation_log.parent.mkdir(parents=True, exist_ok=True)
        
        # Thresholds
        self.drift_threshold = config.get('drift_threshold', 5.0)  # % accuracy drop
        self.min_reference_accuracy = config.get('min_reference_accuracy', 75.0)
        
        # Load reference set
        self.reference_set = ReferenceSet(self.reference_file)
        
        # Validation history
        self.validation_history: List[ValidationMetrics] = []
        self._load_history()
    
    def _load_history(self):
        """Load validation history from disk"""
        if self.validation_log.exists():
            try:
                with open(self.validation_log, 'r') as f:
                    history = json.load(f)
                self.validation_history = [
                    ValidationMetrics(**h) for h in history
                ]
                logger.info(f"Loaded {len(self.validation_history)} validation records")
            except Exception as e:
                logger.error(f"Failed to load validation history: {e}")
    
    def _save_history(self):
        """Persist validation history"""
        try:
            with open(self.validation_log, 'w') as f:
                json.dump([m.to_dict() for m in self.validation_history], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save validation history: {e}")
    
    def validate(self, model, data_loader, model_path: str) -> ValidationMetrics:
        """
        Validate model on reference set
        
        Args:
            model: CNN model with inference capability
            data_loader: DataLoader for reference tracks (must be prepared)
            model_path: Path to current model file
        
        Returns:
            ValidationMetrics with accuracy and drift status
        """
        if not self.reference_set.size():
            logger.warning("No reference set available - skipping validation")
            return None
        
        try:
            model.eval()
            correct = 0
            total = 0
            
            ground_truth = self.reference_set.get_ground_truth()
            
            with __import__('torch').no_grad():
                for batch_idx, (inputs, filenames) in enumerate(data_loader):
                    outputs = model(inputs)
                    _, predicted = outputs.max(1)
                    
                    # Map predictions to genres
                    for i, filename in enumerate(filenames):
                        if filename in ground_truth:
                            pred_genre = model.class_names[predicted[i]]
                            true_genre = ground_truth[filename]
                            if pred_genre == true_genre:
                                correct += 1
                            total += 1
            
            accuracy = (correct / total * 100) if total > 0 else 0.0
            
            # Check for drift
            drift_detected = self._detect_drift(accuracy)
            
            # Create metrics record
            metrics = ValidationMetrics(
                timestamp=datetime.now().isoformat(),
                accuracy=round(accuracy, 2),
                total_tracks=total,
                drift_detected=drift_detected,
                model_path=str(model_path),
                reference_set_size=self.reference_set.size(),
                notes=f"Correct: {correct}/{total}"
            )
            
            self.validation_history.append(metrics)
            self._save_history()
            
            # Log results
            status = "🚨 DRIFT DETECTED" if drift_detected else "✓ OK"
            logger.warning(f"{status} - Validation accuracy: {accuracy:.2f}% ({correct}/{total})")
            
            if drift_detected:
                self._trigger_drift_alert(metrics)
            
            return metrics
        
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return None
    
    def _detect_drift(self, current_accuracy: float) -> bool:
        """Check if accuracy dropped below threshold"""
        if len(self.validation_history) < 2:
            return False
        
        # Get previous accuracy (most recent before current)
        prev_metrics = self.validation_history[-1]
        prev_accuracy = prev_metrics.accuracy
        
        accuracy_drop = prev_accuracy - current_accuracy
        
        logger.info(f"Accuracy trend: {prev_accuracy:.2f}% → {current_accuracy:.2f}% "
                   f"(Δ {accuracy_drop:+.2f}%)")
        
        # Drift if:
        # 1. Below minimum threshold, OR
        # 2. Dropped more than drift_threshold since last check
        is_drifted = (current_accuracy < self.min_reference_accuracy or 
                     accuracy_drop > self.drift_threshold)
        
        return is_drifted
    
    def _trigger_drift_alert(self, metrics: ValidationMetrics):
        """Handle drift detection (alert, logging, etc.)"""
        logger.critical(
            f"⚠️ MODEL DRIFT ALERT\n"
            f"   Accuracy: {metrics.accuracy:.2f}%\n"
            f"   Threshold: {self.min_reference_accuracy:.2f}%\n"
            f"   Model: {metrics.model_path}\n"
            f"   Action: Consider rollback or retraining"
        )
    
    def get_baseline_accuracy(self) -> Optional[float]:
        """Get accuracy from first deployment (baseline for comparison)"""
        if self.validation_history:
            return self.validation_history[0].accuracy
        return None
    
    def get_recent_accuracy(self, days: int = 7) -> List[ValidationMetrics]:
        """Get validation records from last N days"""
        cutoff = datetime.fromisoformat(
            (datetime.now().fromtimestamp(
                datetime.now().timestamp() - days * 86400
            )).isoformat()
        )
        return [m for m in self.validation_history 
               if datetime.fromisoformat(m.timestamp) >= cutoff]
    
    # ===== CHECKPOINT MANAGEMENT =====
    
    def backup_model(self, current_model_path: Path, label: str = "auto"):
        """Create versioned backup of current model"""
        try:
            backups_dir = self.models_dir / "backups"
            backups_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backups_dir / f"genre_cnn_{label}_{timestamp}.pt"
            
            shutil.copy(current_model_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None
    
    def get_good_model(self) -> Optional[Path]:
        """Get last model with acceptable validation accuracy"""
        for metrics in reversed(self.validation_history):
            if metrics.accuracy >= self.min_reference_accuracy:
                model_path = Path(metrics.model_path)
                if model_path.exists():
                    logger.info(f"Found good model: {model_path} ({metrics.accuracy:.2f}% accuracy)")
                    return model_path
        return None
    
    def rollback_model(self, current_model_path: Path) -> bool:
        """
        Rollback to last good model
        
        Returns:
            True if rollback successful, False otherwise
        """
        good_model = self.get_good_model()
        
        if not good_model:
            logger.error("No good model found for rollback")
            return False
        
        try:
            # Backup current bad model
            self.backup_model(current_model_path, label="rollback_bad")
            
            # Restore good model
            shutil.copy(good_model, current_model_path)
            logger.warning(f"⚠️ ROLLED BACK to {good_model} ({good_model.stat().st_mtime})")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def get_validation_report(self) -> Dict:
        """Generate comprehensive validation report"""
        if not self.validation_history:
            return {"status": "no_data"}
        
        recent = self.get_recent_accuracy(days=7)
        
        return {
            "total_validations": len(self.validation_history),
            "baseline_accuracy": round(self.get_baseline_accuracy(), 2),
            "latest_accuracy": round(self.validation_history[-1].accuracy, 2),
            "recent_7_days": len(recent),
            "drift_alerts": sum(1 for m in self.validation_history if m.drift_detected),
            "average_recent": round(
                np.mean([m.accuracy for m in recent]) if recent else 0, 2
            ),
            "min_threshold": self.min_reference_accuracy,
            "last_validation": self.validation_history[-1].timestamp,
        }


if __name__ == "__main__":
    # Example: Create reference set
    logging.basicConfig(level=logging.INFO)
    
    ref_set = ReferenceSet(Path("config/reference_validation_set.json"))
    
    # Add some baseline tracks
    ref_set.add_track("metal_001.wav", "metal", 0.98, "Classic thrash - immutable baseline")
    ref_set.add_track("synthwave_001.wav", "synthwave", 0.97, "Neon Drive vibes")
    ref_set.add_track("phonk_001.wav", "phonk", 0.96, "Lo-fi beats")
    ref_set.add_track("ambient_001.wav", "ambient", 0.95, "Chill evening")
    
    ref_set.save()
    print(f"Created reference set with {ref_set.size()} tracks")
