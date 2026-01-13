"""
Audio Intelligence Module - Genre-Based DSP EQ Integration
Maps track genres to EQ presets using existing dataset clusters
Enhanced with ML-based genre classification from GTZAN dataset
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path

# Dataset paths
DATASET_PATH = Path(__file__).parent.parent / "music_dataset"
TRACKS_FILE = DATASET_PATH / "track_genre_clusters.csv"
GENRE_ENCODED_FILE = DATASET_PATH / "cleaned_track_metadata_with_genres_encoded.csv"

# JSON config for editable genre mappings
CONFIG_PATH = Path(__file__).parent.parent / "config"
GENRE_MAPPING_FILE = CONFIG_PATH / "genre_eq_mapping.json"

# ML Genre Classifier (lazy import to avoid circular deps)
_ml_classifier = None

# Cached JSON mappings (loaded once)
_genre_eq_map_cache = None
_gtzan_to_eq_cache = None


def load_genre_mappings():
    """Load genre→EQ mappings from JSON config file."""
    global _genre_eq_map_cache, _gtzan_to_eq_cache
    
    if _genre_eq_map_cache is not None:
        return _genre_eq_map_cache, _gtzan_to_eq_cache
    
    if GENRE_MAPPING_FILE.exists():
        try:
            with open(GENRE_MAPPING_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _genre_eq_map_cache = data.get("genre_eq_map", {})
                _gtzan_to_eq_cache = data.get("gtzan_to_eq", {})
                # Remove comment keys
                _gtzan_to_eq_cache.pop("_comment", None)
                print(f"✅ Loaded {len(_genre_eq_map_cache)} genre mappings from JSON")
                return _genre_eq_map_cache, _gtzan_to_eq_cache
        except Exception as e:
            print(f"⚠️ Failed to load genre mappings: {e}")
    
    # Fallback to None (will use hardcoded)
    return None, None


def get_ml_classifier():
    """Get or create ML genre classifier instance."""
    global _ml_classifier
    if _ml_classifier is None:
        try:
            from .genre_classifier import GenreClassifier
            _ml_classifier = GenreClassifier()
            if not _ml_classifier.is_trained:
                print("⚠️ ML classifier not trained. Run: python -m core.genre_classifier")
        except ImportError as e:
            print(f"⚠️ ML classifier unavailable: {e}")
    return _ml_classifier


# ========== EQ PRESETS ==========
# 10-band EQ, values in dB (-12 to +12 range)
# Bands: 31Hz, 62Hz, 125Hz, 250Hz, 500Hz, 1kHz, 2kHz, 4kHz, 8kHz, 16kHz

EQ_PRESETS = {
    "flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "bass_boost": [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
    "treble_boost": [0, 0, 0, 0, 0, 0, 2, 4, 5, 6],
    "v_shape": [5, 4, 2, 0, -2, -2, 0, 2, 4, 5],
    "vocal_presence": [-2, -1, 0, 2, 4, 4, 3, 2, 0, -1],
    "rock": [4, 3, 2, 0, -1, 0, 2, 3, 4, 3],
    "metal": [4, 3, 1, 0, -2, -1, 1, 4, 5, 4],
    "electronic": [5, 4, 2, 0, 1, 2, 1, 3, 4, 4],
    "acoustic": [-2, 0, 1, 2, 3, 2, 1, 2, 2, 1],
    "hip_hop": [6, 5, 3, 1, 0, 0, 1, 1, 2, 2],
    "classical": [0, 0, 0, 0, 0, 0, -1, -1, -2, -3],
    "jazz": [0, 1, 2, 2, 1, 0, 1, 2, 2, 1],
    # NEW: Phonk/Drift preset - heavy bass, crispy highs
    "phonk": [7, 6, 4, 1, -2, -2, 0, 3, 5, 4],
    # NEW: EDM/Festival preset - sub bass + bright highs
    "edm": [6, 5, 3, 0, 0, 1, 2, 4, 5, 5],
    # NEW: Lo-fi/Chill preset - warm, rolled-off highs
    "lofi": [3, 3, 2, 1, 0, 0, -1, -1, -2, -3],
    "pop": [1, 2, 3, 2, 1, 0, 1, 2, 3, 2],
    "latin": [4, 4, 3, 1, 0, 1, 2, 3, 3, 2],
    "country": [2, 2, 2, 2, 2, 1, 2, 3, 3, 2],
    "r_and_b": [5, 4, 3, 2, 1, 0, 1, 2, 2, 1],
}

# Genre to EQ preset mapping (authoritative source of truth)
GENRE_EQ_MAP = {
    # Phonk / Drift - uses dedicated phonk preset
    "phonk": "phonk", "drift phonk": "phonk", "brazilian phonk": "phonk",
    "memphis phonk": "phonk", "aggressive phonk": "phonk",
    "cowbell phonk": "phonk", "dark phonk": "phonk",
    
    # Rock variants
    "rock": "rock", "classic rock": "rock", "hard rock": "rock",
    "alternative rock": "rock", "indie rock": "rock", "punk": "rock",
    "grunge": "rock", "garage rock": "rock", "arena rock": "rock",
    "glam rock": "rock", "soft rock": "pop", "folk rock": "acoustic",
    "aor": "rock", "album rock": "rock", "modern rock": "rock",
    "post-grunge": "rock", "southern rock": "rock", "blues rock": "rock",
    
    # Metal variants
    "metal": "metal", "heavy metal": "metal", "thrash metal": "metal",
    "death metal": "metal", "black metal": "metal", "doom metal": "metal",
    "nu metal": "metal", "alternative metal": "metal", "rap metal": "metal",
    "progressive metal": "metal", "metalcore": "metal", "glam metal": "metal",
    "power metal": "metal", "gothic metal": "metal", "groove metal": "metal",
    "symphonic metal": "metal", "industrial metal": "metal", "speed metal": "metal",
    "deathcore": "metal", "djent": "metal",
    
    # Electronic / EDM variants - uses dedicated edm preset for festival stuff
    "electronic": "electronic", "edm": "edm", "house": "edm",
    "techno": "electronic", "trance": "edm", "dubstep": "edm",
    "drum and bass": "electronic", "electro": "electronic", "electro house": "edm",
    "synthwave": "electronic", "synthpop": "electronic", "chillwave": "lofi",
    "future bass": "edm", "progressive house": "edm",
    "electroclash": "electronic", "darkwave": "electronic",
    "dreamwave": "electronic", "retrowave": "electronic", "outrun": "electronic",
    "vaporwave": "lofi", "lo-fi": "lofi", "lofi": "lofi",
    "lo-fi beats": "lofi", "lofi hip hop": "lofi", "chillhop": "lofi",
    "ambient": "lofi", "downtempo": "lofi", "chillout": "lofi",
    "deep house": "electronic", "tropical house": "edm", "big room": "edm",
    "hardstyle": "edm", "hardcore": "edm", "gabber": "edm",
    "breakbeat": "electronic", "uk garage": "electronic", "bass music": "edm",
    "riddim": "edm", "brostep": "edm", "complextro": "edm",
    "future house": "edm", "electropop": "pop",
    "slap house": "edm", "brazilian bass": "edm", "tech house": "electronic",
    
    # Hip-hop variants
    "hip hop": "hip_hop", "rap": "hip_hop", "trap": "hip_hop",
    "gangster rap": "hip_hop", "g-funk": "hip_hop",
    "east coast hip hop": "hip_hop", "west coast hip hop": "hip_hop",
    "southern hip hop": "hip_hop", "latin hip hop": "hip_hop",
    "crunk": "hip_hop", "old school hip hop": "hip_hop",
    "trap soul": "hip_hop", "conscious hip hop": "hip_hop",
    "underground hip hop": "hip_hop", "dirty south": "hip_hop",
    "boom bap": "hip_hop", "mumble rap": "hip_hop", "drill": "hip_hop",
    "uk drill": "hip_hop", "chicago drill": "hip_hop",
    "trap latino": "hip_hop", "urbano": "hip_hop",
    
    # Pop variants
    "pop": "pop", "pop punk": "pop", "indie pop": "pop",
    "art pop": "pop", "k-pop": "pop", "j-pop": "pop",
    "europop": "pop", "latin pop": "pop", "soft pop": "pop",
    "power pop": "pop", "dance pop": "pop", "teen pop": "pop",
    "bubblegum pop": "pop", "synth-pop": "pop", "chamber pop": "pop",
    "dream pop": "pop", "sunshine pop": "pop", "baroque pop": "pop",
    "bedroom pop": "pop", "hyperpop": "pop", "viral pop": "pop",
    "barbadian pop": "pop", "canadian pop": "pop", "australian pop": "pop",
    "british pop": "pop", "swedish pop": "pop", "german pop": "pop",
    
    # Latin variants
    "latin": "latin", "reggaeton": "latin", "salsa": "latin",
    "bachata": "latin", "merengue": "latin", "cumbia": "latin",
    "urbano latino": "latin", "latin rock": "latin", "ranchera": "latin",
    "rock en español": "latin", "latin alternative": "latin",
    "dembow": "latin", "perreo": "latin", "latin trap": "latin",
    "corrido": "latin", "norteño": "latin", "banda": "latin",
    "mariachi": "latin", "bolero": "latin", "tango": "latin",
    "tropical": "latin", "vallenato": "latin", "champeta": "latin",
    
    # R&B / Soul
    "r&b": "r_and_b", "soul": "r_and_b", "neo soul": "r_and_b",
    "motown": "r_and_b", "funk": "r_and_b", "quiet storm": "r_and_b",
    "contemporary r&b": "r_and_b", "new jack swing": "r_and_b",
    "urban contemporary": "r_and_b", "alternative r&b": "r_and_b",
    "rhythm and blues": "r_and_b", "doo-wop": "r_and_b",
    
    # Acoustic / Folk
    "acoustic": "acoustic", "folk": "acoustic", "indie folk": "acoustic",
    "singer-songwriter": "acoustic", "country": "country",
    "americana": "country", "bluegrass": "country", "outlaw country": "country",
    "contemporary country": "country", "country rock": "country",
    "alt-country": "country", "bro-country": "country",
    
    # Classical / Jazz
    "classical": "classical", "orchestra": "classical", "opera": "classical",
    "jazz": "jazz", "blues": "jazz", "jazz fusion": "jazz",
    "smooth jazz": "jazz", "bebop": "jazz", "cool jazz": "jazz",
    "contemporary jazz": "jazz", "acid jazz": "jazz",
    "delta blues": "jazz", "chicago blues": "jazz", "electric blues": "jazz",
    
    # Punk variants  
    "punk rock": "rock", "hardcore punk": "rock", "pop punk": "pop",
    "skate punk": "rock", "emo": "rock", "post-punk": "rock",
    
    # Default fallback
    "default": "v_shape"
}

# GTZAN genre to EQ preset mapping (for ML classifier output)
# The GTZAN dataset has 10 genres, we map them to our expanded presets
GTZAN_TO_EQ = {
    "blues": "jazz",
    "classical": "classical",
    "country": "country",
    "disco": "edm",       # Disco is dance music - use EDM preset
    "hiphop": "hip_hop",
    "jazz": "jazz",
    "metal": "metal",
    "pop": "pop",
    "reggae": "latin",
    "rock": "rock"
}


def get_genre_eq_map():
    """Get genre→EQ mapping, preferring JSON config over hardcoded."""
    json_map, _ = load_genre_mappings()
    return json_map if json_map else GENRE_EQ_MAP


def get_gtzan_to_eq():
    """Get GTZAN→EQ mapping, preferring JSON config over hardcoded."""
    _, json_gtzan = load_genre_mappings()
    return json_gtzan if json_gtzan else GTZAN_TO_EQ


class GenreEQMapper:
    """Maps tracks to EQ settings based on genre."""
    
    def __init__(self):
        self.tracks_df = None
        self.genre_encoded_df = None
        self._load_data()
    
    def _load_data(self):
        """Load track datasets."""
        if TRACKS_FILE.exists():
            self.tracks_df = pd.read_csv(TRACKS_FILE)
            print(f"✅ Loaded {len(self.tracks_df)} tracks with clusters")
        
        if GENRE_ENCODED_FILE.exists():
            self.genre_encoded_df = pd.read_csv(GENRE_ENCODED_FILE)
            print(f"✅ Loaded genre-encoded data ({len(self.genre_encoded_df)} tracks)")
    
    def get_track_genres(self, track_id=None, track_name=None, artist=None):
        """
        Get genres for a track by ID, name, or artist.
        Returns list of genre strings.
        """
        if self.tracks_df is None:
            return []
        
        mask = pd.Series([True] * len(self.tracks_df))
        
        if track_id:
            mask &= self.tracks_df["track_id"] == track_id
        if track_name:
            mask &= self.tracks_df["track_name"].str.lower().str.contains(track_name.lower(), na=False, regex=False)
        if artist:
            mask &= self.tracks_df["artist"].str.lower().str.contains(artist.lower(), na=False, regex=False)
        
        matches = self.tracks_df[mask]
        
        if matches.empty:
            return []
        
        # Parse genres from comma-separated string
        genres_str = matches.iloc[0].get("genres", "")
        if pd.isna(genres_str) or not genres_str:
            return []
        
        return [g.strip().lower() for g in str(genres_str).split(",")]
    
    def genres_to_eq(self, genres):
        """
        Map list of genres to EQ settings.
        Returns (preset_name, eq_bands, matched_genre, confidence)
        """
        if not genres:
            return "v_shape", EQ_PRESETS["v_shape"], None, 0.0
        
        # Load mappings (prefers JSON config)
        genre_map = get_genre_eq_map()
        
        # Priority: more specific genres first (exact match)
        for genre in genres:
            genre_clean = genre.strip().lower()
            if genre_clean in genre_map:
                preset_name = genre_map[genre_clean]
                confidence = 1.0  # Exact match
                return preset_name, EQ_PRESETS[preset_name], genre_clean, confidence
        
        # Check for partial matches (lower confidence)
        for genre in genres:
            genre_clean = genre.strip().lower()
            for key, preset_name in genre_map.items():
                if key in genre_clean or genre_clean in key:
                    confidence = 0.75  # Partial match
                    return preset_name, EQ_PRESETS[preset_name], f"{genre_clean}~{key}", confidence
        
        # No match - use default
        return "v_shape", EQ_PRESETS["v_shape"], None, 0.0
    
    def get_eq_for_track(self, track_id=None, track_name=None, artist=None):
        """
        Get recommended EQ for a track.
        
        Returns:
            Dict with track info, genres, preset name, EQ bands, 
            matched_genre (reason), and confidence score
        """
        genres = self.get_track_genres(track_id, track_name, artist)
        preset_name, eq_bands, matched_genre, confidence = self.genres_to_eq(genres)
        
        # Get track info
        track_info = {}
        if self.tracks_df is not None:
            mask = pd.Series([True] * len(self.tracks_df))
            if track_id:
                mask &= self.tracks_df["track_id"] == track_id
            if track_name:
                mask &= self.tracks_df["track_name"].str.lower().str.contains(track_name.lower(), na=False, regex=False)
            if artist:
                mask &= self.tracks_df["artist"].str.lower().str.contains(artist.lower(), na=False, regex=False)
            
            matches = self.tracks_df[mask]
            if not matches.empty:
                row = matches.iloc[0]
                track_info = {
                    "track_id": row.get("track_id"),
                    "track_name": row.get("track_name"),
                    "artist": row.get("artist"),
                    "cluster": row.get("cluster")
                }
        
        return {
            **track_info,
            "genres": genres,
            "preset": preset_name,
            "eq_bands": eq_bands,
            "matched_genre": matched_genre,  # The genre that triggered this EQ
            "confidence": confidence,         # How confident we are (0.0-1.0)
            "source": "database"              # Where the genre came from
        }
    
    def get_eq_from_audio(self, audio_data=None, filepath=None, sr=22050):
        """
        Get EQ recommendation from audio data using ML classifier.
        This works on ANY audio, not just tracks in our database!
        
        Args:
            audio_data: numpy array of audio samples
            filepath: path to audio file
            sr: sample rate
        
        Returns:
            Dict with ML-predicted genre, EQ preset, and confidence
        """
        classifier = get_ml_classifier()
        
        if classifier is None or not classifier.is_trained:
            return {
                "genres": [],
                "preset": "v_shape",
                "eq_bands": EQ_PRESETS["v_shape"],
                "matched_genre": None,
                "confidence": 0.0,
                "source": "fallback",
                "error": "ML classifier not available"
            }
        
        try:
            from .genre_classifier import LiveAudioAnalyzer
            analyzer = LiveAudioAnalyzer(classifier)
            
            result = analyzer.classify_audio(
                audio_data=audio_data, 
                filepath=filepath, 
                sr=sr
            )
            
            if result is None:
                return {
                    "genres": [],
                    "preset": "v_shape",
                    "eq_bands": EQ_PRESETS["v_shape"],
                    "matched_genre": None,
                    "confidence": 0.0,
                    "source": "fallback",
                    "error": "Feature extraction failed"
                }
            
            # Map GTZAN genre to EQ preset
            ml_genre = result['genre']
            preset_name = GTZAN_TO_EQ.get(ml_genre, "v_shape")
            
            return {
                "genres": [ml_genre],
                "preset": preset_name,
                "eq_bands": EQ_PRESETS[preset_name],
                "matched_genre": ml_genre,
                "confidence": result['confidence'],
                "source": "ml_classifier",
                "top_3": result.get('top_3', []),
                "all_probabilities": result.get('all_probabilities', {})
            }
            
        except Exception as e:
            return {
                "genres": [],
                "preset": "v_shape",
                "eq_bands": EQ_PRESETS["v_shape"],
                "matched_genre": None,
                "confidence": 0.0,
                "source": "fallback",
                "error": str(e)
            }
    
    def get_eq_hybrid(self, track_id=None, track_name=None, artist=None, 
                      audio_data=None, filepath=None):
        """
        Hybrid EQ recommendation: database first, ML fallback.
        
        Tries database lookup first (fast, accurate for known tracks).
        Falls back to ML classification if track not found.
        
        Returns:
            Dict with EQ recommendation and source
        """
        # Try database first
        db_result = self.get_eq_for_track(track_id, track_name, artist)
        
        if db_result.get("genres") and db_result.get("confidence", 0) > 0:
            return db_result
        
        # Fallback to ML if we have audio
        if audio_data is not None or filepath is not None:
            ml_result = self.get_eq_from_audio(audio_data=audio_data, filepath=filepath)
            ml_result["fallback_reason"] = "track_not_in_database"
            return ml_result
        
        # No audio available, return default
        return {
            "genres": [],
            "preset": "v_shape",
            "eq_bands": EQ_PRESETS["v_shape"],
            "matched_genre": None,
            "confidence": 0.0,
            "source": "default",
            "fallback_reason": "no_data_available"
        }
    
    def search_tracks(self, query, limit=10):
        """Search tracks by name or artist."""
        if self.tracks_df is None:
            return []
        
        query_lower = query.lower()
        mask = (
            self.tracks_df["track_name"].str.lower().str.contains(query_lower, na=False, regex=False) |
            self.tracks_df["artist"].str.lower().str.contains(query_lower, na=False, regex=False)
        )
        
        matches = self.tracks_df[mask].head(limit)
        return matches.to_dict("records")
    
    def get_cluster_eq(self, cluster_id):
        """Get most common EQ preset for a cluster."""
        if self.tracks_df is None:
            return "v_shape", EQ_PRESETS["v_shape"]
        
        cluster_tracks = self.tracks_df[self.tracks_df["cluster"] == cluster_id]
        
        # Count presets for each track in cluster
        preset_counts = {}
        for _, row in cluster_tracks.iterrows():
            genres = [g.strip().lower() for g in str(row.get("genres", "")).split(",") if g.strip()]
            preset_name, _ = self.genres_to_eq(genres)
            preset_counts[preset_name] = preset_counts.get(preset_name, 0) + 1
        
        if preset_counts:
            best_preset = max(preset_counts, key=preset_counts.get)
            return best_preset, EQ_PRESETS[best_preset]
        
        return "v_shape", EQ_PRESETS["v_shape"]


# ========== DSP OUTPUT INTERFACE ==========

# Equalizer APO config path (Windows)
EQUALIZER_APO_CONFIG_PATH = Path(os.getenv("PROGRAMFILES", "C:\\Program Files")) / "EqualizerAPO" / "config"
ARIA_EQ_FILE = EQUALIZER_APO_CONFIG_PATH / "aria_eq.txt"


def format_eq_for_dsp(eq_bands, dsp_type="generic"):
    """
    Format EQ bands for different DSP interfaces.
    
    Args:
        eq_bands: List of 10 dB values
        dsp_type: "generic", "equalizer_apo", "minidsp", "json"
    
    Returns:
        Formatted string or dict for DSP control
    """
    band_freqs = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    
    if dsp_type == "equalizer_apo":
        # Equalizer APO config format
        lines = ["Preamp: -3 dB"]
        for freq, gain in zip(band_freqs, eq_bands):
            lines.append(f"Filter: ON PK Fc {freq} Hz Gain {gain} dB Q 1.4")
        return "\n".join(lines)
    
    elif dsp_type == "minidsp":
        # MiniDSP-style JSON
        return {
            "bands": [
                {"frequency": freq, "gain": gain, "q": 1.4}
                for freq, gain in zip(band_freqs, eq_bands)
            ]
        }
    
    elif dsp_type == "json":
        return {
            "bands": dict(zip([f"{f}Hz" for f in band_freqs], eq_bands))
        }
    
    else:  # generic
        return " | ".join([f"{f}Hz: {g:+.0f}dB" for f, g in zip(band_freqs, eq_bands)])


def apply_eq_to_apo(eq_bands, preset_name="custom"):
    """
    Apply EQ settings to Equalizer APO in real-time.
    
    Args:
        eq_bands: List of 10 dB values
        preset_name: Name for logging
    
    Returns:
        True if successful, False otherwise
    """
    if not EQUALIZER_APO_CONFIG_PATH.exists():
        print(f"❌ Equalizer APO not found at: {EQUALIZER_APO_CONFIG_PATH}")
        print("   Install from: https://sourceforge.net/projects/equalizerapo/")
        return False
    
    # Generate config content
    config_content = f"""# Aria Audio Intelligence - Auto-generated EQ
