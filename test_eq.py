"""
Aria Audio EQ Tester - Test Equalizer APO integration
Run this to test EQ presets in real-time
"""

import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from core.audio_intelligence import (
    GenreEQMapper, 
    EQ_PRESETS, 
    apply_eq_to_apo, 
    get_apo_status,
    format_eq_for_dsp
)


def main():
    print("=" * 60)
    print("  Aria Audio EQ Tester - Equalizer APO")
    print("=" * 60)
    
    # Check APO status
    status = get_apo_status()
    
    print(f"\n📁 Config path: {status['config_path']}")
    print(f"   Installed: {'✅' if status['installed'] else '❌'}")
    
    if not status["installed"]:
        print("\n⚠️ Equalizer APO not installed!")
        print("   Download from: https://sourceforge.net/projects/equalizerapo/")
        print("   After installing, run the Configurator to enable it on your audio device.")
        return
    
    print(f"   Aria config exists: {'✅' if status.get('aria_config_exists') else '❌'}")
    print(f"   Aria included in main: {'✅' if status.get('aria_included') else '❌'}")
    
    # Load mapper
    mapper = GenreEQMapper()
    
    print("\n" + "-" * 60)
    print("Available EQ Presets:")
    print("-" * 60)
    
    presets = list(EQ_PRESETS.keys())
    for i, name in enumerate(presets, 1):
        print(f"  {i:2}. {name}")
    
    print("\n" + "-" * 60)
    print("Commands:")
    print("  [number]  - Apply preset by number")
    print("  [name]    - Apply preset by name (rock, metal, etc.)")
    print("  search    - Search tracks and apply their EQ")
    print("  flat      - Reset to flat EQ")
    print("  quit      - Exit")
    print("-" * 60)
    
    while True:
        try:
            cmd = input("\n🎛️ EQ> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
        
        if cmd in ["quit", "exit", "q"]:
            # Reset to flat before exiting
            apply_eq_to_apo(EQ_PRESETS["flat"], "flat")
            print("👋 Reset to flat EQ. Goodbye!")
            break
        
        if cmd == "search":
            query = input("   Search track: ").strip()
            if query:
                matches = mapper.search_tracks(query, limit=5)
                if matches:
                    print(f"\n   Found {len(matches)} match(es):")
                    for i, m in enumerate(matches, 1):
                        print(f"   {i}. {m['track_name']} - {m['artist']}")
                    
                    # Apply EQ for first match
                    first = matches[0]
                    result = mapper.get_eq_for_track(
                        track_name=first["track_name"], 
                        artist=first["artist"]
                    )
                    print(f"\n   Applying EQ for: {first['track_name']}")
                    print(f"   Genres: {', '.join(result['genres'])}")
                    print(f"   Preset: {result['preset']}")
                    apply_eq_to_apo(result["eq_bands"], result["preset"])
                else:
                    print("   No matches found.")
            continue
        
        # Try as number
        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(presets):
                preset_name = presets[idx]
                eq_bands = EQ_PRESETS[preset_name]
                apply_eq_to_apo(eq_bands, preset_name)
                print(f"   {format_eq_for_dsp(eq_bands, 'generic')}")
            else:
                print(f"   Invalid number. Use 1-{len(presets)}")
            continue
        
        # Try as preset name
        if cmd in EQ_PRESETS:
            eq_bands = EQ_PRESETS[cmd]
            apply_eq_to_apo(eq_bands, cmd)
            print(f"   {format_eq_for_dsp(eq_bands, 'generic')}")
            continue
        
        # Try as artist/track search
        matches = mapper.search_tracks(cmd, limit=1)
        if matches:
            m = matches[0]
            result = mapper.get_eq_for_track(track_name=m["track_name"], artist=m["artist"])
            print(f"   Found: {m['track_name']} - {m['artist']}")
            print(f"   Preset: {result['preset']}")
            apply_eq_to_apo(result["eq_bands"], result["preset"])
        else:
            print(f"   Unknown command or no track found: {cmd}")


if __name__ == "__main__":
    main()
