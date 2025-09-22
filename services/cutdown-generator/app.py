import os
from flask import Flask, request, render_template, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
import requests
import logging
import traceback
import io
import json
from pathlib import Path
import uuid
import time
from pydantic import BaseModel
from fastapi import HTTPException

# Logging konfigurieren
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Konfiguration
UPLOAD_FOLDER = '/app/videos/uploads'
CUTDOWN_FOLDER = '/app/videos/cutdowns'
TEMP_FOLDER = '/app/temp'
REVOICED_FOLDER = '/app/videos/revoiced'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB max file size

# ElevenLabs Configuration
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', 'your-api-key-here')
ELEVENLABS_BASE_URL = 'https://api.elevenlabs.io/v1'

# Umgebungsbasierte Konfiguration
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
ENV = os.environ.get('FLASK_ENV', 'production')

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    CUTDOWN_FOLDER=CUTDOWN_FOLDER,
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    DEBUG=DEBUG,
    ENV=ENV
)

# Stelle sicher, dass die Verzeichnisse existieren
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CUTDOWN_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(REVOICED_FOLDER, exist_ok=True)

# Speichere den Status der Cutdown-Generierung
cutdown_status = {}

class AudioUrlRequest(BaseModel):
    audio_url: str

class AsrUrlRequest(BaseModel):
    audio_url: str
    language_code: str = None

