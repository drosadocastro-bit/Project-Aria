#!/usr/bin/env python3
"""
Setup validation reference set
Initializes reference set JSON with template tracks
Run once before deployment to set up ground-truth validation data
"""

import logging
from pathlib import Path
from core.model_validator import ReferenceSet
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_reference_set():
    """Initialize reference validation set"""
    ref_set = ReferenceSet(config.VALIDATION_REFERENCE_FILE)
    
    # If already has tracks, skip
    if ref_set.size() > 0:
        logger.info(f"Reference set already has {ref_set.size()} tracks")
        return
    
    # Template baseline tracks
    baseline_tracks = [
        ("metal_baseline_001.wav", "metal", 0.98, "Classic thrash metal - consistent baseline"),
        ("synthwave_baseline_001.wav", "synthwave", 0.97, "Neon synth-wave"),
        ("phonk_baseline_001.wav", "phonk", 0.96, "Lo-fi phonk beats"),
        ("ambient_baseline_001.wav", "ambient", 0.95, "Chill ambient"),
        ("rock_baseline_001.wav", "rock", 0.97, "Classic rock"),
        ("hiphop_baseline_001.wav", "hiphop", 0.96, "Hip-hop baseline"),
        ("jazz_baseline_001.wav", "jazz", 0.94, "Jazz standards"),
        ("classical_baseline_001.wav", "classical", 0.95, "Orchestral"),
        ("pop_baseline_001.wav", "pop", 0.96, "Modern pop"),
        ("reggae_baseline_001.wav", "reggae", 0.95, "Reggae rhythm"),
    ]
    
    logger.info("Adding baseline reference tracks...")
    for filename, genre, conf, reason in baseline_tracks:
        ref_set.add_track(filename, genre, conf, reason)
    
    ref_set.metadata = {
        "created": "2026-01-18",
        "version": "1.0",
        "purpose": "Ground-truth validation for CNN drift detection",
        "locked": True,
        "description": "10 baseline tracks - immutable after first deployment"
    }
    
    ref_set.save()
    logger.info(f"✓ Reference set initialized with {ref_set.size()} tracks")
    logger.info(f"  Location: {config.VALIDATION_REFERENCE_FILE}")
    logger.info("  Next: Place actual audio files in the locations specified above")


if __name__ == "__main__":
    setup_reference_set()
