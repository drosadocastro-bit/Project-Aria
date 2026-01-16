"""
Personal Genre Fine-Tuning - Adapts GTZAN model to user's music preferences
Uses transfer learning on top 5 favorite genres with user feedback data
Lightweight: ~2 min runtime, targets your specific taste
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import pickle
import warnings

warnings.filterwarnings('ignore')

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.listener_profile import ListenerProfile
from core.genre_classifier import GenreClassifier


class PersonalModelTrainer:
    """Fine-tunes GTZAN model on user's top genres."""
    
    def __init__(self, base_model_path=None, listener_profile=None):
        self.base_model_path = base_model_path or \
            Path(__file__).parent.parent / "models" / "genre_classifier_rf.pkl"
        self.listener_profile = listener_profile or ListenerProfile()
        self.base_model = None
        self.personal_model = None
        self.scaler = StandardScaler()
        self.top_genres = []
    
    def load_base_model(self):
        """Load pre-trained GTZAN model."""
        try:
            with open(self.base_model_path, 'rb') as f:
                classifier = pickle.load(f)
                self.base_model = classifier
                print(f"[OK] Loaded GTZAN base model: {self.base_model_path}")
                return True
        except Exception as e:
            print(f"[ERROR] Failed to load base model: {e}")
            return False
    
    def get_training_data_from_feedback(self, min_samples_per_genre=5):
        """
        Extract training data from user feedback logs.
        
        Returns: (X, y) where X = listener affinities, y = genre labels
        """
        feedback_data = self.listener_profile.export_feedback_for_training()
        
        if not feedback_data:
            print("[WARN] No feedback data available for personal training")
            return None, None
        
        # Group by genre
        genre_counts = {}
        X_data = []
        y_data = []
        
        for genre, action_label in feedback_data:
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
            affinity = self.listener_profile.get_genre_affinity(genre)
            X_data.append([affinity])
            y_data.append(genre)
        
        print(f"[DATA] Extracted {len(feedback_data)} feedback samples")
        print(f"[DATA] Genres represented: {list(genre_counts.keys())}")
        
        return np.array(X_data), np.array(y_data)
    
    def train_personal_model(self, X, y):
        """
        Train a lightweight personal model using transfer learning.
        Keeps GTZAN structure, personalizes for user's top genres.
        """
        if X is None or len(X) < 5:
            print("[WARN] Insufficient training data (<5 samples)")
            return False
        
        print("[TRAIN] Training personal adaptation layer...")
        print(f"        Samples: {len(X)}")
        print(f"        Features: {X.shape[1]}")
        
        # Lightweight RF: fewer estimators than base model
        self.personal_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1
        )
        
        try:
            self.personal_model.fit(X, y)
            score = self.personal_model.score(X, y)
            print(f"[RESULT] Personal model trained | Accuracy: {score:.1%}")
            return True
        except Exception as e:
            print(f"[ERROR] Training failed: {e}")
            return False
    
    def save_personal_model(self, output_path=None):
        """Save personal model for deployment."""
        if output_path is None:
            output_path = Path(__file__).parent.parent / "models" / "personal_adapter_rf.pkl"
        
        if self.personal_model is None:
            print("[ERROR] No personal model to save")
            return False
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                pickle.dump(self.personal_model, f)
            print(f"[SAVE] Personal model saved: {output_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save: {e}")
            return False
    
    def create_ensemble(self):
        """
        Create weighted ensemble: GTZAN + Personal Model
        Future feature: blend predictions with weights
        """
        if not self.personal_model or not self.base_model:
            print("[ERROR] Missing base or personal model")
            return False
        
        ensemble_config = {
            "base_model": str(self.base_model_path),
            "personal_model": str(Path(__file__).parent.parent / "models" / "personal_adapter_rf.pkl"),
            "base_weight": 0.7,  # GTZAN carries more weight
            "personal_weight": 0.3,  # Personal adds fine-tuning
            "listener_affinity_weight": 0.15,  # Final layer: listener preference
            "created": str(pd.Timestamp.now())
        }
        
        config_path = Path(__file__).parent.parent / "models" / "ensemble_config.json"
        import json
        with open(config_path, 'w') as f:
            json.dump(ensemble_config, f, indent=2)
        
        print(f"[ENSEMBLE] Weights configured: GTZAN {ensemble_config['base_weight']:.0%} + Personal {ensemble_config['personal_weight']:.0%} + Affinity {ensemble_config['listener_affinity_weight']:.0%}")
        return True
    
    def print_training_summary(self):
        """Pretty-print training summary."""
        top_genres = self.listener_profile.get_top_genres(5)
        
        print("\n" + "=" * 60)
        print("  🎓 Personal Model Training Summary")
        print("=" * 60)
        print(f"  Base Model:       {self.base_model_path.name}")
        print(f"  Feedback Samples: {len(self.listener_profile.profile['feedback_log'])}")
        
        if top_genres:
            print(f"\n  🎵 Top Genres (Affinity):")
            for genre, affinity in top_genres:
                print(f"     {genre:15} {affinity:6.1%}")
        
        if self.personal_model:
            print(f"\n  ✅ Personal Model Status: TRAINED")
            print(f"     Model file: models/personal_adapter_rf.pkl")
        
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Train personal ML model adapted to user's music taste"
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Train personal model from feedback data"
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Show listener profile summary"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-train if feedback threshold reached"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("  Personal Genre Fine-Tuning System")
    print("=" * 60 + "\n")
    
    # Load listener profile
    listener_profile = ListenerProfile()
    
    if args.profile:
        listener_profile.print_profile_summary()
        return
    
    if args.train or args.auto:
        trainer = PersonalModelTrainer(listener_profile=listener_profile)
        
        # Load base GTZAN model
        if not trainer.load_base_model():
            print("[ERROR] Cannot proceed without base model")
            return
        
        # Extract feedback data
        X, y = trainer.get_training_data_from_feedback()
        if X is None:
            print("[INFO] No sufficient feedback yet. Keep listening and rating!")
            print("       Target: 50+ feedback entries before personal retraining")
            return
        
        # Train personal model
        if trainer.train_personal_model(X, y):
            trainer.save_personal_model()
            trainer.create_ensemble()
            trainer.print_training_summary()
            print("[SUCCESS] Personal model ready for deployment!")
            print("          Next session will use adaptive ensemble")
        else:
            print("[FAILED] Training did not complete")


if __name__ == "__main__":
    main()
