"""
Aria Auto EQ - Automatically adjusts EQ based on Spotify playback
Polls Spotify for current track and applies matching EQ preset
Enhanced with ML genre classification for unknown tracks
"""

import sys
import time
import webbrowser
import json
import base64
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent))

from core.audio_intelligence import (
    GenreEQMapper, 
    EQ_PRESETS, 
    apply_eq_to_apo,
    format_eq_for_dsp,
    GENRE_EQ_MAP,
    GTZAN_TO_EQ,
    get_ml_classifier
)
from core.voice import generate_voice, play_audio
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, USE_ELEVENLABS

# Token storage
TOKEN_FILE = Path(__file__).parent / "state" / "spotify_token.json"

# ML Classification cache (avoid re-classifying same track)
_ml_cache = {}


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
    
    # Priority 1: Exact match
    for genre in genres:
        genre_lower = genre.lower().strip()
        if genre_lower in GENRE_EQ_MAP:
            return GENRE_EQ_MAP[genre_lower], genre_lower, 1.0
    
    # Priority 2: Partial/substring match
    for genre in genres:
        genre_lower = genre.lower().strip()
        for key, preset in GENRE_EQ_MAP.items():
            if key in genre_lower or genre_lower in key:
                return preset, f"{genre_lower}~{key}", 0.85
    
    # Priority 3: Word-level matching (e.g., "barbadian pop" contains "pop")
    for genre in genres:
        words = genre.lower().split()
        for word in words:
            if word in GENRE_EQ_MAP:
                return GENRE_EQ_MAP[word], f"{genre}→{word}", 0.70
    
    # No match
    return "v_shape", None, 0.0


def classify_track_with_ml(track_id, preview_url):
    """
    Use ML classifier to detect genre from Spotify's 30-second preview.
    Results are cached to avoid re-downloading/classifying.
    
    Returns:
        (preset_name, genre, confidence) or (None, None, 0.0) on failure
    """
    global _ml_cache
    
    # Check cache first
    if track_id in _ml_cache:
        cached = _ml_cache[track_id]
        return cached["preset"], cached["genre"], cached["confidence"]
    
    if not preview_url:
        return None, None, 0.0
    
    classifier = get_ml_classifier()
    if classifier is None or not classifier.is_trained:
        return None, None, 0.0
    
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
            # Extract features and classify
            from core.genre_classifier import LiveAudioAnalyzer
            analyzer = LiveAudioAnalyzer(classifier)
            result = analyzer.classify_audio(filepath=tmp_path)
            
            if result and result.get("genre"):
                ml_genre = result["genre"]
                confidence = result["confidence"]
                preset = GTZAN_TO_EQ.get(ml_genre, "v_shape")
                
                # Cache result
                _ml_cache[track_id] = {
                    "preset": preset,
                    "genre": ml_genre,
                    "confidence": confidence,
                    "top_3": result.get("top_3", [])
                }
                
                print(f"   🤖 ML: Detected {ml_genre} ({confidence:.0%}) → {preset}")
                return preset, ml_genre, confidence
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
    last_voice_time = 0
    VOICE_COOLDOWN = 60 if driving_mode else 5  # Rate limit: 60s driving, 5s parked
    MIN_CONFIDENCE = 0.80  # Don't announce if confidence below this
    
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
            track = get_current_track(oauth)
            
            if track and track.get("is_playing"):
                track_id = track["track_id"]
                
                # Only update if track changed
                if track_id != last_track_id:
                    last_track_id = track_id
                    
                    # Get genres from Spotify API (artist genres)
                    spotify_genres = track.get("spotify_genres", [])
                    source = "spotify"
                    
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
                    
                    # Fallback 2: ML classification from audio preview
                    if confidence == 0.0 and ml_enabled:
                        preview_url = track.get("preview_url")
                        ml_preset, ml_genre, ml_confidence = classify_track_with_ml(
                            track_id, preview_url
                        )
                        if ml_preset and ml_confidence > 0.5:
                            new_preset = ml_preset
                            matched_genre = f"ML:{ml_genre}"
                            confidence = ml_confidence
                            genres = [ml_genre]
                            source = "ml_classifier"
                    
                    # Logging - truthful about intent
                    print(f"\n🎵 Now Playing: {track['track_name']} - {track['artist']}")
                    if genres:
                        print(f"   🏷️ Genres: {', '.join(genres[:5])} (source: {source})")
                    
                    # Apply EQ if preset changed
                    if new_preset != current_preset:
                        apply_eq_to_apo(EQ_PRESETS[new_preset], new_preset)
                        
                        # Truthful reason logging
                        if matched_genre:
                            print(f"   🎛️ EQ applied: {new_preset}")
                            print(f"   📋 Reason: {matched_genre} → {new_preset} (confidence: {confidence:.0%})")
                        else:
                            print(f"   🎛️ EQ applied: {new_preset}")
                            print(f"   📋 Reason: no genre match → default (confidence: {confidence:.0%})")
                        
                        # Voice announcement (gated)
                        speak(new_preset, confidence)
                        
                        current_preset = new_preset
                    else:
                        print(f"   🎛️ EQ: {current_preset} (unchanged)")
            
            elif track is None or not track.get("is_playing"):
                if last_track_id is not None:
                    print("\n⏸️ Playback paused/stopped")
                    last_track_id = None
            
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
    
    # Check credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("\n❌ Spotify credentials not configured!")
        print("   Set in config.py or environment variables")
        return
    
    # Initialize
    oauth = SpotifyOAuth()
    mapper = GenreEQMapper()
    
    # Check ML classifier
    classifier = get_ml_classifier()
    if classifier and classifier.is_trained:
        print(f"🤖 ML classifier ready (accuracy: {classifier.accuracy:.0%})")
    else:
        print("⚠️ ML classifier not trained - run: python -m core.genre_classifier")
    
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
    
    voice_on = "--no-voice" not in sys.argv
    ml_on = "--no-ml" not in sys.argv
    driving = "--driving" in sys.argv
    
    auto_eq_loop(oauth, mapper, voice_enabled=voice_on, driving_mode=driving, ml_enabled=ml_on)


if __name__ == "__main__":
    main()
