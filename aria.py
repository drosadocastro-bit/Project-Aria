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
import random
import time as time_module
from pathlib import Path

# Optional imports are initialized to avoid "possibly unbound" warnings
web = None
try:
    from aiohttp import web as aiohttp_web
    web = aiohttp_web
except ImportError:
    web = None
nova_text_handler = None
transcribe = None
initialize_tts = None
get_tts_info = None
speak = None
speak_async = None
initialize_stt = None
get_stt_info = None
speak_for_persona_async = None
get_persona_ui_config = None

# Import local modules
from config import *
from core.personality import *
from core.voice import generate_voice, play_audio, cleanup_old_files
from core.obd_integration import obd_monitor
from core.state_manager import create_state_manager, VehicleState
from core.response_validator import create_response_validator

# Import TTS router for persona-aware voice
try:
    from core.tts_router import speak_for_persona_async, get_persona_ui_config
    TTS_ROUTER_AVAILABLE = True
except ImportError:
    TTS_ROUTER_AVAILABLE = False
    print("⚠️ TTS router not available")

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
        from backend import nova_text_handler  # type: ignore
        print("✅ NIC integration enabled")
    except Exception as e:
        print(f"⚠️ NIC import failed: {e}")
        nova_text_handler = None
        NIC_ENABLED = False

# ========== STATE ==========

current_language = DEFAULT_LANGUAGE
current_personality = DEFAULT_PERSONALITY
connected_clients = set()
last_dual_banter_time = 0.0

# Initialize state manager and response validator
import config as config_module
state_manager = create_state_manager(config_module)
response_validator = create_response_validator(config_module)

# ========== NIC QUERY ==========

def query_nic_for_context(user_message):
    """Query NIC for manual information (if enabled)."""
    if not NIC_ENABLED or not nova_text_handler:
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


def chat_with_lm_studio(message, persona_override=None, language_override=None):
    """
    Chat using LM Studio with state-aware response validation.
    
    Args:
        message: User message (already stripped of persona prefix if any)
        persona_override: Optional persona to use for this turn (None = use current_personality)
        language_override: Optional language to use for this turn (None = use current_language)
    """
    
    # Determine which persona and language to use for this turn
    active_persona = persona_override if persona_override else current_personality
    active_language = language_override if language_override else current_language
    
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
    
    # Get system prompt for the active persona - modify for DRIVING state
    system_prompt = get_system_prompt(active_persona, active_language)
    
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
        
        # Validate response based on state (regardless of persona)
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


def get_other_persona(persona: str) -> str:
    return "nova" if persona == "aria" else "aria"


def should_dual_banter(current_state) -> bool:
    global last_dual_banter_time
    if not DUAL_PERSONA_ENABLED:
        return False
    if current_state == VehicleState.DRIVING:
        return False
    now = time_module.time()
    if now - last_dual_banter_time < DUAL_PERSONA_COOLDOWN_SEC:
        return False
    return random.random() < DUAL_PERSONA_CHANCE


def generate_banter_reply(primary_persona: str, other_persona: str, primary_reply: str, language: str):
    banter_prompt = (
        f"Respond to {primary_persona}'s reply in 1–2 sentences. "
        f"Be playful, challenge or question gently, and stay on-topic. "
        f"Don't address the user directly.\n\n"
        f"Reply: {primary_reply}"
    )
    return chat_with_lm_studio(
        banter_prompt,
        persona_override=other_persona,
        language_override=language,
    )

# ========== HTTP SERVER (For STT endpoint and static files) ==========

async def handle_stt_upload(request):
    """Handle /stt POST endpoint for audio transcription."""
    if web is None:
        # Cannot use web.json_response if web is None
        raise RuntimeError('aiohttp not installed')
    
    # web is available
    
    if not offline_stt_enabled:
        return web.json_response({
            'success': False,
            'error': 'Offline STT not enabled. Set OFFLINE_STT_ENABLED=true'
        }, status=503)
    
    try:
        # Parse multipart form data
        reader = await request.multipart()
        
        audio_data = None
        audio_path = None
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
        
        if not audio_data or not audio_path:
            return web.json_response({
                'success': False,
                'error': 'No audio file provided'
            }, status=400)
        
        if not transcribe:
            return web.json_response({
                'success': False,
                'error': 'Offline STT not enabled'
            }, status=503)
        
        # Transcribe using offline STT
        result = transcribe(audio_path, language=language)
        
        # Clean up temp file
        try:
            os.unlink(audio_path)
        except OSError:
            pass
        
        return web.json_response(result)
        
    except Exception as e:
        return web.json_response({
            'success': False,
            'error': str(e)
        }, status=500)


