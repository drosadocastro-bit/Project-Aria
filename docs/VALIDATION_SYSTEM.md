# Model Validation & Drift Detection System

## Overview

Complete model validation framework for CNN genre classifier to detect performance degradation and enable rollback.

**Key Components:**
- `core/model_validator.py` - Drift detection, reference set management, rollback
- `config.py` - Validation thresholds and settings
- `config/reference_validation_set.json` - Ground-truth validation dataset
- `scripts/setup_validation.py` - Initialize reference set
- `scripts/validation_dashboard.py` - Monitor drift trends

---

## Architecture

### 1. Reference Validation Set
**Purpose:** Immutable baseline tracks for accuracy checking

```
config/reference_validation_set.json
├── tracks: [
│   ├── filename: "metal_baseline_001.wav"
│   ├── genre: "metal"
│   ├── confidence: 0.98
│   └── reason: "Classic thrash metal - immutable baseline"
│   └── ...10 total tracks across genres
└── metadata:
    ├── locked: true
    ├── created: "2026-01-18"
    └── purpose: "Drift detection"
```

**Properties:**
- **10 baseline tracks** (1 per major genre)
- **Locked after deployment** - never add new tracks
- **Stores ground-truth labels** (human-verified)
- **High confidence scores** (0.94-0.98) - clear genre signals

### 2. Validation Metrics & History

**Stored in:** `state/validation_history.json`

```json
[
  {
    "timestamp": "2026-01-18T15:30:00",
    "accuracy": 87.5,
    "total_tracks": 10,
    "drift_detected": false,
    "model_path": "models/genre_cnn.pt",
    "reference_set_size": 10,
    "notes": "Correct: 7/10"
  },
  ...
]
```

**Tracked:**
- Accuracy on reference set (%)
- Timestamp
- Drift detection flag
- Model path (for rollback)

### 3. Drift Detection Rules

**Alert triggered if:**

```
1. Accuracy < min_threshold (75%)  [below minimum acceptable]
   OR
2. Accuracy drops > drift_threshold % (5%)  [sharp drop]
   OR
3. Rolling average trends down
```

**Config:**
```python
VALIDATION_DRIFT_THRESHOLD = 5.0      # % drop triggers alert
VALIDATION_MIN_ACCURACY = 75.0        # Below this = bad
VALIDATION_CHECK_INTERVAL = 1000      # Validate every 1000 inferences
```

---

## Usage

### Setup (Before Deployment)

```bash
# 1. Initialize reference set
python scripts/setup_validation.py
# Creates: config/reference_validation_set.json (10 baseline tracks)

# 2. Add actual audio files
# Copy 10 representative tracks to somewhere accessible:
# - music_dataset/validation/ or
# - state/reference_tracks/

# 3. Test validation
python -c "from core.model_validator import ModelValidator; import config; v = ModelValidator({...}); print(f'Loaded {v.reference_set.size()} tracks')"
```

### During Operation

**Automatic (periodic):**
```python
# In auto_eq.py or aria.py
classifier = CNNGenreClassifier()
# Every 1000 inferences, automatically validates on reference set
result = classifier.predict_audio(track_path)  # triggers check
```

**Manual (on-demand):**
```python
from core.genre_cnn import CNNGenreClassifier

clf = CNNGenreClassifier()
metrics = clf.validate_on_reference_set()
# Returns: {"accuracy": 87.5, "total_tracks": 10, ...}

# Get full report
report = clf.get_validation_report()
print(report)
# {
#   "baseline_accuracy": 85.0,
#   "latest_accuracy": 87.5,
#   "drift_alerts": 0,
#   "average_recent": 86.2
# }
```

### Monitoring (Weekly)

```bash
python scripts/validation_dashboard.py
```

**Output:**
```
============================================================
  VALIDATION STATUS
============================================================
  Total Validations:  52
  Baseline Accuracy:  85.0%
  Latest Accuracy:    87.5%
  7-Day Average:      86.8%
  Drift Alerts:       0 / 52
  Last Check:         2026-01-18T15:30:00

============================================================
  LATEST VALIDATION
============================================================
  Accuracy:      87.5%
  Sample Size:   10 tracks
  Drift?:        ✓ NO

============================================================
  RECOMMENDATIONS
============================================================
  ✓ Model is healthy
    Continue monitoring periodically
```

---

## Retraining Strategy

### Monthly Retraining Cycle

