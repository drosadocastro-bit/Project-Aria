#!/usr/bin/env python3
"""
Validation Monitoring Dashboard
Monitor model drift and validation metrics in real-time
Run periodically (daily/weekly) to track CNN health
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import config
from core.model_validator import ModelValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_metrics(metrics):
    """Pretty-print validation metrics"""
    print(f"  Timestamp:     {metrics['timestamp']}")
    print(f"  Accuracy:      {metrics['accuracy']}%")
    print(f"  Sample Size:   {metrics['total_tracks']} tracks")
    print(f"  Model:         {metrics['model_path']}")
    print(f"  Drift?:        {'🚨 YES' if metrics['drift_detected'] else '✓ NO'}")
    print(f"  Notes:         {metrics['notes']}")


def dashboard():
    """Display validation dashboard"""
    validator_config = {
        'validation_reference_file': str(config.VALIDATION_REFERENCE_FILE),
        'validation_models_dir': str(config.VALIDATION_MODELS_DIR),
        'drift_threshold': config.VALIDATION_DRIFT_THRESHOLD,
        'min_reference_accuracy': config.VALIDATION_MIN_ACCURACY,
        'validation_log_file': str(config.VALIDATION_LOG_FILE),
    }
    
    validator = ModelValidator(validator_config)
    
    # === Current Status ===
    print_header("VALIDATION STATUS")
    report = validator.get_validation_report()
    
    if report.get("status") == "no_data":
        print("  No validation history yet. Run: python -m core.genre_cnn --train")
        return
    
    print(f"  Total Validations:  {report['total_validations']}")
    print(f"  Baseline Accuracy:  {report['baseline_accuracy']}%")
    print(f"  Latest Accuracy:    {report['latest_accuracy']}%")
    print(f"  7-Day Average:      {report['average_recent']}%")
    print(f"  Min Threshold:      {report['min_threshold']}%")
    print(f"  Drift Alerts:       {report['drift_alerts']} / {report['total_validations']}")
    print(f"  Last Check:         {report['last_validation']}")
    
    # === Latest Validation ===
    if validator.validation_history:
        print_header("LATEST VALIDATION")
        latest = validator.validation_history[-1]
        print_metrics(latest.to_dict())
    
    # === Recent Trend (7 days) ===
    recent = validator.get_recent_accuracy(days=7)
    if recent:
        print_header(f"RECENT TREND (Last 7 Days - {len(recent)} checks)")
        for i, m in enumerate(recent[-5:], 1):  # Show last 5
            print(f"\n  [{i}] {m.timestamp[:10]}")
            print(f"      Accuracy: {m.accuracy}%  |  Status: {'🚨' if m.drift_detected else '✓'}")
    
    # === Recommendations ===
    print_header("RECOMMENDATIONS")
    
    if report['drift_alerts'] > 0:
        print("  ⚠️  MODEL DRIFT DETECTED")
        print("      Consider retraining on recent data")
        good_model = validator.get_good_model()
        if good_model:
            print(f"      Last good model: {good_model}")
    
    if report['latest_accuracy'] < report['min_threshold']:
        print("  🚨 CRITICAL: Accuracy below minimum threshold")
        print("     Take action immediately")
    elif report['latest_accuracy'] < (report['min_threshold'] + 5):
        print("  ⚠️  WARNING: Accuracy trending down")
        print("     Monitor closely, prepare retraining")
    else:
        print("  ✓ Model is healthy")
        print("    Continue monitoring periodically")
    
    # === Next Steps ===
    print_header("NEXT STEPS")
    print("  Weekly:  python scripts/validation_dashboard.py")
    print("  Monthly: python -m core.genre_cnn --train (retrain if needed)")
    print("  OnDrift: git push latest model checkpoint")
    print("           Update MODELS_DIR/genre_cnn_backup.pt")


if __name__ == "__main__":
    dashboard()
