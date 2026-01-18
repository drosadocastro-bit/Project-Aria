"""
Aria Auto EQ - Automatically adjusts EQ based on Spotify playback
Polls Spotify for current track and applies matching EQ preset
Enhanced with ML genre classification for unknown tracks
"""

import sys
import time
import webbrowser
import json
import csv
import base64
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import Counter
import threading
import tempfile
import os
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.audio_intelligence import (
    GenreEQMapper,
    EQ_PRESETS,
    apply_eq_to_apo,
    format_eq_for_dsp,
    GENRE_EQ_MAP,
    GTZAN_TO_EQ,
    get_ml_classifier,
    get_metadata_classifier,
    get_cnn_classifier,
    get_genre_eq_map,
    get_gtzan_to_eq,
)
from core.voice import generate_voice, play_audio
from core.listener_profile import ListenerProfile
from core.active_learning import ActiveLearningMonitor

# DSP Hardware Control (optional)
try:
    from core.dsp_controller import DSPController
except ImportError:
    DSPController = None

from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    USE_ELEVENLABS,
    DSP_HARDWARE_PROFILE,
    DSP_GAIN_OFFSET_DB,
    DSP_SUB_TRIM_DB,
    DSP_RPM_DUCKING_ENABLED,
    DSP_RPM_DUCKING_THRESHOLD,
    DSP_RPM_DUCKING_DEPTH_DB,
    EQ_CONFIDENCE_FLOOR,
    EQ_FALLBACK_PRESET,
    EQ_BLEND_MIN_PROB,
    EQ_BLEND_MAX_GAP,
    USE_CNN_GENRE,
    CNN_CONFIDENCE_FLOOR,
    USE_HARDWARE_DSP,
    DSP_METHOD,
    DSP_PORT,
    DSP_BAUDRATE,
    DSP_PROTOCOL_FILE,
    ADB_DEVICE,
    DSP_PRESET_MAPPING,
)

try:
    from core.obd_integration import obd_monitor
except Exception:
    obd_monitor = None

# Token storage
TOKEN_FILE = Path(__file__).parent / "state" / "spotify_token.json"

# ML Predictions persistence (offline cache / audit trail)
ML_PREDICTIONS_FILE = Path(__file__).parent / "state" / "ml_predictions.csv"

# ML Classification cache (avoid re-classifying same track)
_ml_cache = {}

# User preference learning
listener_profile = ListenerProfile()
active_monitor = ActiveLearningMonitor(listener_profile)

# DSP Hardware Controller (B2 Audio)
dsp_controller = None
if USE_HARDWARE_DSP and DSPController:
    try:
        dsp_controller = DSPController({
            "DSP_METHOD": DSP_METHOD,
            "DSP_PORT": DSP_PORT,
            "DSP_BAUDRATE": DSP_BAUDRATE,
            "DSP_PROTOCOL_FILE": DSP_PROTOCOL_FILE,
            "ADB_DEVICE": ADB_DEVICE,
            "DSP_PRESET_MAPPING": DSP_PRESET_MAPPING,
        })
        print(f"🎛️ DSP Controller initialized ({DSP_METHOD} mode)")
    except Exception as e:
        print(f"⚠️ DSP Controller failed to initialize: {e}")
        dsp_controller = None

# Model versioning for future confidence decay
MODEL_VERSION = "GTZAN_RF_v1.1"

# Cache limits
ML_CACHE_MAX_ENTRIES = 10000


def load_ml_predictions_cache():
    """Load persistent ML predictions from CSV into memory cache."""
    global _ml_cache
    
    if not ML_PREDICTIONS_FILE.exists():
        return 0
    
    loaded = 0
    try:
        with open(ML_PREDICTIONS_FILE, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                track_id = row.get("track_id")
                if track_id and track_id not in _ml_cache:
                    _ml_cache[track_id] = {
                        "preset": row.get("preset", "v_shape"),
                        "genre": row.get("genre_predicted", ""),
                        "confidence": float(row.get("confidence", 0.0)),
                        "top_3": row.get("top_3", ""),
                        "source": row.get("source", "csv"),
                        "timestamp": row.get("timestamp", ""),
                        "model_version": row.get("model_version", "unknown")
                    }
                    loaded += 1
    except Exception as e:
        print(f"⚠️ Failed to load ML predictions cache: {e}")
    
    if loaded > 0:
        print(f"✅ Loaded {loaded} cached ML predictions (offline-first)")
    return loaded


def save_ml_prediction(
    track_id,
    track_name,
    artist,
    genre,
    preset,
    confidence,
    top_3,
    source="ml",
    model_version=None,
):
    """Persist a single ML prediction to CSV for audit trail & offline use."""
    try:
        file_exists = ML_PREDICTIONS_FILE.exists()
        ML_PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(ML_PREDICTIONS_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "track_id", "track_name", "artist", "genre_predicted", 
                    "preset", "confidence", "top_3", "source", "timestamp", "model_version"
                ])
            
            writer.writerow([
                track_id,
                track_name or "",
                artist or "",
                genre,
                preset,
                f"{confidence:.2f}",
                str(top_3) if top_3 else "",
                source,
                datetime.now().isoformat(),
                model_version or MODEL_VERSION,
            ])
    except Exception as e:
        print(f"⚠️ Failed to save ML prediction: {e}")


