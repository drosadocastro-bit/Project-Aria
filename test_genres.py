"""Quick test of the genre mapping"""
from core.audio_intelligence import GENRE_EQ_MAP

print(f"Total genres mapped: {len(GENRE_EQ_MAP)}")
print()

# Test some specific genres
test_genres = [
    'barbadian pop',     # Rihanna
    'dance pop',         # Rihanna
    'pop',               # Generic
    'dreamwave',         # Navjaxx
    'synthwave',         # Electronic
    'urbano latino',     # Latin
    'trap soul',         # Hip hop
    'uk drill',          # Hip hop
    'hyperpop',          # Pop
]

print("=== Direct Matches ===")
for g in test_genres:
    result = GENRE_EQ_MAP.get(g, "NO MATCH")
    print(f"  {g} → {result}")

print()
print("=== Checking substring match logic ===")
# Simulate the auto_eq matching
def test_match(genres):
    for genre in genres:
        genre_lower = genre.lower().strip()
        if genre_lower in GENRE_EQ_MAP:
            return GENRE_EQ_MAP[genre_lower], genre_lower, 1.0
    
    for genre in genres:
        genre_lower = genre.lower().strip()
        for key, preset in GENRE_EQ_MAP.items():
            if key in genre_lower or genre_lower in key:
                return preset, f"{genre_lower}~{key}", 0.85
    
    for genre in genres:
        words = genre.lower().split()
        for word in words:
            if word in GENRE_EQ_MAP:
                return GENRE_EQ_MAP[word], f"{genre}→{word}", 0.70
    
    return "v_shape", None, 0.0

# Simulate Rihanna's artist genres from Spotify
rihanna_genres = ['barbadian pop', 'dance pop', 'pop', 'r&b', 'urban contemporary']
navjaxx_genres = ['dreamwave', 'chillwave', 'synthwave']  # hypothetical

print(f"Rihanna genres: {rihanna_genres}")
preset, match, conf = test_match(rihanna_genres)
print(f"  Result: {preset} (matched: {match}, confidence: {conf})")

print()
print(f"Navjaxx genres: {navjaxx_genres}")
preset, match, conf = test_match(navjaxx_genres)
print(f"  Result: {preset} (matched: {match}, confidence: {conf})")