@app.errorhandler(Exception)
def handle_error(error):
    logger.exception("An error occurred")
    # Check if it's a webhook error
    if isinstance(error, requests.exceptions.RequestException):
        # Only handle errors from the main webhook URL
        if hasattr(error, 'response') and error.response is not None:
            if '/webhook/video' in error.response.url and '/metadata' not in error.response.url:
                return jsonify({
                    'message': 'File successfully uploaded',
                    'webhook_status': 'failed',
                    'webhook_error': str(error)
                }), 200
    # For other errors, return 500
    return jsonify({
        'error': 'Internal Server Error',
        'details': str(error),
        'traceback': traceback.format_exc() if app.debug else None
    }), 500

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check-status', methods=['POST', 'OPTIONS'])
def check_status():
    """Proxy-Route für den n8n Webhook Status-Check"""
    if request.method == 'OPTIONS':
        # Handle CORS preflight
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    try:
        # Die video_id aus dem Request-Body nehmen
        data = request.get_json()
        video_id = data.get('video_id') if data else None
        
        if not video_id:
            return jsonify({
                'error': 'video_id missing in request body'
            }), 400
        
        webhook_url = f"http://n8n:5678/webhook/check-status"
        logger.debug(f"Call n8n webhook: {webhook_url} with video_id: {video_id}")
        
        # Füge Timeout und Retry-Logik hinzu
        for attempt in range(3):  # 3 Versuche
            try:
                # Die video_id wird jetzt im Body übergeben
                response = requests.post(webhook_url, json={"video_id": video_id}, timeout=5)
                logger.debug(f"n8n response (Attempt {attempt + 1}): Status {response.status_code}")
                logger.debug(f"n8n response body: {response.text}")
                
                if response.status_code == 200:
                    try:
                        status_data = response.json()
                        logger.debug(f"Status data from n8n: {status_data}")
                        result = jsonify(status_data)
                        result.headers['Access-Control-Allow-Origin'] = '*'
                        return result
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON parse error: {json_err}")
                        logger.error(f"Raw data: {response.text}")
                        continue  # Versuche es erneut bei JSON-Fehler
                
                elif response.status_code == 404:
                    logger.warning(f"Webhook not found (404) - Attempt {attempt + 1}")
                    # Warte kurz vor dem nächsten Versuch
                    time.sleep(1)
                    continue
                
                else:
                    logger.error(f"Unexpected status code: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    break  # Bei anderen Fehlern nicht erneut versuchen
            
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout during attempt {attempt + 1}")
                continue
            except requests.exceptions.ConnectionError as conn_err:
                logger.error(f"Connection error during attempt {attempt + 1}: {conn_err}")
                time.sleep(1)  # Warte kurz vor dem nächsten Versuch
                continue
        
        # Wenn alle Versuche fehlgeschlagen sind
        logger.error("All attempts failed")
        result = jsonify({
            'status': 0,
            'message': 'Failed to connect to status service'
        })
        result.headers['Access-Control-Allow-Origin'] = '*'
        return result
        
    except Exception as e:
        logger.exception(f"Unexpected error during status check: {str(e)}")
        result = jsonify({
            'status': 0,
            'error': str(e),
            'message': 'Internal server error during status check'
        })
        result.headers['Access-Control-Allow-Origin'] = '*'
        return result, 500

@app.route('/proxy-check-status/<video_id>', methods=['POST'])
def proxy_check_status(video_id):
    """Proxy-Route für den n8n Webhook Status-Check"""
    try:
        logger.debug(f"Proxy status check for video {video_id}")
        webhook_url = f"http://n8n:5678/webhook/check-status/{video_id}"
        logger.debug(f"Call n8n webhook: {webhook_url}")
        
        response = requests.post(webhook_url, json={"video_id": video_id})
        logger.debug(f"n8n response status: {response.status_code}")
        
        if response.status_code == 200:
            status_data = response.json()
            logger.debug(f"Status data: {status_data}")
            # Aktualisiere den lokalen Status-Cache
            cutdown_status[video_id] = status_data
            return jsonify(status_data)
        
        logger.warning(f"Unexpected status code from n8n: {response.status_code}")
        return jsonify({
            'status': 'processing',
            'message': 'Video is being processed'
        }), response.status_code
        
    except Exception as e:
        logger.exception("Error during proxy status check")
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500

@app.route('/check-cutdown-status/<video_id>')
def check_cutdown_status(video_id):
    """Überprüft den Status der Cutdown-Generierung für ein Video"""
    try:
        # Prüfe, ob das Cutdown-Video bereits existiert
        cutdown_path = f"/app/videos/cutdowns/{video_id}_cut.mp4"
        if os.path.exists(cutdown_path):
            return jsonify({
                'status': 'completed',
                'cutdown_path': f"/videos/cutdowns/{video_id}_cut.mp4"
            })
        
        # Prüfe den Status in der Datenbank
        if video_id in cutdown_status:
            return jsonify(cutdown_status[video_id])
        
        # Wenn kein Status gefunden wurde, prüfe bei n8n nach
        webhook_url = f"http://n8n:5678/webhook/check-status/{video_id}"
        response = requests.get(webhook_url)
        
        if response.status_code == 200:
            status_data = response.json()
            cutdown_status[video_id] = status_data
            return jsonify(status_data)
        
        # Wenn n8n nicht antwortet, nehmen wir an, dass es noch verarbeitet wird
        return jsonify({
            'status': 'processing',
            'message': 'Video is being processed'
        })
        
    except Exception as e:
        logger.exception("Error during cutdown status check")
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        logger.debug("Upload request received")
        logger.debug(f"Request files: {request.files}")
        logger.debug(f"Request form: {request.form}")
        
        if 'video' not in request.files:
            logger.error("No video file in request")
            return jsonify({'error': 'No file found'}), 400
        
        file = request.files['video']
        logger.debug(f"Received file: {file.filename}")
        
        if file.filename == '':
            logger.error("No filename provided")
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            logger.error(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'File type not allowed'}), 400
            
        # Store original filename for duplicate checking
        original_filename = secure_filename(file.filename)
        
        # Generiere eine eindeutige ID für das Video
        video_id = str(uuid.uuid4())
        filename = f"{video_id}_{original_filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.debug(f"Saving file to: {filepath}")
        
        # Stelle sicher, dass das Upload-Verzeichnis existiert
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save the file
        file.save(filepath)
        logger.debug("File saved successfully")
        
        # Get file size
        file_size = os.path.getsize(filepath)
        logger.debug(f"File size: {file_size} bytes")
        
        # Parse cutdown options if provided
        cutdown_options = {}
        if 'cutdown_options' in request.form:
            try:
                cutdown_options = json.loads(request.form['cutdown_options'])
                logger.debug(f"Cutdown options: {cutdown_options}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse cutdown options: {e}")
                cutdown_options = {
                    'length': '60',
                    'style': 'highlight',
                    'focus': ['action']
                }
        else:
            # Default options
            cutdown_options = {
                'length': '60',
                'style': 'highlight',
                'focus': ['action']
            }

        # Optional prompt (textarea)
        prompt_text = (request.form.get('prompt') or '').strip()
        if prompt_text:
            cutdown_options['prompt'] = prompt_text
        
        # Send webhook notification to n8n
        webhook_url = "http://n8n:5678/webhook/video"
        webhook_payload = {
            "filepath": "/app/videos/uploads/" + filename,
            "filename": filename,
            "original_filename": original_filename,  # NEW: Original filename for duplicate checking
            "size": file_size,
            "video_id": video_id,
            "id": video_id,
            "cutdown_options": cutdown_options,
            "prompt": prompt_text
        }
        webhook_response = requests.post(webhook_url, json=webhook_payload, headers={"Content-Type": "application/json"})
        
        # Setze initialen Status
        cutdown_status[video_id] = {
            'status': 'processing',
            'message': 'Video is being processed'
        }
        
        if webhook_response.status_code != 200:
            logger.error(f"Error sending webhook: {webhook_response.status_code} {webhook_response.text}")
            return jsonify({
                'message': 'File successfully uploaded',
                'filename': filename,
                'original_filename': original_filename,  # NEW: Include in response
                'filepath': "/videos/uploads/" + filename,
                'status': 'uploaded',
                'size': file_size,
                'video_id': video_id,
                'webhook_status': 'failed',
                'webhook_error': str(webhook_response.text)
            }), 200
        else:
            logger.debug("Webhook sent successfully.")
            return jsonify({
                'message': 'File successfully uploaded',
                'filename': filename,
                'original_filename': original_filename,  # NEW: Include in response
                'filepath': "/videos/uploads/" + filename,
                'status': 'uploaded',
                'size': file_size,
                'video_id': video_id,
                'webhook_status': 'success'
            }), 200
            
    except requests.exceptions.RequestException as e:
        # Only handle errors from the main webhook URL
        if hasattr(e, 'response') and e.response is not None:
            if '/webhook/video' in e.response.url and '/metadata' not in e.response.url:
                logger.error(f"Webhook error: {str(e)}")
                return jsonify({
                    'message': 'File successfully uploaded',
                    'filename': filename,
                    'filepath': "/app/videos/uploads/" + filename,
                    'status': 'uploaded',
                    'size': file_size,
                    'video_id': video_id,
                    'webhook_status': 'failed',
                    'webhook_error': str(e)
                }), 200
        # For other request errors, return 500
        raise
    except Exception as e:
        logger.exception("Unexpected error during upload")
        return jsonify({
            'error': 'Internal Server Error',
            'details': str(e),
            'traceback': traceback.format_exc() if app.debug else None
        }), 500

