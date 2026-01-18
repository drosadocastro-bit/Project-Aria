"""
Listener Profile - Tracks user music preferences and listening patterns
Learns from Spotify playback: genres loved/hated, EQ preferences, skip patterns
"""

import json
from pathlib import Path
from typing import Optional
from collections import defaultdict
from datetime import datetime
import statistics


class ListenerProfile:
    """Persistent user preference learning system."""
    
    def __init__(self, profile_path: Optional[Path] = None):
        if profile_path is None:
            profile_path = Path(__file__).parent.parent / "state" / "listener_profile.json"
        
        self.profile_path = profile_path
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.profile = self._load_or_init()
        self._sanitize_profile()
    
    def _load_or_init(self):
        """Load existing profile or initialize new one."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load profile: {e}, creating new")
        
        # Initialize new profile
        return {
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "listening_stats": {
                "total_tracks": 0,
                "total_skips": 0,
                "total_replays": 0,
                "sessions": 0
            },
            "genre_affinities": {},  # {genre: affinity_score 0-1}
            "preset_preferences": {},  # {preset: [confidence_history]}
            "skip_patterns": {},  # {genre: skip_count}
            "replay_patterns": {},  # {genre: replay_count}
            "feedback_log": []  # [{track_id, predicted_genre, actual_genre, action, timestamp}]
        }
    
    def save(self):
        """Persist profile to disk."""
        try:
            self._sanitize_profile()
            self.profile["last_updated"] = datetime.now().isoformat()
            with open(self.profile_path, 'w', encoding='utf-8') as f:
                json.dump(self.profile, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save profile: {e}")

    def _sanitize_profile(self):
        """Clean up invalid keys and cap metadata influence."""
        # Remove empty preset keys
        preset_prefs = self.profile.get("preset_preferences", {})
        if "" in preset_prefs:
            preset_prefs.pop("", None)
        if None in preset_prefs:
            preset_prefs.pop(None, None)
        self.profile["preset_preferences"] = preset_prefs

        # Cap metadata affinity to avoid dominating preferences
        genre_affinities = self.profile.get("genre_affinities", {})
        for key in list(genre_affinities.keys()):
            if isinstance(key, str) and key.startswith("metadata"):
                genre_affinities[key] = min(0.6, float(genre_affinities.get(key, 0.5)))
        self.profile["genre_affinities"] = genre_affinities
    
    def log_track_prediction(self, track_id, track_name, artist, predicted_genre, 
                            predicted_preset, confidence, dwell_time_sec=0):
        """
        Record a track prediction.
        
        Args:
            track_id: Spotify track ID
            predicted_genre: GTZAN genre
            predicted_preset: EQ preset applied
            confidence: GTZAN confidence
            dwell_time_sec: How long user listened (for skip detection)
        """
        # Default dwell threshold: < 10sec = likely skip
        is_skip = dwell_time_sec < 10 if dwell_time_sec > 0 else False
        
        # Update listening stats
        self.profile["listening_stats"]["total_tracks"] += 1
        if is_skip:
            self.profile["listening_stats"]["total_skips"] += 1
            # Track genre skips
            self.profile["skip_patterns"][predicted_genre] = \
                self.profile["skip_patterns"].get(predicted_genre, 0) + 1
        
        is_metadata = isinstance(predicted_genre, str) and predicted_genre.startswith("metadata")

        # Update genre affinity (naive: penalize skips, reward plays)
        current_affinity = self.profile["genre_affinities"].get(predicted_genre, 0.5)
        if is_skip:
            delta = 0.02 if is_metadata else 0.05
            new_affinity = max(0.0, current_affinity - delta)
        else:
            delta = 0.01 if is_metadata else 0.03
            new_affinity = min(1.0, current_affinity + delta)
        if is_metadata:
            new_affinity = min(0.6, new_affinity)
        self.profile["genre_affinities"][predicted_genre] = new_affinity
        
        # Track preset preference (skip empty)
        if predicted_preset:
            if predicted_preset not in self.profile["preset_preferences"]:
                self.profile["preset_preferences"][predicted_preset] = []
            self.profile["preset_preferences"][predicted_preset].append(confidence)
        
        # Log for audit trail
        self.profile["feedback_log"].append({
            "track_id": track_id,
            "track_name": track_name,
            "artist": artist,
            "genre": predicted_genre,
            "preset": predicted_preset,
            "confidence": confidence,
            "action": "skip" if is_skip else "play",
            "dwell_time_sec": dwell_time_sec,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 500 entries to avoid bloat
        if len(self.profile["feedback_log"]) > 500:
            self.profile["feedback_log"] = self.profile["feedback_log"][-500:]
        
        self.save()
    
    def log_manual_feedback(self, track_id, predicted_genre, actual_genre, action="corrected"):
        """
        User manually corrected EQ or genre (active learning).
        
        Args:
            track_id: Spotify track ID
            predicted_genre: What we predicted
            actual_genre: What user indicated (via manual EQ switch)
            action: "corrected", "skipped", "replayed"
        """
        # Strong learning signal: user explicitly corrected our prediction
        if action == "corrected":
            # Penalize old prediction
            old_affinity = self.profile["genre_affinities"].get(predicted_genre, 0.5)
            self.profile["genre_affinities"][predicted_genre] = max(0.0, old_affinity - 0.10)
            
            # Reward correct genre
            new_affinity = self.profile["genre_affinities"].get(actual_genre, 0.5)
            self.profile["genre_affinities"][actual_genre] = min(1.0, new_affinity + 0.15)
        
        elif action == "replayed":
            # User replayed = they loved it
            affinity = self.profile["genre_affinities"].get(predicted_genre, 0.5)
            self.profile["genre_affinities"][predicted_genre] = min(1.0, affinity + 0.12)
            self.profile["replay_patterns"][predicted_genre] = \
                self.profile["replay_patterns"].get(predicted_genre, 0) + 1
            self.profile["listening_stats"]["total_replays"] += 1
        
        self.profile["feedback_log"].append({
            "track_id": track_id,
            "predicted_genre": predicted_genre,
            "actual_genre": actual_genre,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        
        self.save()
    
    def get_genre_affinity(self, genre):
        """Get affinity score for genre (0.0-1.0)."""
        return self.profile["genre_affinities"].get(genre, 0.5)
    
    def get_top_genres(self, n=5):
        """Get user's top N favorite genres."""
        sorted_genres = sorted(
            self.profile["genre_affinities"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_genres[:n]
    
    def get_preset_stats(self, preset):
        """Get average confidence for a preset."""
        confidences = self.profile["preset_preferences"].get(preset, [])
        if not confidences:
            return {"avg_confidence": 0.0, "count": 0}
        
        return {
            "avg_confidence": statistics.mean(confidences),
            "count": len(confidences),
            "min": min(confidences),
            "max": max(confidences)
        }
    
    def get_skip_rate_for_genre(self, genre):
        """Calculate skip rate for a genre (0.0-1.0)."""
        genre_plays = sum(
            1 for log in self.profile["feedback_log"]
            if log.get("genre") == genre
        )
        if genre_plays == 0:
            return 0.0
        
        genre_skips = self.profile["skip_patterns"].get(genre, 0)
        return genre_skips / genre_plays
    
    def print_profile_summary(self):
        """Pretty-print listener profile stats."""
        stats = self.profile["listening_stats"]
        print("\n" + "=" * 60)
        print("  👤 Listener Profile Summary")
        print("=" * 60)
        print(f"  Total Tracks:     {stats['total_tracks']}")
        print(f"  Total Skips:      {stats['total_skips']} ({100*stats['total_skips']/max(1, stats['total_tracks']):.1f}%)")
        print(f"  Total Replays:    {stats['total_replays']}")
        
        top_genres = self.get_top_genres(5)
        if top_genres:
            print(f"\n  🎵 Top Genres (by affinity):")
            for genre, affinity in top_genres:
                skip_rate = self.get_skip_rate_for_genre(genre)
                print(f"     {genre:15} {affinity:5.1%} affinity | {skip_rate:5.1%} skip rate")
        
        print("\n  🎛️ EQ Presets Used:")
        for preset, confidences in sorted(self.profile["preset_preferences"].items()):
            avg_conf = statistics.mean(confidences)
            print(f"     {preset:15} x{len(confidences):3} (avg conf: {avg_conf:.1%})")
        
        print("=" * 60 + "\n")
    
    def export_feedback_for_training(self, min_genre_threshold=5):
        """
        Export feedback logs as (genre, action) pairs for training personalized model.
        
        Returns: List of (genre, label) where label = 0 (skip) or 1 (play/replay)
        """
        genre_data = defaultdict(list)
        
        for log in self.profile["feedback_log"]:
            genre = log.get("genre")
            if not genre:
                continue
            
            action = log.get("action", "play")
            label = 0 if action == "skip" else 1  # 0=skip, 1=play/replay
            genre_data[genre].append(label)
        
        # Filter genres with too few samples
        training_data = []
        for genre, labels in genre_data.items():
            if len(labels) >= min_genre_threshold:
                training_data.extend([(genre, label) for label in labels])
        
        return training_data