async def handle_static_tts(request):
    """Serve static TTS audio files from static/tts/."""
    if web is None:
        raise RuntimeError('aiohttp not installed')
    
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
    if web is None:
        print("⚠️ aiohttp not installed. HTTP endpoints disabled.")
        print("   Install: pip install aiohttp")
        return None
    
    app = web.Application()
    
    # Add routes
    app.router.add_post('/stt', handle_stt_upload)
    app.router.add_get('/tts/{filename}', handle_static_tts)
    
    # Serve static HTML files (avatar UI)
    async def serve_avatar(request):
        """Serve the nova_avatar.html file."""
        if web is None:
            raise RuntimeError('aiohttp not installed')
        static_dir = Path(__file__).parent / "static"
        file_path = static_dir / "nova_avatar.html"
        if file_path.exists():
            return web.FileResponse(file_path)
        return web.Response(text='Avatar HTML not found', status=404)
    
    async def serve_static_file(request):
        """Serve files from static/ directory."""
        if web is None:
            raise RuntimeError('aiohttp not installed')
        filename = request.match_info.get('filename', '')
        if '..' in filename:
            return web.Response(text='Invalid path', status=400)
        static_dir = Path(__file__).parent / "static"
        file_path = static_dir / filename
        if file_path.exists() and file_path.is_file():
            return web.FileResponse(file_path)
        return web.Response(text='File not found', status=404)
    
    app.router.add_get('/', serve_avatar)
    app.router.add_get('/avatar', serve_avatar)
    app.router.add_get('/static/{filename:.*}', serve_static_file)
    
    # Add health check endpoint
    async def health_check(request):
        if web is None:
            raise RuntimeError('aiohttp not installed')
        status = {
            'status': 'ok',
            'offline_tts_enabled': offline_tts_enabled,
            'offline_stt_enabled': offline_stt_enabled,
            'lm_studio_connected': test_lm_studio_connection(),
            'obd_connected': obd_monitor.connected
        }
        
        if offline_tts_enabled:
            if get_tts_info:
                status['tts_backend'] = get_tts_info()
        if offline_stt_enabled:
            if get_stt_info:
                status['stt_backend'] = get_stt_info()
        
        return web.json_response(status)
    
    app.router.add_get('/health', health_check)
    
    return app

# ========== WEBSOCKET SERVER (For Avatar) ==========

