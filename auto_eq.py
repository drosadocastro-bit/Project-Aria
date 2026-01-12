"""
Aria Auto EQ - Automatically adjusts EQ based on Spotify playback
Polls Spotify for current track and applies matching EQ preset
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

sys.path.insert(0, str(Path(__file__).parent))

from core.audio_intelligence import (
    GenreEQMapper, 
    EQ_PRESETS, 
    apply_eq_to_apo,
    format_eq_for_dsp
)
from core.voice import generate_voice, play_audio
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, USE_ELEVENLABS

# Token storage
TOKEN_FILE = Path(__file__).parent / "state" / "spotify_token.json"


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


def get_current_track(oauth):
    """Get currently playing track from Spotify."""
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
            return {
                "track_id": data["item"]["id"],
                "track_name": data["item"]["name"],
                "artist": data["item"]["artists"][0]["name"],
                "album": data["item"]["album"]["name"],
                "is_playing": data.get("is_playing", False)
            }
    elif response.status_code == 204:
        return None  # Nothing playing
    elif response.status_code == 401:
        oauth.refresh_access_token()
        return get_current_track(oauth)
    
    return None


def auto_eq_loop(oauth, mapper, interval=3, voice_enabled=True, driving_mode=False):
    """Main loop - poll Spotify and auto-adjust EQ."""
    print("\n" + "=" * 60)
    print("  🎵 AUTO EQ MODE - Monitoring Spotify")
    print(f"  🎙️ Voice: {'ON' if voice_enabled else 'OFF'}")
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
                    
                    # Try to find in our dataset
                    result = mapper.get_eq_for_track(
                        track_name=track["track_name"],
                        artist=track["artist"]
                    )
                    
                    # Extract results
                    new_preset = result.get("preset", "v_shape")
                    matched_genre = result.get("matched_genre")
                    confidence = result.get("confidence", 0.0)
                    genres = result.get("genres", [])
                    
                    # Logging - truthful about intent
                    print(f"\n🎵 Now Playing: {track['track_name']} - {track['artist']}")
                    if genres:
                        print(f"   Genres: {', '.join(genres[:4])}")
                    
                    # Apply EQ if preset changed
                    if new_preset != current_preset:
                        apply_eq_to_apo(EQ_PRESETS[new_preset], new_preset)
                        
                        # Truthful reason logging
                        if matched_genre:
                            print(f"   🎛️ EQ applied: {new_preset}")
                            print(f"   📋 Reason: {matched_genre} → {new_preset} (confidence: {confidence:.0%})")
                        else:
                            print(f"   🎛️ EQ applied: {new_preset}")
                            print(f"   📋 Reason: no match → default (confidence: {confidence:.0%})")
                        
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
    print("  Aria Auto EQ - Spotify Integration")
    print("=" * 60)
    
    # Check credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("\n❌ Spotify credentials not configured!")
        print("   Set in config.py or environment variables")
        return
    
    # Initialize
    oauth = SpotifyOAuth()
    mapper = GenreEQMapper()
    
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
    else:
        print("\n⏸️ Nothing currently playing on Spotify")
    
    # Start auto mode
    print("\nStarting auto EQ mode...")
    print("   --no-voice    Disable voice announcements")
    print("   --driving     Enable driving-safe mode (short phrases, 60s cooldown)")
    
    voice_on = "--no-voice" not in sys.argv
    driving = "--driving" in sys.argv
    
    auto_eq_loop(oauth, mapper, voice_enabled=voice_on, driving_mode=driving)


if __name__ == "__main__":
    main()
