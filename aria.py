"""
ARIA/JOI - GTI AI Copilot (Windows Edition)
Integrates: LM Studio, ElevenLabs, OBD-II, NIC (optional)
"""

import requests
import json
import asyncio
import sys
from pathlib import Path

# Import local modules
from config import *
from core.personality import *
from core.voice import generate_voice, play_audio, cleanup_old_files
from core.obd_integration import obd_monitor
from core.state_manager import create_state_manager, VehicleState
from core.response_validator import create_response_validator

# ========== NIC INTEGRATION (Optional) ==========

if NIC_ENABLED:
    sys.path.append(NIC_PATH)
    try:
        from backend import nova_text_handler
        print("✅ NIC integration enabled")
    except Exception as e:
        print(f"⚠️ NIC import failed: {e}")
        NIC_ENABLED = False

# ========== STATE ==========

current_language = DEFAULT_LANGUAGE
current_personality = DEFAULT_PERSONALITY
connected_clients = set()

# Initialize state manager and response validator
import config as config_module
state_manager = create_state_manager(config_module)
response_validator = create_response_validator(config_module)

# ========== NIC QUERY ==========

def query_nic_for_context(user_message):
    """Query NIC for manual information (if enabled)."""
    if not NIC_ENABLED:
        return None
    
    try:
        # Check if question is car-related
        car_keywords = ['torque', 'pressure', 'code', 'error', 'diagnostic',
                       'replace', 'install', 'repair', 'manual', 'procedure',
                       'spec', 'specification', 'how to', 'what is']
        
        is_car_question = any(kw in user_message.lower() for kw in car_keywords)
        
        if is_car_question:
            print("🔍 Querying NIC manuals...")
            answer, metadata = nova_text_handler(user_message, mode="Auto")
            
            sources = metadata.get('sources', [])
            citations = "\n".join([
                f"- {s.get('source', 'Manual')}, Page {s.get('page', 'N/A')}"
                for s in sources[:3]
            ])
            
            context = f"""[Manual Reference Found]:
{answer}

Sources:
{citations}

Use this information to answer accurately."""
            return context
        
    except Exception as e:
        print(f"⚠️ NIC error: {e}")
    
    return None

# ========== LLM (LM Studio) ==========

def test_lm_studio_connection():
    """Test if LM Studio is running and accessible."""
    try:
        test_url = LM_STUDIO_API.replace("/v1/chat/completions", "/v1/models")
        response = requests.get(test_url, timeout=2)
        if response.status_code == 200:
            return True
        return False
    except:
        return False


def chat_with_lm_studio(message):
    """Chat using LM Studio with state-aware response validation."""
    
    # Get current vehicle state
    car_status = obd_monitor.get_live_data()
    current_state = state_manager.get_current_state(car_status)
    
    # Get NIC context if relevant
    nic_context = query_nic_for_context(message)
    
    # Get car status formatting
    car_context = obd_monitor.format_status(car_status) if car_status else ""
    
    # Add state context to car status
    if car_context:
        car_context = f"[Vehicle State: {current_state.value}]\n{car_context}"
    else:
        car_context = f"[Vehicle State: {current_state.value}]"
    
    # Build enhanced message
    enhanced_message = message
    if nic_context:
        enhanced_message = f"{nic_context}\n\nUser Question: {message}"
    if car_context:
        enhanced_message = f"{car_context}\n\n{enhanced_message}"
    
    # Get system prompt - modify for DRIVING state
    system_prompt = get_system_prompt(current_personality, current_language)
    
    # Add DRIVING mode instructions if needed
    if current_state == VehicleState.DRIVING:
        driving_instructions = """
CRITICAL: Vehicle is in DRIVING mode. Your responses MUST be:
- Maximum 150 characters
- Format: [Metric/State] → [Interpretation] → [Action]
- No questions, no emotional language, no humor
- Essential information only
- If question is non-essential, respond with "Monitoring."
"""
        system_prompt = f"{system_prompt}\n\n{driving_instructions}"
    
    # Prepare payload (LM Studio format)
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": enhanced_message}
        ],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 512 if current_state != VehicleState.DRIVING else 100,  # Limit tokens in DRIVING
        "stream": False,
        "model": LM_STUDIO_MODEL
    }
    
    try:
        response = requests.post(LM_STUDIO_API, json=payload, timeout=30)
        response.raise_for_status()
        reply = response.json()['choices'][0]['message']['content']
        reply = reply.strip()
        
        # Validate response based on state
        is_valid, sanitized_reply, violation = response_validator.validate_response(
            reply, current_state
        )
        
        if not is_valid and current_state == VehicleState.DRIVING:
            # Response violated DRIVING constraints - use sanitized version
            print(f"⚠️ DRIVING mode violation: {violation}")
            print(f"   Original: {reply[:100]}...")
            print(f"   Sanitized: {sanitized_reply}")
            return sanitized_reply
        
        return reply
        
    except requests.exceptions.RequestException as e:
        print(f"❌ LM Studio error: {e}")
        
        # Return state-appropriate error message
        if current_state == VehicleState.DRIVING:
            return "Monitoring."
        return "I'm having trouble thinking right now. Is LM Studio running?"
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
        if current_state == VehicleState.DRIVING:
            return "Monitoring."
        return "Something went wrong. Let me try again."

