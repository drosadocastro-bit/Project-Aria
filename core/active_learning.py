"""
Active Learning Feedback Capture - Detects user corrections and learning signals
Monitors: manual EQ switches, skips, replays for real-time model adaptation
"""

from pathlib import Path
from datetime import datetime


class ActiveLearningMonitor:
    """
    Captures user interactions as training signals for model adaptation.
    Detects:
    - Manual EQ changes (user disagreed with our prediction)
    - Early skips (< 10 sec = likely wrong genre prediction)
    - Replays (user loved the genre/preset)
    """
    
    def __init__(self, listener_profile):
        self.profile = listener_profile
        self.last_track_id = None
        self.track_start_time = None
        self.current_predicted_genre = None
    
    def on_track_started(self, track_id, predicted_genre):
        """Called when a new track starts playing."""
        self.last_track_id = track_id
        self.current_predicted_genre = predicted_genre
        self.track_start_time = datetime.now()
    
    def on_track_ended(self, action="normal"):
        """
        Called when track ends or user acts.
        
        Args:
            action: "skip" (< 10 sec), "normal" (completed), "replay" (restarted)
        """
        if not self.track_start_time:
            return
        
        dwell_time = (datetime.now() - self.track_start_time).total_seconds()
        
        # Auto-detect skip if not specified
        if action == "normal" and dwell_time < 10:
            action = "skip"
        
        if action == "skip":
            self.profile.log_track_prediction(
                track_id=self.last_track_id or "unknown",
                track_name="",
                artist="",
                predicted_genre=self.current_predicted_genre or "unknown",
                predicted_preset="",
                confidence=0.5,
                dwell_time_sec=dwell_time
            )
        elif action == "replay":
            self.profile.log_manual_feedback(
                track_id=self.last_track_id or "unknown",
                predicted_genre=self.current_predicted_genre or "unknown",
                actual_genre=self.current_predicted_genre or "unknown",
                action="replayed"
            )
        
        self.last_track_id = None
        self.track_start_time = None
        self.current_predicted_genre = None
    
    def on_manual_eq_change(self, predicted_genre, new_preset):
        """
        Called when user manually switches EQ preset.
        Interprets as: "You got the genre wrong"
        
        Args:
            predicted_genre: What we predicted
            new_preset: What user switched to
        """
        # Map preset back to likely genre
        preset_to_genre_guess = {
            "rock": "rock",
            "metal": "metal",
            "electronic": "electronic",
            "edm": "edm",
            "phonk": "phonk",
            "lofi": "classical",
            "hip_hop": "hiphop",
            "pop": "pop",
            "latin": "reggae",  # Approximation
            "acoustic": "country",
            "classical": "classical",
            "jazz": "jazz",
            "v_shape": "rock",
            "r_and_b": "hiphop",
            "country": "country",
        }
        
        actual_genre = preset_to_genre_guess.get(new_preset, "unknown")
        
        if predicted_genre != actual_genre:
            self.profile.log_manual_feedback(
                track_id=self.last_track_id or "unknown",
                predicted_genre=predicted_genre,
                actual_genre=actual_genre,
                action="corrected"
            )
            
            print(f"   [ACTIVE LEARNING] User corrected: {predicted_genre} → {actual_genre}")
    
    def get_training_confidence(self):
        """
        Returns how confident we are in personalized model based on feedback volume.
        
        Returns: 0.0-1.0 (0 = need more data, 1.0 = strong signal)
        """
        feedback_count = len(self.profile.profile["feedback_log"])
        
        if feedback_count < 10:
            return 0.0
        elif feedback_count < 50:
            return 0.3
        elif feedback_count < 100:
            return 0.6
        elif feedback_count < 200:
            return 0.8
        else:
            return 1.0
    
    def should_trigger_retraining(self):
        """Returns True if enough feedback to justify personal retraining."""
        feedback_count = len(self.profile.profile["feedback_log"])
        return feedback_count >= 50 and feedback_count % 50 == 0  # Every 50 new entries