@app.route('/videos/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded video files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, conditional=True)

@app.route('/videos/screenshots/<path:filename>')
def serve_screenshot(filename):
    """Serve screenshot files"""
    screenshot_dir = '/app/videos/screenshots'
    full_path = os.path.join(screenshot_dir, filename)
    if not os.path.isfile(full_path):
        app.logger.error(f"Screenshot not found: {full_path}")
        return jsonify({'error': 'Screenshot not found', 'path': full_path}), 404
    return send_file(full_path, conditional=True)

@app.route('/videos/cutdowns/<path:filename>')
def serve_cutdown(filename):
    """Serve cutdown video files"""
    return send_from_directory(app.config['CUTDOWN_FOLDER'], filename, conditional=True)

@app.route('/videos/revoiced/<path:filename>')
def serve_revoiced(filename):
    """Serve revoiced audio files"""
    return send_from_directory(REVOICED_FOLDER, filename, conditional=True)

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files including video.mp4"""
    return send_from_directory('static', filename, conditional=True)

@app.route('/generate-music', methods=['POST'])
def generate_music():
    """
    Proxy endpoint for music generation.
    Forwards the request to the dedicated musicgen-service.
    """
    try:
        if not request.is_json:
            logger.error("Request is not JSON. Content-Type: " + request.content_type)
            return jsonify({'error': 'Request must be application/json'}), 415

        data = request.get_json()
        if not data:
            logger.error("No JSON data received in body.")
            return jsonify({'error': 'No data found in request body'}), 400

        logger.debug(f"Forwarding music generation request to musicgen-service: {data}")

        # URL for the new musicgen-service
        musicgen_url = "http://musicgen:8001/generate"
        
        # Forward the request
        response = requests.post(musicgen_url, json=data, timeout=360) # Longer timeout
        response.raise_for_status() # Raises an error for status codes 4xx/5xx

        # Return the response from the musicgen-service to the client
        music_data = response.json()
        
        # The URL from the musicgen-service is internal. We need to adjust it for the browser.
        # The musicgen-service returns z.B. /music/generated/somefile.wav.
        # We can use this path directly as Caddy correctly forwards the requests.
        
        return jsonify({
            'status': 'success',
            'message': 'Music successfully generated',
            'data': {
                'filename': music_data.get('filename'),
                'url': music_data.get('url') # Pass URL directly
            }
        })

    except requests.exceptions.Timeout:
        logger.error("Timeout during request to musicgen-service.")
        return jsonify({'status': 'error', 'message': 'Music generation timed out'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during request to musicgen-service: {e}")
        return jsonify({'status': 'error', 'message': f"Error connecting to music generation service: {e}"}), 502
    except Exception as e:
        logger.exception("Error in /generate-music endpoint")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/music/generated/<path:filename>')
def serve_generated_music(filename):
    """Serve generated music files"""
    return send_from_directory('/app/music/generated', filename, conditional=True)

@app.post("/detect-language-url")
async def detect_language_from_url(request: AudioUrlRequest):
    if not model:
        raise HTTPException(status_code=503, detail="Whisper model not loaded yet")
    try:
        temp_file_path = download_file_from_url(request.audio_url)
        logger.info(f"Detecting language for URL: {request.audio_url}")
        result = model.detect_language(temp_file_path)
        os.unlink(temp_file_path)
        return {
            "language": result,
            "confidence": 1.0
        }
    except Exception as e:
        logger.error(f"Error in detect_language_from_url: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/asr-url")
async def transcribe_audio_from_url(request: AsrUrlRequest):
    if not model:
        raise HTTPException(status_code=503, detail="Whisper model not loaded yet")
    try:
        temp_file_path = download_file_from_url(request.audio_url)
        result = process_audio_file(temp_file_path, request.language_code)
        os.unlink(temp_file_path)
        return result
    except Exception as e:
        logger.error(f"Error in transcribe_audio_from_url: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ElevenLabs Voice Integration
@app.route('/elevenlabs/voices')
def get_elevenlabs_voices():
    """Get list of available ElevenLabs voices"""
    try:
        headers = {
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(f'{ELEVENLABS_BASE_URL}/voices', headers=headers)
        
        if response.status_code == 200:
            voices_data = response.json()
            voices = []
            
            for voice in voices_data.get('voices', []):
                voice_info = {
                    'voice_id': voice.get('voice_id'),
                    'name': voice.get('name'),
                    'labels': voice.get('labels', {}),
                    'description': voice.get('description', ''),
                    'category': voice.get('category', ''),
                    'preview_url': voice.get('preview_url', '')
                }
                voices.append(voice_info)
            
            logger.info(f'Loaded {len(voices)} ElevenLabs voices')
            return jsonify(voices)
        else:
            logger.error(f'ElevenLabs API error: {response.status_code}')
            return jsonify({'error': 'Failed to load voices'}), 500
            
    except Exception as e:
        logger.error(f'Error loading ElevenLabs voices: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/elevenlabs/preview', methods=['POST'])
def preview_elevenlabs_voice():
    """Generate audio preview for a voice"""
    try:
        data = request.get_json()
        voice_id = data.get('voice_id')
        text = data.get('text', 'Hallo, das ist eine Vorschau dieser Stimme.')
        
        if not voice_id:
            return jsonify({'error': 'Voice ID required'}), 400
        
        headers = {
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'text': text,
            'model_id': 'eleven_multilingual_v2',
            'voice_settings': {
                'stability': 0.5,
                'similarity_boost': 0.5
            }
        }
        
        response = requests.post(
            f'{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}',
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            # Save audio to temp folder
            audio_filename = f'preview_{voice_id}.mp3'
            audio_path = os.path.join(TEMP_FOLDER, audio_filename)
            
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            
            return send_from_directory(TEMP_FOLDER, audio_filename, mimetype='audio/mpeg', conditional=True)
        else:
            logger.error(f'ElevenLabs TTS error: {response.status_code}')
            return jsonify({'error': 'Failed to generate preview'}), 500
            
    except Exception as e:
        logger.error(f'Error generating voice preview: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/elevenlabs/generate', methods=['POST'])
def generate_elevenlabs_audio():
    """Generate full audio for a scene"""
    try:
        data = request.get_json()
        voice_id = data.get('voice_id')
        text = data.get('text')
        scene_id = data.get('scene_id')
        
        if not all([voice_id, text, scene_id]):
            return jsonify({'error': 'Voice ID, text, and scene ID required'}), 400
        
        headers = {
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'text': text,
            'model_id': 'eleven_multilingual_v2',
            'voice_settings': {
                'stability': 0.5,
                'similarity_boost': 0.5
            }
        }
        
        response = requests.post(
            f'{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}',
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            # Save audio to revoiced folder
            audio_filename = f'scene_{scene_id}_voice_{voice_id}.mp3'
            audio_path = os.path.join(REVOICED_FOLDER, audio_filename)
            
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            
            return jsonify({
                'success': True,
                'audio_path': f'/videos/revoiced/{audio_filename}',
                'filename': audio_filename
            })
        else:
            logger.error(f'ElevenLabs TTS error: {response.status_code}')
            return jsonify({'error': 'Failed to generate audio'}), 500
            
    except Exception as e:
        logger.error(f'Error generating audio: {e}')
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5679, debug=True) 