def prune_ml_cache(max_entries=None):
    """
    Keep only the last N predictions in CSV (FIFO).
    Prevents unbounded growth on long listening sessions.
    Also migrates old entries to include model_version column.
    
    Returns: (kept, pruned) tuple
    """
    if max_entries is None:
        max_entries = ML_CACHE_MAX_ENTRIES
    
    if not ML_PREDICTIONS_FILE.exists():
        return 0, 0
    
    # Standard fieldnames (including new model_version)
    standard_fieldnames = [
        "track_id", "track_name", "artist", "genre_predicted", 
        "preset", "confidence", "top_3", "source", "timestamp", "model_version"
    ]
    
    try:
        # Read all entries
        with open(ML_PREDICTIONS_FILE, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        total = len(rows)
        
        # Migrate: add model_version to old entries that don't have it
        for row in rows:
            if "model_version" not in row or not row.get("model_version"):
                row["model_version"] = "unknown"
        
        if total <= max_entries:
            # Still rewrite to ensure schema is up to date
            with open(ML_PREDICTIONS_FILE, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=standard_fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(rows)
            return total, 0
        
        # Keep last N entries (most recent)
        kept_rows = rows[-max_entries:]
        pruned = total - max_entries
        
        # Rewrite file with only kept entries (and updated schema)
        with open(ML_PREDICTIONS_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=standard_fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(kept_rows)
        
        print(f"🗑️ Pruned ML cache: {pruned} old entries removed, {len(kept_rows)} kept")
        return len(kept_rows), pruned
        
    except Exception as e:
        print(f"⚠️ Failed to prune ML cache: {e}")
        return 0, 0


def get_ml_stats():
    """
    Get ML cache analytics for debugging/monitoring.
    
    Returns dict with:
        - count: Total cached entries
        - avg_confidence: Mean confidence across all predictions
        - top_presets: Most common EQ presets (top 5)
        - top_genres: Most common predicted genres (top 5)
        - oldest: Oldest prediction timestamp
        - newest: Most recent prediction timestamp
        - model_versions: Count by model version
    """
    global _ml_cache
    
    stats = {
        "count": 0,
        "avg_confidence": 0.0,
        "top_presets": [],
        "top_genres": [],
        "oldest": None,
        "newest": None,
        "model_versions": {}
    }
    
    if not _ml_cache:
        # Try loading from file if cache is empty
        if ML_PREDICTIONS_FILE.exists():
            try:
                with open(ML_PREDICTIONS_FILE, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    
                if rows:
                    stats["count"] = len(rows)
                    
                    # Confidence
                    confidences = [float(r.get("confidence", 0)) for r in rows if r.get("confidence")]
                    if confidences:
                        stats["avg_confidence"] = sum(confidences) / len(confidences)
                    
                    # Top presets
                    presets = [r.get("preset", "") for r in rows if r.get("preset")]
                    stats["top_presets"] = Counter(presets).most_common(5)
                    
                    # Top genres
                    genres = [r.get("genre_predicted", "") for r in rows if r.get("genre_predicted")]
                    stats["top_genres"] = Counter(genres).most_common(5)
                    
                    # Timestamps
                    timestamps = [r.get("timestamp", "") for r in rows if r.get("timestamp")]
                    if timestamps:
                        stats["oldest"] = min(timestamps)
                        stats["newest"] = max(timestamps)
                    
                    # Model versions
                    versions = [r.get("model_version", "unknown") for r in rows]
                    stats["model_versions"] = dict(Counter(versions))
                    
            except Exception as e:
                print(f"⚠️ Failed to read stats from file: {e}")
    else:
        # Use memory cache
        stats["count"] = len(_ml_cache)
        
        confidences = [v.get("confidence", 0) for v in _ml_cache.values()]
        if confidences:
            stats["avg_confidence"] = sum(confidences) / len(confidences)
        
        presets = [v.get("preset", "") for v in _ml_cache.values() if v.get("preset")]
        stats["top_presets"] = Counter(presets).most_common(5)
        
        genres = [v.get("genre", "") for v in _ml_cache.values() if v.get("genre")]
        stats["top_genres"] = Counter(genres).most_common(5)
        
        timestamps = [v.get("timestamp", "") for v in _ml_cache.values() if v.get("timestamp")]
        if timestamps:
            stats["oldest"] = min(timestamps)
            stats["newest"] = max(timestamps)
        
        versions = [v.get("model_version", "unknown") for v in _ml_cache.values()]
        stats["model_versions"] = dict(Counter(versions))
    
    return stats


def print_ml_stats():
    """Pretty-print ML cache statistics."""
    stats = get_ml_stats()
    
    print("\n" + "=" * 50)
    print("  📊 ML Classification Cache Stats")
    print("=" * 50)
    print(f"  Cached entries:    {stats['count']}")
    print(f"  Avg confidence:    {stats['avg_confidence']:.1%}")
    print(f"  Model version:     {MODEL_VERSION}")
    
    if stats['top_presets']:
        print(f"\n  🎛️ Top EQ Presets:")
        for preset, count in stats['top_presets']:
            print(f"     {preset:15} {count:4} tracks")
    
    if stats['top_genres']:
        print(f"\n  🎵 Top Genres:")
        for genre, count in stats['top_genres']:
            print(f"     {genre:15} {count:4} tracks")
    
    if stats['oldest']:
        print(f"\n  📅 Date range:")
        print(f"     Oldest: {stats['oldest'][:10]}")
        print(f"     Newest: {stats['newest'][:10]}")
    
    if stats['model_versions']:
        print(f"\n  🤖 Model versions:")
        for ver, count in stats['model_versions'].items():
            print(f"     {ver}: {count} predictions")
    
    print("=" * 50 + "\n")
    return stats


class SpotifyOAuth:
    """Handle Spotify OAuth for user-level API access."""
    
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    SCOPES = "user-read-currently-playing user-read-playback-state"
    
    def __init__(self):
        self.client_id = SPOTIFY_CLIENT_ID
        self.client_secret = SPOTIFY_CLIENT_SECRET
        self.redirect_uri = SPOTIFY_REDIRECT_URI
        self.access_token = None
        self.refresh_token = None
        self.token_expires = 0
        
        self._load_token()
    
    def _load_token(self):
        """Load saved token from file."""
        if TOKEN_FILE.exists():
            try:
                with open(TOKEN_FILE, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self.token_expires = data.get("expires_at", 0)
            except:
                pass
    
    def _save_token(self):
        """Save token to file."""
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, 'w') as f:
            json.dump({
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.token_expires
            }, f)
    
    def get_auth_url(self):
        """Get URL for user to authorize."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": self.SCOPES,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"
    
    def exchange_code(self, code):
        """Exchange authorization code for tokens."""
        auth_b64 = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        response = requests.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token")
            self.token_expires = time.time() + data.get("expires_in", 3600)
            self._save_token()
            return True
        else:
            print(f"❌ Token exchange failed: {response.text}")
            return False
    
    def refresh_access_token(self):
        """Refresh the access token."""
        if not self.refresh_token:
            return False
        
        auth_b64 = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        response = requests.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.token_expires = time.time() + data.get("expires_in", 3600)
            if "refresh_token" in data:
                self.refresh_token = data["refresh_token"]
            self._save_token()
            return True
        return False
    
    def get_token(self):
        """Get valid access token, refreshing if needed."""
        if self.access_token and time.time() < self.token_expires - 60:
            return self.access_token
        
        if self.refresh_token and self.refresh_access_token():
            return self.access_token
        
        return None
    
    def is_authenticated(self):
        """Check if we have valid auth."""
        return self.get_token() is not None


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""
    
    auth_code = None
    
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            CallbackHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>&#10004; Authorized!</h1>
                <p>You can close this window and return to Aria.</p>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


def authenticate_spotify(oauth):
    """Run OAuth flow to authenticate user."""
    print("\n🔐 Spotify Authentication Required")
    print("   Opening browser for authorization...")
    
    auth_url = oauth.get_auth_url()
    webbrowser.open(auth_url)
    
    # Start local server to receive callback
    port = int(SPOTIFY_REDIRECT_URI.split(":")[-1].split("/")[0])
    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120
    
    print(f"   Waiting for authorization (timeout: 2 min)...")
    
    # Wait for callback
    CallbackHandler.auth_code = None
    while CallbackHandler.auth_code is None:
        server.handle_request()
        if CallbackHandler.auth_code:
            break
    
    server.server_close()
    
    if CallbackHandler.auth_code:
        if oauth.exchange_code(CallbackHandler.auth_code):
            print("✅ Spotify authenticated successfully!")
            return True
    
    print("❌ Authentication failed")
    return False


def get_artist_genres(oauth, artist_id):
    """Get genres for an artist from Spotify API."""
    token = oauth.get_token()
    if not token:
        return []
    
    response = requests.get(
        f"https://api.spotify.com/v1/artists/{artist_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        return data.get("genres", [])
    return []


def get_current_track(oauth):
    """Get currently playing track from Spotify with artist genres and preview URL."""
    token = oauth.get_token()
    if not token:
        return None
    
    response = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5
    )
    
    if response.status_code == 200 and response.content:
        data = response.json()
        if data and data.get("item"):
            artist_id = data["item"]["artists"][0]["id"]
            # Fetch artist genres from Spotify
            spotify_genres = get_artist_genres(oauth, artist_id)
            
            return {
                "track_id": data["item"]["id"],
                "track_name": data["item"]["name"],
                "artist": data["item"]["artists"][0]["name"],
                "artist_id": artist_id,
                "album": data["item"]["album"]["name"],
                "is_playing": data.get("is_playing", False),
                "popularity": data["item"].get("popularity", 0),
                "spotify_genres": spotify_genres,  # Artist genres from Spotify
                "preview_url": data["item"].get("preview_url")  # 30-sec MP3 preview for ML
            }
    elif response.status_code == 204:
        return None  # Nothing playing
    elif response.status_code == 401:
        oauth.refresh_access_token()
        return get_current_track(oauth)
    
    return None


def genres_to_eq_preset(genres):
    """Map a list of genres to an EQ preset with confidence."""
    if not genres:
        return "v_shape", None, 0.0
    
    # Load mappings (prefers JSON config)
    genre_map = get_genre_eq_map()
    
    # Priority 1: Exact match
    for genre in genres:
        genre_lower = genre.lower().strip()
        if genre_lower in genre_map:
            return genre_map[genre_lower], genre_lower, 1.0
    
    # Priority 2: Partial/substring match
    for genre in genres:
        genre_lower = genre.lower().strip()
        for key, preset in genre_map.items():
            if key in genre_lower or genre_lower in key:
                return preset, f"{genre_lower}~{key}", 0.85
    
    # Priority 3: Word-level matching (e.g., "barbadian pop" contains "pop")
    for genre in genres:
        words = genre.lower().split()
        for word in words:
            if word in genre_map:
                return genre_map[word], f"{genre}→{word}", 0.70
    
    # No match
    return "v_shape", None, 0.0


def classify_track_with_metadata(track):
    """Predict EQ preset using metadata-only classifier (no audio required)."""
    if not track:
        return None, 0.0

    classifier = get_metadata_classifier()
    if classifier is None or not classifier.is_trained:
        return None, 0.0

    try:
        popularity_value = track.get("popularity", 0)
        preset, confidence = classifier.predict_preset_from_metadata(popularity_value)
        if preset:
            return preset, confidence
    except Exception as e:
        print(f"   ⚠️ Metadata classify failed: {e}")

    return None, 0.0


def apply_preference_boost(genre, confidence):
    """
    Boost or penalize confidence based on listener's genre preferences.
    
    Returns: (adjusted_confidence, boost_explanation)
    """
    if not listener_profile or not genre:
        return confidence, ""
    
    affinity = listener_profile.get_genre_affinity(genre)
    skip_rate = listener_profile.get_skip_rate_for_genre(genre)
    
    # Boost factor based on affinity
    if affinity >= 0.80:
        boost = +0.15
        reason = f"High affinity ({affinity:.0%})"
    elif affinity >= 0.65:
        boost = +0.08
        reason = f"Good affinity ({affinity:.0%})"
    elif affinity <= 0.30:
        boost = -0.15
        reason = f"Low affinity ({affinity:.0%})"
    elif affinity <= 0.45:
        boost = -0.08
        reason = f"Poor affinity ({affinity:.0%})"
    else:
        boost = 0.0
        reason = ""
    
    # Extra penalty if skip rate is high
    if skip_rate > 0.5:
        boost -= 0.10
        reason += f" | High skip rate ({skip_rate:.0%})"
    
    adjusted = max(0.0, min(1.0, confidence + boost))
    return adjusted, reason


def blend_eq_presets(top_3, gtzan_map, min_prob=0.35, max_gap=0.12):
    """
    Blend two EQ presets when ML top-2 genres are close.

    Returns: (label, blended_bands, reason) or (None, None, None)
    """
    if not top_3 or len(top_3) < 2:
        return None, None, None

    (genre_1, prob_1), (genre_2, prob_2) = top_3[:2]

    if prob_1 < min_prob:
        return None, None, None
    if (prob_1 - prob_2) > max_gap:
        return None, None, None

    preset_1 = gtzan_map.get(genre_1)
    preset_2 = gtzan_map.get(genre_2)
    if not preset_1 or not preset_2 or preset_1 == preset_2:
        return None, None, None

    bands_1 = EQ_PRESETS.get(preset_1)
    bands_2 = EQ_PRESETS.get(preset_2)
    if not bands_1 or not bands_2:
        return None, None, None

    weight_1 = prob_1 / (prob_1 + prob_2)
    weight_2 = 1.0 - weight_1

    blended_bands = [
        (b1 * weight_1) + (b2 * weight_2)
        for b1, b2 in zip(bands_1, bands_2)
    ]

    label = f"blend({preset_1}+{preset_2})"
    reason = f"{genre_1}:{prob_1:.0%} + {genre_2}:{prob_2:.0%}"
    return label, blended_bands, reason


def classify_track_with_ml(track_id, preview_url, track_name=None, artist=None):
    """
    Use ML classifier to detect genre from Spotify's 30-second preview.
    Results are cached in memory AND persisted to CSV for offline use.
    
    Returns:
        (preset_name, genre, confidence) or (None, None, 0.0) on failure
    """
    global _ml_cache
    
    # Check memory cache first (includes entries loaded from CSV)
    if track_id in _ml_cache:
        cached = _ml_cache[track_id]
        source = cached.get("source", "cache")
        print(f"   💾 Cache hit ({source}): {cached['genre']} → {cached['preset']}")
        return cached["preset"], cached["genre"], cached["confidence"]
    
    if not preview_url:
        return None, None, 0.0
    
    classifier = get_ml_classifier()
    if classifier is None or not classifier.is_trained:
        return None, None, 0.0
    model_version = getattr(classifier, "model_version", MODEL_VERSION)
    
    # Use dynamic GTZAN mapping (prefers JSON config)
    gtzan_map = get_gtzan_to_eq()
    
    try:
        # Download preview audio
        print(f"   🤖 ML: Downloading preview for analysis...")
        response = requests.get(preview_url, timeout=10)
        if response.status_code != 200:
            print(f"   ⚠️ ML: Preview download failed ({response.status_code})")
            return None, None, 0.0
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        try:
            best = None

            # Extract features and classify with GTZAN RF
            from core.genre_classifier import LiveAudioAnalyzer
            analyzer = LiveAudioAnalyzer(classifier)
            result = analyzer.classify_audio(filepath=tmp_path)

            if result and result.get("genre"):
                ml_genre = result["genre"]
                confidence = result["confidence"]
                preset = gtzan_map.get(ml_genre, "v_shape")
                top_3 = result.get("top_3", [])
                best = {
                    "preset": preset,
                    "genre": ml_genre,
                    "confidence": confidence,
                    "top_3": top_3,
                    "source": "ml",
                    "model_version": model_version,
                }

            # Optional CNN inference (PyTorch) for complex/mixed tracks
            if USE_CNN_GENRE:
                cnn = get_cnn_classifier()
                if cnn and cnn.is_trained:
                    cnn_result = cnn.predict_audio(Path(tmp_path))
                    if cnn_result and cnn_result.get("genre"):
                        cnn_conf = cnn_result.get("confidence", 0.0)
                        if cnn_conf >= CNN_CONFIDENCE_FLOOR and (
                            best is None or cnn_conf > best.get("confidence", 0.0)
                        ):
                            cnn_genre = cnn_result["genre"]
                            best = {
                                "preset": gtzan_map.get(cnn_genre, "v_shape"),
                                "genre": cnn_genre,
                                "confidence": cnn_conf,
                                "top_3": cnn_result.get("top_3", []),
                                "source": "cnn",
                                "model_version": "CNN_v1",
                            }

            if best:
                # Cache result in memory
                _ml_cache[track_id] = {
                    "preset": best["preset"],
                    "genre": best["genre"],
                    "confidence": best["confidence"],
                    "top_3": best["top_3"],
                    "source": best["source"],
                }

                # Persist to CSV for offline use & audit trail
                save_ml_prediction(
                    track_id=track_id,
                    track_name=track_name,
                    artist=artist,
                    genre=best["genre"],
                    preset=best["preset"],
                    confidence=best["confidence"],
                    top_3=best["top_3"],
                    source=best["source"],
                    model_version=best["model_version"],
                )

                print(f"   🤖 ML: Detected {best['genre']} ({best['confidence']:.0%}) → {best['preset']} [{best['source']}]")
                return best["preset"], best["genre"], best["confidence"]
        finally:
            # Cleanup temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
                
    except ImportError:
        print("   ⚠️ ML: librosa not installed (pip install librosa)")
    except Exception as e:
        print(f"   ⚠️ ML: Classification failed: {e}")
    
    return None, None, 0.0


_rpm_ducking_warned = False

def read_rpm_for_ducking():
    """Best-effort RPM read for sub ducking; silent if unavailable."""
    global _rpm_ducking_warned
    if not DSP_RPM_DUCKING_ENABLED:
        return None
    try:
        if obd_monitor and getattr(obd_monitor, "connected", False):
            data = obd_monitor.get_live_data()
            if data and data.get("rpm") is not None:
                return data.get("rpm")
    except Exception as e:
        # Warn once to avoid log spam
        if not _rpm_ducking_warned:
            print(f"⚠️ RPM ducking unavailable: {e}")
            _rpm_ducking_warned = True
    return None


def shape_eq_for_hardware(eq_bands, rpm=None):
    """Apply hardware gain offsets, sub trim, and RPM ducking."""
    bands = list(eq_bands)
    notes = []
    if DSP_GAIN_OFFSET_DB != 0:
        bands = [g + DSP_GAIN_OFFSET_DB for g in bands]
        notes.append(f"gain {DSP_GAIN_OFFSET_DB:+.1f}dB")

    if DSP_SUB_TRIM_DB != 0:
        for idx in (0, 1):  # 31Hz, 62Hz
            bands[idx] += DSP_SUB_TRIM_DB
        notes.append(f"sub {DSP_SUB_TRIM_DB:+.1f}dB")

    if (
        DSP_RPM_DUCKING_ENABLED
        and rpm is not None
        and rpm >= DSP_RPM_DUCKING_THRESHOLD
        and DSP_RPM_DUCKING_DEPTH_DB != 0
    ):
        for idx in (0, 1):
            bands[idx] += DSP_RPM_DUCKING_DEPTH_DB
        notes.append(
            f"rpm>{DSP_RPM_DUCKING_THRESHOLD}→{DSP_RPM_DUCKING_DEPTH_DB:+.1f}dB"
        )

    return bands, notes


def enforce_confidence_floor(preset_name, confidence):
    """Fallback to balanced preset if confidence is too low."""
    fallback = EQ_FALLBACK_PRESET if EQ_FALLBACK_PRESET in EQ_PRESETS else "v_shape"
    if confidence < EQ_CONFIDENCE_FLOOR:
        print(
            f"   ⚠️ Confidence {confidence:.0%} below floor {EQ_CONFIDENCE_FLOOR:.0%}; using {fallback}"
        )
        return fallback, True
    return preset_name, False


def auto_eq_loop(oauth, mapper, interval=3, voice_enabled=True, driving_mode=False, ml_enabled=True):
    """Main loop - poll Spotify and auto-adjust EQ."""
    print("\n" + "=" * 60)
    print("  🎵 AUTO EQ MODE - Monitoring Spotify")
    print(f"  🎙️ Voice: {'ON' if voice_enabled else 'OFF'}")
    print(f"  🤖 ML Fallback: {'ON' if ml_enabled else 'OFF'}")
    print(f"  🚗 Driving Mode: {'ON (safe)' if driving_mode else 'OFF (verbose)'}")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    
    last_track_id = None
    current_preset = "flat"
    current_bands = EQ_PRESETS["flat"]
    last_voice_time = 0
    VOICE_COOLDOWN = 60 if driving_mode else 5  # Rate limit: 60s driving, 5s parked
    MIN_CONFIDENCE = 0.80  # Don't announce if confidence below this
    last_rpm_ducked = False
    
    # Voice phrases - driving mode uses ultra-short
    eq_phrases_driving = {
        "rock": "EQ: Rock.",
        "metal": "EQ: Metal.",
        "electronic": "EQ: Electronic.",
        "edm": "EQ: EDM.",
        "phonk": "EQ: Phonk.",
        "lofi": "EQ: Lo-fi.",
        "hip_hop": "EQ: Hip-hop.",
        "pop": "EQ: Pop.",
        "latin": "EQ: Latin.",
        "acoustic": "EQ: Acoustic.",
        "classical": "EQ: Classical.",
        "jazz": "EQ: Jazz.",
        "v_shape": "EQ: V-shape.",
        "flat": "EQ: Flat.",
        "r_and_b": "EQ: R and B.",
        "country": "EQ: Country.",
    }
    
    eq_phrases_parked = {
        "rock": "Switching to rock mode. Let's crank it up.",
        "metal": "Metal preset engaged. Time to headbang.",
        "electronic": "Electronic mode activated.",
        "edm": "E.D.M. preset. Festival mode engaged.",
        "phonk": "Phonk mode. Heavy bass, let's drift.",
        "lofi": "Lo-fi chill activated. Vibes only.",
        "hip_hop": "Hip hop EQ. Feeling the beat.",
        "pop": "Pop preset. Nice and balanced.",
        "latin": "Latin vibes. Let's dance.",
        "acoustic": "Acoustic mode. Keeping it natural.",
        "classical": "Classical preset. Pure and clean.",
        "jazz": "Jazz mode. Smooth tones.",
        "v_shape": "V-shape EQ applied.",
        "flat": "Resetting to flat.",
        "r_and_b": "R and B preset. Smooth vibes.",
        "country": "Country mode. Twangy.",
    }
    
    def should_announce(confidence, current_time):
        """Gate: decide if voice announcement is allowed."""
        if not voice_enabled:
            return False
        if confidence < MIN_CONFIDENCE:
            return False
        if current_time - last_voice_time < VOICE_COOLDOWN:
            return False
        return True
    
    def speak(preset, confidence):
        """Generate and play voice if allowed."""
        nonlocal last_voice_time
        current_time = time.time()
        
        if not should_announce(confidence, current_time):
            if confidence < MIN_CONFIDENCE:
                print(f"   🔇 Voice skipped (confidence {confidence:.0%} < {MIN_CONFIDENCE:.0%})")
            return
        
        phrases = eq_phrases_driving if driving_mode else eq_phrases_parked
        phrase = phrases.get(preset, f"EQ: {preset}.")
        
        try:
            audio_path = generate_voice(phrase)
            if audio_path:
                time.sleep(0.3)
                play_audio(audio_path)
                last_voice_time = current_time
        except Exception as e:
            print(f"   ⚠️ Voice error: {e}")
    
    while True:
        try:
            rpm_value = read_rpm_for_ducking()
            track = get_current_track(oauth)
            
            if track and track.get("is_playing"):
                track_id = track["track_id"]
                
                # Only update if track changed
                if track_id != last_track_id:
                    if last_track_id is not None:
                        active_monitor.on_track_ended(action="normal")
                    last_track_id = track_id
                    
                    # Get genres from Spotify API (artist genres)
                    spotify_genres = track.get("spotify_genres", [])
                    source = "spotify"
                    custom_bands = None
                    
                    # First try: Spotify artist genres
                    new_preset, matched_genre, confidence = genres_to_eq_preset(spotify_genres)
                    genres = spotify_genres
                    
                    # Fallback 1: Try our local dataset if Spotify didn't match
                    if confidence == 0.0:
                        result = mapper.get_eq_for_track(
                            track_name=track["track_name"],
                            artist=track["artist"]
                        )
                        if result.get("confidence", 0.0) > 0:
                            new_preset = result.get("preset", "v_shape")
                            matched_genre = result.get("matched_genre")
                            confidence = result.get("confidence", 0.0)
                            genres = result.get("genres", [])
                            source = "database"

                    # Fallback 2: metadata-based preset classifier (no audio needed)
                    if confidence == 0.0:
                        metadata_classifier = get_metadata_classifier()
                        meta_preset, meta_confidence = classify_track_with_metadata(track)
                        if meta_preset:
                            new_preset = meta_preset
                            matched_genre = "metadata_popularity"
                            confidence = meta_confidence
                            source = "metadata_classifier"
                            model_version = (
                                getattr(metadata_classifier, "model_version", MODEL_VERSION)
                                if metadata_classifier
                                else MODEL_VERSION
                            )

                            # Persist lightweight prediction for audit/cache
                            _ml_cache[track_id] = {
                                "preset": meta_preset,
                                "genre": "metadata",
                                "confidence": meta_confidence,
                                "top_3": [],
                                "source": "metadata",
                            }
                            save_ml_prediction(
                                track_id=track_id,
                                track_name=track.get("track_name"),
                                artist=track.get("artist"),
                                genre="metadata",
                                preset=meta_preset,
                                confidence=meta_confidence,
                                top_3=[],
                                source="metadata",
                                model_version=model_version,
                            )
                    
                    # Fallback 3: ML classification from audio preview
                    if confidence == 0.0 and ml_enabled:
                        preview_url = track.get("preview_url")
                        ml_preset, ml_genre, ml_confidence = classify_track_with_ml(
                            track_id, preview_url,
                            track_name=track["track_name"],
                            artist=track["artist"]
                        )
                        if ml_preset and ml_confidence > 0.5:
                            new_preset = ml_preset
                            matched_genre = f"ML:{ml_genre}"
                            confidence = ml_confidence
                            genres = [ml_genre]
                            source = "ml_classifier"
                            
                            # LAYER 2: Apply adaptive preference boosting
                            adjusted_confidence, boost_reason = apply_preference_boost(ml_genre, confidence)
                            if boost_reason:
                                print(f"   📈 Preference boost: {confidence:.0%} → {adjusted_confidence:.0%} ({boost_reason})")
                                confidence = adjusted_confidence

                            # Mixed-genre handling: blend EQ when top-2 are close
                            top_3 = _ml_cache.get(track_id, {}).get("top_3", [])
                            gtzan_map = get_gtzan_to_eq()
                            blend_label, blended_bands, blend_reason = blend_eq_presets(
                                top_3,
                                gtzan_map,
                                min_prob=EQ_BLEND_MIN_PROB,
                                max_gap=EQ_BLEND_MAX_GAP,
                            )
                            if blended_bands:
                                new_preset = blend_label
                                custom_bands = blended_bands
                                if len(top_3) >= 2:
                                    genres = [top_3[0][0], top_3[1][0]]
                                    matched_genre = f"ML:blend({genres[0]}+{genres[1]})"
                                source = "ml_blend"
                                print(f"   🎚️ Blend EQ: {blend_label} ({blend_reason})")

                    # Confidence guard → balanced fallback
                    new_preset, forced_fallback = enforce_confidence_floor(new_preset, confidence)
                    if forced_fallback:
                        source = "confidence_guard"
                        matched_genre = matched_genre or "low_confidence"
                        custom_bands = None
                    
                    # Resolve predicted genre for learning/logging
                    if genres:
                        predicted_genre = str(genres[0])
                    else:
                        predicted_genre = matched_genre or "unknown"
                    if predicted_genre.startswith("ML:"):
                        predicted_genre = predicted_genre[3:]
                    if predicted_genre.startswith("metadata_"):
                        predicted_genre = "metadata"

                    active_monitor.on_track_started(track_id, predicted_genre)

                    # Logging - truthful about intent
                    print(f"\n🎵 Now Playing: {track['track_name']} - {track['artist']}")
                    if genres:
                        print(f"   🏷️ Genres: {', '.join(str(g) for g in genres[:5] if g)} (source: {source})")
                    
                    ducking_now = (
                        DSP_RPM_DUCKING_ENABLED
                        and rpm_value is not None
                        and rpm_value >= DSP_RPM_DUCKING_THRESHOLD
                    )
                    if not new_preset:
                        new_preset = EQ_FALLBACK_PRESET if EQ_FALLBACK_PRESET in EQ_PRESETS else "v_shape"
                    base_bands = custom_bands if custom_bands else EQ_PRESETS[new_preset]
                    shaped_bands, shape_notes = shape_eq_for_hardware(
                        base_bands, rpm=rpm_value
                    )

                    # Apply EQ if preset changed or ducking state changed
                    if new_preset != current_preset or ducking_now != last_rpm_ducked:
                        # Hardware DSP preset switching (if enabled)
                        if dsp_controller:
                            try:
                                dsp_controller.set_preset(new_preset)
                            except Exception as e:
                                print(f"⚠️ DSP preset switch failed: {e}")
                        
                        # Software EQ (Equalizer APO)
                        apply_eq_to_apo(shaped_bands, f"{new_preset} | {DSP_HARDWARE_PROFILE}")
                        current_bands = base_bands
                        
                        # LAYER 1: Log to listener profile for learning
                        predicted_genre = predicted_genre or "unknown"
                        listener_profile.log_track_prediction(
                            track_id=track_id,
                            track_name=track["track_name"],
                            artist=track["artist"],
                            predicted_genre=predicted_genre,
                            predicted_preset=new_preset,
                            confidence=confidence,
                            dwell_time_sec=0  # Will update on skip
                        )

                        # Truthful reason logging
                        if matched_genre:
                            print(f"   🎛️ EQ applied: {new_preset}")
                            print(f"   📋 Reason: {matched_genre} → {new_preset} (confidence: {confidence:.0%})")
                        else:
                            print(f"   🎛️ EQ applied: {new_preset}")
                            print(f"   📋 Reason: no genre match → default (confidence: {confidence:.0%})")

                        if shape_notes:
                            print(f"   🔧 Hardware shaping: {', '.join(shape_notes)} [{DSP_HARDWARE_PROFILE}]")

                        # Voice announcement (gated)
                        speak(new_preset, confidence)

                        current_preset = new_preset
                        last_rpm_ducked = ducking_now
                    else:
                        print(f"   🎛️ EQ: {current_preset} (unchanged)")

                else:
                    # Same track - only reapply if RPM ducking toggles state
                    ducking_now = (
                        DSP_RPM_DUCKING_ENABLED
                        and rpm_value is not None
                        and rpm_value >= DSP_RPM_DUCKING_THRESHOLD
                    )
                    if ducking_now != last_rpm_ducked:
                        shaped_bands, shape_notes = shape_eq_for_hardware(
                            current_bands, rpm=rpm_value
                        )
                        # Note: DSP preset doesn't change, only software EQ adjusts for RPM ducking
                        apply_eq_to_apo(shaped_bands, f"{current_preset} | {DSP_HARDWARE_PROFILE}")
                        print(
                            f"   🔄 RPM ducking {'engaged' if ducking_now else 'released'} at {rpm_value or 0:.0f} RPM"
                        )
                        if shape_notes:
                            print(f"   🔧 Hardware shaping: {', '.join(shape_notes)} [{DSP_HARDWARE_PROFILE}]")
                        last_rpm_ducked = ducking_now
                    else:
                        print(f"   🎛️ EQ: {current_preset} (unchanged)")
            
            elif track is None or not track.get("is_playing"):
                if last_track_id is not None:
                    print("\n⏸️ Playback paused/stopped")
                    active_monitor.on_track_ended(action="normal")
                    last_track_id = None
                    last_rpm_ducked = False
            
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n\n👋 Stopping auto EQ...")
            apply_eq_to_apo(EQ_PRESETS["flat"], "flat")
            print("   Reset to flat EQ")
            if voice_enabled:
                try:
                    phrase = "Auto EQ off." if driving_mode else "Auto EQ disabled. See you next time."
                    audio_path = generate_voice(phrase)
                    if audio_path:
                        play_audio(audio_path)
                except:
                    pass
            break
        except Exception as e:
            print(f"\n⚠️ Error: {e}")
            time.sleep(interval)


def main():
    print("=" * 60)
    print("  Aria Auto EQ - Spotify Integration + ML Classification")
    print("=" * 60)
    
    # Handle --stats flag (show analytics and exit)
    if "--stats" in sys.argv:
        load_ml_predictions_cache()
        print_ml_stats()
        return
    
    # Handle --prune flag (prune cache and exit)
    if "--prune" in sys.argv:
        kept, pruned = prune_ml_cache()
        print(f"Cache pruned: kept {kept}, removed {pruned}")
        return
    
    # Check credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("\n❌ Spotify credentials not configured!")
        print("   Set in config.py or environment variables")
        return
    
    # Initialize
    oauth = SpotifyOAuth()
    mapper = GenreEQMapper()
    
    # Load persistent ML predictions (offline-first cache)
    cached_count = load_ml_predictions_cache()
    
    # Auto-prune if cache exceeds limit (prevents unbounded growth)
    if cached_count > ML_CACHE_MAX_ENTRIES:
        prune_ml_cache()
    
    # Check ML classifier
    classifier = get_ml_classifier()
    if classifier and classifier.is_trained:
        print(f"🤖 ML classifier ready (accuracy: {classifier.accuracy:.0%})")
        print(f"   Model version: {MODEL_VERSION}")
    else:
        print("⚠️ ML classifier not trained - run: python -m core.genre_classifier")

    metadata_classifier = get_metadata_classifier()
    if metadata_classifier and metadata_classifier.is_trained:
        print(f"🧠 Metadata classifier ready (accuracy: {metadata_classifier.accuracy:.0%})")
        print(f"   Model version: {metadata_classifier.model_version}")
    else:
        print("⚠️ Metadata classifier not trained - run: python -m core.genre_classifier --train-metadata")
    
    # Check auth status
    if oauth.is_authenticated():
        print("\n✅ Already authenticated with Spotify")
    else:
        if not authenticate_spotify(oauth):
            return
    
    # Test connection
    track = get_current_track(oauth)
    if track:
        print(f"\n🎵 Currently playing: {track['track_name']} - {track['artist']}")
        if track.get("preview_url"):
            print(f"   📥 Preview available for ML analysis")
    else:
        print("\n⏸️ Nothing currently playing on Spotify")
    
    # Start auto mode
    print("\nStarting auto EQ mode...")
    print("   --no-voice    Disable voice announcements")
    print("   --no-ml       Disable ML fallback classification")
    print("   --driving     Enable driving-safe mode (short phrases, 60s cooldown)")
    print("   --stats       Show ML cache statistics")
    print("   --prune       Manually prune cache to last 10K entries")
    
    voice_on = "--no-voice" not in sys.argv
    ml_on = "--no-ml" not in sys.argv
    driving = "--driving" in sys.argv
    
    auto_eq_loop(oauth, mapper, voice_enabled=voice_on, driving_mode=driving, ml_enabled=ml_on)


if __name__ == "__main__":
    main()