# ========== WEBSOCKET SERVER (For Avatar) ==========

async def handle_websocket(websocket, path):
    """Handle WebSocket connections from browser avatar."""
    try:
        import websockets
    except ImportError:
        print("❌ websockets not installed. Run: pip install websockets")
        return
    
    connected_clients.add(websocket)
    print(f"🌟 Avatar connected: {websocket.remote_address}")
    
    # Send greeting
    greeting = get_greeting(current_personality)
    await websocket.send(json.dumps({
        'type': 'greeting',
        'text': greeting
    }))
    
    try:
        async for message in websocket:
            data = json.loads(message)
            
            if data['type'] == 'query':
                question = data['text']
                
                # Send "thinking" status
                await websocket.send(json.dumps({
                    'type': 'thinking',
                    'active': True
                }))
                
                # Get response
                reply = chat_with_lm_studio(question)
                
                # Send response
                await websocket.send(json.dumps({
                    'type': 'response',
                    'text': reply,
                    'thinking': False
                }))
                
                # Generate voice
                audio_path = generate_voice(reply)
                if audio_path:
                    play_audio(audio_path)
                
                cleanup_old_files()
                
    except Exception as e:
        print(f"❌ Avatar disconnected: {e}")
    finally:
        connected_clients.discard(websocket)


async def broadcast_car_status():
    """Broadcast car status to all connected avatars."""
    try:
        import websockets
    except ImportError:
        return
    
    while True:
        await asyncio.sleep(2)  # Update every 2 seconds
        
        status = obd_monitor.get_live_data()
        if status and connected_clients:
            message = json.dumps({
                'type': 'car_status',
                'data': status
            })
            
            websockets.broadcast(connected_clients, message)