# Preset: {preset_name}
# Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

Preamp: -3 dB

"""
    band_freqs = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    for freq, gain in zip(band_freqs, eq_bands):
        config_content += f"Filter: ON PK Fc {freq} Hz Gain {gain:.1f} dB Q 1.4\n"
    
    try:
        # Write to aria_eq.txt
        with open(ARIA_EQ_FILE, 'w') as f:
            f.write(config_content)
        
        # Check if included in main config.txt
        main_config = EQUALIZER_APO_CONFIG_PATH / "config.txt"
        include_line = "Include: aria_eq.txt"
        
        if main_config.exists():
            with open(main_config, 'r') as f:
                content = f.read()
            
            if include_line not in content:
                print(f"⚠️ Add this line to {main_config}:")
                print(f"   {include_line}")
                print(f"   (Or run as admin to auto-add)")
                
                # Try to add it (may need admin)
                try:
                    with open(main_config, 'a') as f:
                        f.write(f"\n{include_line}\n")
                    print(f"✅ Added include to config.txt")
                except PermissionError:
                    pass
        
        print(f"🎛️ EQ applied: {preset_name}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to write EQ config: {e}")
        return False


def get_apo_status():
    """Check if Equalizer APO is installed and configured."""
    status = {
        "installed": EQUALIZER_APO_CONFIG_PATH.exists(),
        "aria_config_exists": ARIA_EQ_FILE.exists() if EQUALIZER_APO_CONFIG_PATH.exists() else False,
        "config_path": str(EQUALIZER_APO_CONFIG_PATH)
    }
    
    if status["installed"]:
        main_config = EQUALIZER_APO_CONFIG_PATH / "config.txt"
        if main_config.exists():
            with open(main_config, 'r') as f:
                status["aria_included"] = "aria_eq.txt" in f.read()
        else:
            status["aria_included"] = False
    
    return status


# ========== CLI TESTING ==========

if __name__ == "__main__":
    print("=" * 60)
    print("  Audio Intelligence - Genre-Based EQ Mapper")
    print("=" * 60)
    
    mapper = GenreEQMapper()
    
    if mapper.tracks_df is None:
        print("\n❌ No track data found!")
        exit(1)
    
    # Test with some tracks from the dataset
    test_queries = [
        ("Don't Stop Believin'", "Journey"),
        ("Sweet Child O' Mine", "Guns N' Roses"),
        ("Brick by Boring Brick", "Paramore"),
        ("Alive", "P.O.D."),
    ]
    
    print("\n" + "-" * 60)
    print("Testing EQ recommendations:")
    print("-" * 60)
    
    for track_name, artist in test_queries:
        result = mapper.get_eq_for_track(track_name=track_name, artist=artist)
        
        if result.get("track_name"):
            print(f"\n🎵 {result['track_name']} - {result['artist']}")
            print(f"   Genres: {', '.join(result['genres']) if result['genres'] else 'Unknown'}")
            print(f"   Cluster: {result.get('cluster', 'N/A')}")
            print(f"   EQ Preset: {result['preset']}")
            print(f"   Bands: {format_eq_for_dsp(result['eq_bands'], 'generic')}")
        else:
            print(f"\n❌ Not found: {track_name} - {artist}")
    
    # Interactive search
    print("\n" + "=" * 60)
    print("Interactive mode - search for tracks (type 'quit' to exit)")
    print("=" * 60)
    
    while True:
        query = input("\n🔍 Search: ").strip()
        if query.lower() in ["quit", "exit", "q"]:
            break
        
        if not query:
            continue
        
        matches = mapper.search_tracks(query, limit=5)
        
        if not matches:
            print("   No matches found.")
            continue
        
        print(f"\n   Found {len(matches)} match(es):")
        for i, m in enumerate(matches, 1):
            genres = m.get("genres", "")[:50]
            print(f"   {i}. {m['track_name']} - {m['artist']} [{genres}]")
        
        # Get EQ for first match
        first = matches[0]
        result = mapper.get_eq_for_track(track_name=first["track_name"], artist=first["artist"])
        print(f"\n   🎛️ EQ for '{first['track_name']}':")
        print(f"      Preset: {result['preset']}")
        print(f"      {format_eq_for_dsp(result['eq_bands'], 'generic')}")