async def handle_websocket(websocket):
    """Handle WebSocket connections from browser avatar."""
    try:
        import websockets
    except ImportError:
        print("❌ websockets not installed. Run: pip install websockets")
        return
    
    global current_personality, current_language
    
    connected_clients.add(websocket)
    print(f"🌟 Avatar connected: {websocket.remote_address}")
    
    # Send greeting
    greeting = get_greeting(current_personality)
    ui_config = get_persona_ui_config(current_personality) if TTS_ROUTER_AVAILABLE and get_persona_ui_config else {}
    
    await websocket.send(json.dumps({
        'type': 'greeting',
        'text': greeting,
        'persona': current_personality,
        'ui': ui_config
    }))
    
    try:
        async for message in websocket:
            data = json.loads(message)
            
            if data['type'] == 'query':
                question = data['text']
                
                # Detect if user is addressing a specific persona for this turn
                target_persona, stripped_question = detect_target_personality(question)
                
                # Detect language for this turn
                turn_language = detect_language(question)
                
                # Determine which persona to use for this response
                # If target_persona is detected, use it for this turn only
                # Otherwise use current_personality
                response_persona = target_persona if target_persona else current_personality
                
                print(f"📝 Query: '{question}' -> Persona: {response_persona}, Lang: {turn_language}")
                if target_persona:
                    print(f"   (Per-turn routing to {target_persona})")
                
                # Send "thinking" status
                await websocket.send(json.dumps({
                    'type': 'thinking',
                    'active': True
                }))
                
                # Get response using the persona for this turn
                reply = chat_with_lm_studio(
                    stripped_question,
                    persona_override=response_persona,
                    language_override=turn_language
                )
                
                # Get UI config for response persona
                ui_config = get_persona_ui_config(response_persona) if TTS_ROUTER_AVAILABLE and get_persona_ui_config else {}
                
                # Send response with persona metadata
                response_message = {
                    'type': 'response',
                    'text': reply,
                    'persona': response_persona,
                    'thinking': False,
                    'ui': ui_config
                }
                
                # Generate voice using TTS router if available
                if TTS_ROUTER_AVAILABLE and speak_for_persona_async:
                    tts_result = await speak_for_persona_async(reply, response_persona, turn_language)
                    if tts_result.get('success'):
                        response_message['voice'] = {
                            'audio_path': tts_result['audio_path'],
                            'backend': tts_result['backend'],
                            'voice_id': tts_result.get('voice_id', ''),
                            'lang': turn_language
                        }
                elif offline_tts_enabled and speak_async:
                    # Fallback to offline TTS
                    tts_result = await speak_async(reply)
                    if tts_result.get('success'):
                        audio_path = Path(tts_result['audio_path'])
                        response_message['voice'] = {
                            'audio_path': f'/tts/{audio_path.name}',
                            'backend': tts_result.get('backend', 'offline'),
                            'voice_id': '',
                            'lang': turn_language
                        }
                else:
                    # Use ElevenLabs if configured
                    audio_path = generate_voice(reply)
                    if audio_path:
                        play_audio(audio_path)
                
                await websocket.send(json.dumps(response_message))

                # Optional dual-persona banter
                car_status = obd_monitor.get_live_data()
                current_state = state_manager.get_current_state(car_status)
                if should_dual_banter(current_state):
                    other_persona = get_other_persona(response_persona)
                    banter_reply = generate_banter_reply(
                        response_persona,
                        other_persona,
                        reply,
                        turn_language,
                    )
                    if banter_reply:
                        global last_dual_banter_time
                        last_dual_banter_time = time_module.time()
                        banter_ui = get_persona_ui_config(other_persona) if TTS_ROUTER_AVAILABLE and get_persona_ui_config else {}
                        banter_message = {
                            'type': 'response',
                            'text': banter_reply,
                            'persona': other_persona,
                            'thinking': False,
                            'ui': banter_ui
                        }

                        if TTS_ROUTER_AVAILABLE and speak_for_persona_async:
                            tts_result = await speak_for_persona_async(banter_reply, other_persona, turn_language)
                            if tts_result.get('success'):
                                banter_message['voice'] = {
                                    'audio_path': tts_result['audio_path'],
                                    'backend': tts_result['backend'],
                                    'voice_id': tts_result.get('voice_id', ''),
                                    'lang': turn_language
                                }
                        elif offline_tts_enabled and speak_async:
                            tts_result = await speak_async(banter_reply)
                            if tts_result.get('success'):
                                audio_path = Path(tts_result['audio_path'])
                                banter_message['voice'] = {
                                    'audio_path': f'/tts/{audio_path.name}',
                                    'backend': tts_result.get('backend', 'offline'),
                                    'voice_id': '',
                                    'lang': turn_language
                                }
                        else:
                            audio_path = generate_voice(banter_reply)
                            if audio_path:
                                play_audio(audio_path)

                        await websocket.send(json.dumps(banter_message))
                cleanup_old_files()
            
            elif data['type'] == 'command':
                # Handle explicit personality switch commands
                if data.get('command') == 'set_personality':
                    new_personality = data.get('value')
                    if normalize_persona(new_personality):
                        current_personality = new_personality
                        print(f"🔄 Personality switched to: {current_personality}")
                
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
            if get_tts_info:
                info = get_tts_info()
                print(f"✅ Offline TTS initialized: {info['backend']}")
            else:
                print("✅ Offline TTS initialized")
        else:
            print("⚠️ Offline TTS initialization failed")
    
    if offline_stt_enabled:
        from core.offline_stt import initialize_stt
        if initialize_stt():
            if get_stt_info:
                info = get_stt_info()
                print(f"✅ Offline STT initialized: {info['backend']}")
            else:
                print("✅ Offline STT initialized")
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
    print(f"💜 Open static/nova_avatar.html in your browser!")
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
    print("\nCommands: /es, /en, /nova, /aria, /status, /state, /setstate [STATE], /clearstate, exit\n")
    
    # Greeting
    greeting = get_greeting(current_personality)
    print(f"💜 {persona['name']}: {greeting}\n")
    
    # Initialize offline TTS if enabled
    if offline_tts_enabled:
        from core.offline_tts import initialize_tts
        if initialize_tts():
            if speak:
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
            elif user_input.lower() == "/nova":
                current_personality = "nova"
                print("💜 Switched to Nova personality\n")
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
                if offline_tts_enabled and speak:
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

            # Detect per-turn persona addressing and language
            target_persona, stripped_input = detect_target_personality(user_input)
            turn_language = detect_language(user_input)
            
            # Determine which persona to use for this response
            response_persona = target_persona if target_persona else current_personality
            
            if target_persona:
                print(f"   (Routing to {target_persona} for this turn)")
            
            # Get response
            reply = chat_with_lm_studio(
                stripped_input,
                persona_override=response_persona,
                language_override=turn_language
            )
            
            # Print response
            persona_name = PERSONALITIES[response_persona]['name']
            print(f"\n💜 {persona_name}: {reply}\n")

            # Optional dual-persona banter in console mode
            status = obd_monitor.get_live_data()
            current_state = state_manager.get_current_state(status)
            if should_dual_banter(current_state):
                other_persona = get_other_persona(response_persona)
                banter_reply = generate_banter_reply(
                    response_persona,
                    other_persona,
                    reply,
                    turn_language,
                )
                if banter_reply:
                    global last_dual_banter_time
                    last_dual_banter_time = time_module.time()
                    other_name = PERSONALITIES[other_persona]['name']
                    print(f"💬 {other_name}: {banter_reply}\n")
            
            # Generate voice (offline or ElevenLabs)
            if offline_tts_enabled and speak:
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
    parser.add_argument('--personality', choices=['aria', 'nova'], default='nova',
                       help='Choose personality')
    parser.add_argument('--language', choices=['en', 'es'], default='en',
                       help='Choose language')
    
    args = parser.parse_args()
    
    current_personality = args.personality
    current_language = args.language
    
    print("=" * 60)
    print("  ARIA/Nova - GTI AI Copilot")
    print("=" * 60)
    
    if args.mode == 'console':
        console_mode()
    else:
        # Avatar mode with WebSocket
        print("🌟 Starting in Avatar Mode...")
        asyncio.run(start_websocket_server())