async def start_websocket_server():
    """Start WebSocket server."""
    try:
        import websockets
    except ImportError:
        print("❌ websockets not installed. Run: pip install websockets")
        return
    
    # Test LM Studio connection
    print("🔍 Checking LM Studio connection...")
    if not test_lm_studio_connection():
        print("❌ Cannot connect to LM Studio!")
        print(f"   Expected at: {LM_STUDIO_API}")
        print("\nPlease:")
        print("1. Start LM Studio")
        print("2. Load model: google/gemma-3n-e4b")
        print("3. Enable Local Server in LM Studio settings")
        input("\nPress Enter when ready...")
        
        # Try again
        if not test_lm_studio_connection():
            print("❌ Still cannot connect. Exiting.")
            sys.exit(1)

    print("✅ LM Studio connected")
    print(f"   Model: {LM_STUDIO_MODEL}\n")
    
    server = await websockets.serve(
        handle_websocket,
        WEBSOCKET_HOST,
        WEBSOCKET_PORT
    )
    
    print(f"🌐 WebSocket server started on ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
    print(f"💜 Open joi_avatar.html in your browser!")
    print(f"\n   Personality: {PERSONALITIES[current_personality]['name']}")
    print(f"   Language: {current_language}")
    print(f"   NIC: {'Enabled' if NIC_ENABLED else 'Disabled'}")
    print(f"   OBD: {'Connected' if obd_monitor.connected else 'Not Connected'}\n")
    
    # Start car status broadcasting
    asyncio.create_task(broadcast_car_status())
    
    await asyncio.Future()  # Run forever

# ========== CONSOLE MODE ==========

def console_mode():
    """Original console chat mode."""
    global current_language, current_personality
    
    # Test LM Studio connection
    print("🔍 Checking LM Studio connection...")
    if not test_lm_studio_connection():
        print("❌ Cannot connect to LM Studio!")
        print(f"   Expected at: {LM_STUDIO_API}")
        print("\nPlease:")
        print("1. Start LM Studio")
        print("2. Load model: google/gemma-3n-e4b")
        print("3. Enable Local Server in LM Studio settings")
        input("\nPress Enter when ready...")
        
        # Try again
        if not test_lm_studio_connection():
            print("❌ Still cannot connect. Exiting.")
            sys.exit(1)

    print("✅ LM Studio connected")
    print(f"   Model: {LM_STUDIO_MODEL}\n")
    
    persona = PERSONALITIES[current_personality]
    print(f"\n💜 {persona['name']} - {persona['description']}")
    print(f"   Language: {current_language.upper()}")
    print(f"   NIC: {'Enabled' if NIC_ENABLED else 'Disabled'}")
    print(f"   OBD: {'Connected' if obd_monitor.connected else 'Not Connected'}")
    print("\nCommands: /es, /en, /joi, /aria, /status, /state, /setstate [STATE], /clearstate, exit\n")
    
    # Greeting
    greeting = get_greeting(current_personality)
    print(f"💜 {persona['name']}: {greeting}\n")
    if USE_ELEVENLABS:
        audio = generate_voice(greeting)
        if audio:
            play_audio(audio)
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            # Commands
            if user_input.lower() == "/es":
                current_language = "es"
                print("🔄 Cambiado a Español\n")
                continue
            elif user_input.lower() == "/en":
                current_language = "en"
                print("🔄 Switched to English\n")
                continue
            elif user_input.lower() == "/joi":
                current_personality = "joi"
                print("💜 Switched to JOI personality\n")
                continue
            elif user_input.lower() == "/aria":
                current_personality = "aria"
                print("🚗 Switched to Aria personality\n")
                continue
            elif user_input.lower() == "/status":
                status = obd_monitor.get_live_data()
                if status:
                    print(obd_monitor.format_status(status) + "\n")
                else:
                    print("❌ OBD not connected\n")
                continue
            elif user_input.lower() == "/state":
                status = obd_monitor.get_live_data()
                current_state = state_manager.get_current_state(status)
                state_info = state_manager.get_state_info(status)
                print(f"\n🚦 Vehicle State: {current_state.value}")
                print(f"   Time in state: {state_info['time_in_state']:.1f}s")
                print(f"   Manual override: {state_info['manual_override']}")
                print(f"   Telemetry: {'Available' if state_info['telemetry_available'] else 'Not available'}\n")
                continue
            elif user_input.lower().startswith("/setstate "):
                # Manual state override: /setstate PARKED, /setstate GARAGE, /setstate DRIVING
                parts = user_input.split()
                if len(parts) == 2:
                    try:
                        state_manager.set_manual_override(parts[1])
                        print(f"🔧 Manual override set to: {parts[1].upper()}\n")
                    except ValueError as e:
                        print(f"❌ {e}\n")
                else:
                    print("Usage: /setstate PARKED|GARAGE|DRIVING\n")
                continue
            elif user_input.lower() == "/clearstate":
                state_manager.set_manual_override(None)
                print("🔓 Manual override cleared\n")
                continue
            elif user_input.lower() in ["exit", "quit"]:
                goodbye = get_goodbye(current_personality)
                print(f"\n💜 {PERSONALITIES[current_personality]['name']}: {goodbye}\n")
                if USE_ELEVENLABS:
                    audio = generate_voice(goodbye)
                    if audio:
                        play_audio(audio)
                        import time
                        time.sleep(3)  # Wait for audio to finish
                break

            # Get response
            reply = chat_with_lm_studio(user_input)
            
            # Print response
            persona_name = PERSONALITIES[current_personality]['name']
            print(f"\n💜 {persona_name}: {reply}\n")
            
            # Generate voice
            if USE_ELEVENLABS:
                audio_path = generate_voice(reply)
                if audio_path:
                    play_audio(audio_path)
            
            cleanup_old_files()

        except KeyboardInterrupt:
            print("\n👋 Session ended.\n")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}\n")

# ========== MAIN ==========

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ARIA/JOI - GTI AI Copilot")
    parser.add_argument('--mode', choices=['console', 'avatar'], default='console',
                       help='Run in console or avatar mode')
    parser.add_argument('--personality', choices=['aria', 'joi'], default='joi',
                       help='Choose personality')
    parser.add_argument('--language', choices=['en', 'es'], default='en',
                       help='Choose language')
    
    args = parser.parse_args()
    
    current_personality = args.personality
    current_language = args.language
    
    print("=" * 60)
    print("  ARIA/JOI - GTI AI Copilot")
    print("=" * 60)
    
    if args.mode == 'console':
        console_mode()
    else:
        # Avatar mode with WebSocket
        print("🌟 Starting in Avatar Mode...")
        asyncio.run(start_websocket_server())