**Week 1-3:** Monitor on reference set
```python
# Weekly check
python scripts/validation_dashboard.py
```

**Week 4:** Conditional retrain
```bash
# If drift detected OR accuracy < 75%
python -m core.genre_cnn --train \
  --epochs 8 \
  --profile-bias \
  --augment

# Validate new model
python scripts/validation_dashboard.py
```

**Retraining Rules:**
1. **Never** lock new listeners into old model
2. **Always** keep last 3 model checkpoints:
   - `genre_cnn_current.pt` (active)
   - `genre_cnn_backup.pt` (previous good)
   - `genre_cnn_previous.pt` (fallback)

3. **After retrain:**
   ```python
   # Backup old model
   validator.backup_model(current_path, label="pre_retrain_2026_01")
   
   # Test new model on reference set
   new_metrics = new_classifier.validate_on_reference_set()
   
   # If accuracy >= 75%, deploy
   if new_metrics['accuracy'] >= 75:
       shutil.copy(new_model, production_path)
       logger.info("✓ Model updated")
   else:
       logger.error("❌ Retraining failed, keeping old model")
   ```

---

## Rollback on Crisis

**If production model crashes:**

```python
from core.model_validator import ModelValidator
import config

validator = ModelValidator({...})

# Find last good model
good_model = validator.get_good_model()
# Returns: Path to last model with accuracy >= 75%

# Automatic rollback
validator.rollback_model(current_model_path)
# Backs up bad model, restores good one
```

**Manual rollback:**
```bash
cp models/backups/genre_cnn_backup_*.pt models/genre_cnn.pt
python -c "from core.genre_cnn import CNNGenreClassifier; clf = CNNGenreClassifier(); print(clf.get_validation_report())"
```

---

## Timeline (Fall/Winter Deployment)

| Phase | Duration | Action |
|-------|----------|--------|
| **Pre-Deploy** | Jan-May | Train baseline CNN, create reference set |
| **Windows Test** | May-Aug | Run on local machine, collect active learning data |
| **Validation Setup** | Aug-Sep | Run monthly validation cycle, refine thresholds |
| **Jetson Port** | Sep-Oct | Deploy inference-only, keep training on Windows |
| **Production** | Nov+ | Monthly retraining, weekly validation checks |

---

## Monitoring Checklist

- [ ] Reference set created with 10 baseline tracks
- [ ] First validation run: baseline accuracy established
- [ ] Monthly retraining scheduled in calendar
- [ ] Validation alerts configured (email/log)
- [ ] Model backups configured (keep 3 versions)
- [ ] Rollback tested (at least once)
- [ ] Team trained on validation workflow

---

## Config Reference

```python
# config.py

# Reference set file
VALIDATION_REFERENCE_FILE = PROJECT_ROOT / "config" / "reference_validation_set.json"

# Accuracy drop threshold (%) for drift alert
VALIDATION_DRIFT_THRESHOLD = 5.0

# Minimum acceptable accuracy (%)
VALIDATION_MIN_ACCURACY = 75.0

# Validate every N inferences
VALIDATION_CHECK_INTERVAL = 1000

# Auto-rollback on drift (set True only after first month)
VALIDATION_AUTO_ROLLBACK = False
```

---

## Troubleshooting

**Q: "No reference set available for validation"**
```bash
python scripts/setup_validation.py
```

**Q: How to manually validate right now?**
```bash
python -c "
from core.genre_cnn import CNNGenreClassifier
clf = CNNGenreClassifier()
metrics = clf.validate_on_reference_set()
print(f'Accuracy: {metrics[\"accuracy\"]}%')
"
```

**Q: Accuracy is 63% - what do I do?**
1. Check if reference tracks are corrupted
2. Retrain with more data
3. Consider lowering `VALIDATION_MIN_ACCURACY` if baseline is legitimately lower
4. Check OBD data interference (temp/RPM affecting context)

**Q: Model drifting - should I auto-rollback?**
- **No** for first 2 months (learning phase)
- **Yes** after 3 months in production with proven stability
- Always manual review before auto-rollback enabled

---

## Future Enhancements

- [ ] Slack/email alerts on drift
- [ ] Per-genre accuracy tracking (some genres harder?)
- [ ] A/B testing framework (old vs new model)
- [ ] Seasonal adjustment (winter = different music patterns)
- [ ] Hardware monitoring (Jetson GPU memory, latency)
