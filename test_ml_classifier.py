"""Test script for ML genre classifier integration"""
from core.genre_classifier import GenreClassifier
from core.audio_intelligence import GenreEQMapper, GTZAN_TO_EQ, EQ_PRESETS, GENRE_EQ_MAP
import pandas as pd

print("=" * 60)
print("  Audio Intelligence - Full Integration Test")
print("=" * 60)

# Load classifier
clf = GenreClassifier()
print(f"\n✅ Model loaded: {clf.is_trained} | Accuracy: {clf.accuracy:.1%}")

# Load test data
df = pd.read_csv('music_dataset/Data/features_30_sec.csv')
fcols = [c for c in df.columns if c not in ['filename','length','label']]

print("\n" + "-" * 60)
print("Test 1: GTZAN Genre Detection → EQ Mapping")
print("-" * 60)

correct = 0
for genre in ['blues','classical','country','disco','hiphop','jazz','metal','pop','reggae','rock']:
    sample = df[df['label']==genre].iloc[5]
    pred = clf.predict_with_confidence(sample[fcols].values)
    ok = "✅" if pred['genre']==genre else "❌"
    if pred['genre']==genre: correct += 1
    eq_preset = GTZAN_TO_EQ.get(pred['genre'], 'v_shape')
    print(f"{ok} {genre:10} → {pred['genre']:10} ({pred['confidence']:5.1%}) → EQ: {eq_preset}")

print(f"\nAccuracy: {correct}/10 ({correct*10}%)")

# Test new presets
print("\n" + "-" * 60)
print("Test 2: New EQ Presets (phonk, edm, lofi)")
print("-" * 60)

new_presets = ['phonk', 'edm', 'lofi']
for preset in new_presets:
    if preset in EQ_PRESETS:
        bands = EQ_PRESETS[preset]
        print(f"✅ {preset:10} → Bands: {bands[:5]}... (bass heavy: {bands[0] > 4})")
    else:
        print(f"❌ {preset} preset missing!")

# Test genre mappings
print("\n" + "-" * 60)
print("Test 3: Genre → EQ Mappings")
print("-" * 60)

test_genres = [
    ("phonk", "phonk"),
    ("drift phonk", "phonk"),
    ("dubstep", "edm"),
    ("lofi", "lofi"),
    ("chillhop", "lofi"),
    ("hardstyle", "edm"),
    ("trap", "hip_hop"),
    ("thrash metal", "metal"),
]

for genre, expected_eq in test_genres:
    actual_eq = GENRE_EQ_MAP.get(genre, "NOT FOUND")
    ok = "✅" if actual_eq == expected_eq else "❌"
    print(f"{ok} {genre:20} → {actual_eq:15} (expected: {expected_eq})")

# Test EQ Mapper database
print("\n" + "-" * 60)
print("Test 4: Database Lookup (Spotify tracks)")
print("-" * 60)

mapper = GenreEQMapper()

test_tracks = [
    ("Don't Stop Believin'", "Journey"),
    ("Sweet Child O' Mine", "Guns N' Roses"),
    ("Peace Sells", "Megadeth"),
]

for track, artist in test_tracks:
    result = mapper.get_eq_for_track(track_name=track, artist=artist)
    if result.get("track_name"):
        genres_str = ', '.join(result['genres'][:2]) if result['genres'] else 'none'
        print(f"✅ {track[:25]:25} | {genres_str:20} → {result['preset']}")
    else:
        print(f"❌ Not found: {track}")

print("\n" + "=" * 60)
print("✅ All integration tests complete!")
print("=" * 60)
print("\nAvailable presets:", list(EQ_PRESETS.keys()))
