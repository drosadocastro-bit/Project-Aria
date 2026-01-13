"""
ARIA/JOI - GTI AI Copilot (Windows Edition)
Integrates: LM Studio, ElevenLabs, OBD-II, NIC (optional)
Supports: Offline TTS/STT (Coqui, pyttsx3, whisper.cpp)
"""

import requests
import json
import asyncio
import sys
import os
from pathlib import Path

# Import local modules
from config import *
from core.personality import *
from core.voice import generate_voice, play_audio, cleanup_old_files
from core.obd_integration import obd_monitor
from core.state_manager import create_state_manager, VehicleState
from core.response_validator import create_response_validator

# Import offline TTS/STT if enabled
offline_tts_enabled = os.getenv("OFFLINE_TTS_ENABLED", "").lower() in ("true", "1", "yes")
offline_stt_enabled = os.getenv("OFFLINE_STT_ENABLED", "").lower() in ("true", "1", "yes")

if offline_tts_enabled:
    try:
        from core.offline_tts import speak, speak_async, initialize_tts, get_backend_info as get_tts_info
        print("🎙️ Offline TTS enabled")
    except ImportError as e:
        print(f"⚠️ Offline TTS import failed: {e}")
        offline_tts_enabled = False

if offline_stt_enabled:
    try:
        from core.offline_stt import transcribe, initialize_stt, get_backend_info as get_stt_info
        print("🎤 Offline STT enabled")
    except ImportError as e:
        print(f"⚠️ Offline STT import failed: {e}")
        offline_stt_enabled = False

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

# ========== HTTP SERVER (For STT endpoint and static files) ==========

async def handle_stt_upload(request):
    """Handle /stt POST endpoint for audio transcription."""
    try:
        from aiohttp import web
    except ImportError:
        return web.Response(text='{"error": "aiohttp not installed"}', status=500)
    
    if not offline_stt_enabled:
        return web.json_response({
            'success': False,
            'error': 'Offline STT not enabled. Set OFFLINE_STT_ENABLED=true'
        }, status=503)
    
    try:
        # Parse multipart form data
        reader = await request.multipart()
        
        audio_data = None
        language = "en"
        
        async for field in reader:
            if field.name == 'audio':
                # Save uploaded file to temp location
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    audio_data = await field.read()
                    tmp.write(audio_data)
                    audio_path = tmp.name
            elif field.name == 'language':
                language = (await field.read()).decode('utf-8')
        
        if not audio_data:
            return web.json_response({
                'success': False,
                'error': 'No audio file provided'
            }, status=400)
        
        # Transcribe using offline STT
        result = transcribe(audio_path, language=language)
        
        # Clean up temp file
        import os
        try:
            os.unlink(audio_path)
        except:
            pass
        
        return web.json_response(result)
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_static_tts(request):
    """Serve static TTS audio files from static/tts/."""
    try:
        from aiohttp import web
    except ImportError:
        return web.Response(text='aiohttp not installed', status=500)
    
    filename = request.match_info.get('filename', '')
    
    # Sanitize filename to prevent directory traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return web.Response(text='Invalid filename', status=400)
    
    static_dir = Path(__file__).parent / "static" / "tts"
    file_path = static_dir / filename
    
    if not file_path.exists():
        return web.Response(text='File not found', status=404)
    
    return web.FileResponse(file_path)


async def create_http_server():
    """Create HTTP server for STT endpoint and static files."""
    try:
        from aiohttp import web
    except ImportError:
        print("⚠️ aiohttp not installed. HTTP endpoints disabled.")
        print("   Install: pip install aiohttp")
        return None
    
    app = web.Application()
    
    # Add routes
    app.router.add_post('/stt', handle_stt_upload)
    app.router.add_get('/tts/{filename}', handle_static_tts)
    
    # Add health check endpoint
    async def health_check(request):
        status = {
            'status': 'ok',
            'offline_tts_enabled': offline_tts_enabled,
            'offline_stt_enabled': offline_stt_enabled,
            'lm_studio_connected': test_lm_studio_connection(),
            'obd_connected': obd_monitor.connected
        }
        
        if offline_tts_enabled:
            status['tts_backend'] = get_tts_info()
        if offline_stt_enabled:
            status['stt_backend'] = get_stt_info()
        
        return web.json_response(status)
    
    app.router.add_get('/health', health_check)
    
    return app

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
                
                # Generate voice (offline TTS if enabled, otherwise ElevenLabs)
                if offline_tts_enabled:
                    tts_result = await speak_async(reply)
                    if tts_result.get('success'):
                        audio_path = Path(tts_result['audio_path'])
                        # Send audio file path for browser to fetch
                        await websocket.send(json.dumps({
                            'type': 'audio',
                            'path': f'/tts/{audio_path.name}'
                        }))
                else:
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
    """Start WebSocket and HTTP servers."""
    try:
        import websockets
    except ImportError:
        print("❌ websockets not installed. Run: pip install websockets")
        return
    
    # Initialize offline TTS/STT if enabled
    if offline_tts_enabled:
        from core.offline_tts import initialize_tts
        if initialize_tts():
            info = get_tts_info()
            print(f"✅ Offline TTS initialized: {info['backend']}")
        else:
            print("⚠️ Offline TTS initialization failed")
    
    if offline_stt_enabled:
        from core.offline_stt import initialize_stt
        if initialize_stt():
            info = get_stt_info()
            print(f"✅ Offline STT initialized: {info['backend']}")
        else:
            print("⚠️ Offline STT initialization failed")
    
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
    
    # Start HTTP server (for STT endpoint and static files)
    http_app = await create_http_server()
    if http_app:
        from aiohttp import web
        http_runner = web.AppRunner(http_app)
        await http_runner.setup()
        http_port = WEBSOCKET_PORT + 1  # Use next port for HTTP
        http_site = web.TCPSite(http_runner, WEBSOCKET_HOST, http_port)
        await http_site.start()
        print(f"📡 HTTP server started on http://{WEBSOCKET_HOST}:{http_port}")
        print(f"   Endpoints: /stt (POST), /tts/<file> (GET), /health (GET)")
    
    # Start WebSocket server
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
    print(f"   OBD: {'Connected' if obd_monitor.connected else 'Not Connected'}")
    print(f"   Offline TTS: {'Enabled' if offline_tts_enabled else 'Disabled'}")
    print(f"   Offline STT: {'Enabled' if offline_stt_enabled else 'Disabled'}\n")
    
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
    
    # Initialize offline TTS if enabled
    if offline_tts_enabled:
        from core.offline_tts import initialize_tts
        if initialize_tts():
            result = speak(greeting)
            if result.get('success'):
                print(f"   (TTS: {result['backend']})")
    elif USE_ELEVENLABS:
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
                
                # Generate goodbye voice
                if offline_tts_enabled:
                    from core.offline_tts import speak
                    result = speak(goodbye)
                    if result.get('success'):
                        import time
                        time.sleep(3)
                elif USE_ELEVENLABS:
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
            
            # Generate voice (offline or ElevenLabs)
            if offline_tts_enabled:
                from core.offline_tts import speak
                result = speak(reply)
                if result.get('success'):
                    # In console mode, audio is generated but not played
                    # User can manually play from static/tts/ if desired
                    pass
            elif USE_ELEVENLABS:
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
