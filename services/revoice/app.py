#!/usr/bin/env python3
"""
Revoice Upload Service
Video-Upload und Revoicing für video-analysis-agent
"""

import os
import uuid
import time
import json
import logging
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Video-Analysis-Agent Configuration
UPLOAD_FOLDER = '/app/videos/uploads'
CUTDOWNS_FOLDER = '/app/videos/cutdowns'
SCREENSHOTS_FOLDER = '/app/videos/screenshots'
REVOICED_FOLDER = '/app/videos/revoiced'
SEPARATED_FOLDER = '/app/videos/separated'
TEMP_FOLDER = '/app/temp'

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024

# Umgebungsbasierte Konfiguration
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
ENV = os.environ.get('FLASK_ENV', 'production')

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    DEBUG=DEBUG,
    ENV=ENV
)

# Ensure all folders exist
for folder in [UPLOAD_FOLDER, CUTDOWNS_FOLDER, SCREENSHOTS_FOLDER, REVOICED_FOLDER, SEPARATED_FOLDER, TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)

video_sessions = {}

# ElevenLabs API Configuration
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
if not ELEVENLABS_API_KEY:
    raise ValueError("ELEVENLABS_API_KEY Umgebungsvariable ist erforderlich")
ELEVENLABS_BASE_URL = 'https://api.elevenlabs.io/v1'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_video_id():
    timestamp = int(time.time())
    random_hex = uuid.uuid4().hex[:8]
    return f"revoice_{timestamp}_{random_hex}"

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'revoice-upload-service',
        'timestamp': time.time(),
        'active_sessions': len(video_sessions),
        'folders': {
            'uploads': os.path.exists(UPLOAD_FOLDER),
            'cutdowns': os.path.exists(CUTDOWNS_FOLDER),
            'screenshots': os.path.exists(SCREENSHOTS_FOLDER),
            'revoiced': os.path.exists(REVOICED_FOLDER),
            'temp': os.path.exists(TEMP_FOLDER)
        }
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'Keine Video-Datei gefunden'}), 400
        
        file = request.files['video']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'Ungültige Datei'}), 400
            
        original_filename = secure_filename(file.filename)
        video_id = generate_video_id()
        filename = f"{video_id}_{original_filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save file
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        # Store session data
        video_sessions[video_id] = {
            'video_id': video_id,
            'original_filename': original_filename,
            'filename': filename,
            'filepath': filepath,
            'file_size': file_size,
            'upload_time': time.time(),
            'status': 'uploaded'
        }
        
        # Send to N8N for workflow integration
        webhook_data = {
            'video_id': video_id,
            'filename': filename,
            'original_filename': original_filename,
            'filepath': filepath,
            'size': file_size
        }
        
        try:
            webhook_response = requests.post(
                'http://n8n:5678/webhook/lip-sync',
                json=webhook_data,
                timeout=10
            )
            logger.info(f"N8N webhook response: {webhook_response.status_code}")
        except Exception as webhook_error:
            logger.error(f"N8N webhook error: {webhook_error}")
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'filename': filename,
            'original_filename': original_filename,
            'file_size': file_size,
            'status': 'processing'
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status/<video_id>')
def check_status(video_id):
    """Check video processing status"""
    try:
        # Get session data
        session_data = video_sessions.get(video_id, {})
        
        if not session_data:
            return jsonify({'error': 'Video ID not found'}), 404
        
        # Check if revoiced file exists
        revoiced_filename = f"{video_id}_revoiced.mp4"
        revoiced_path = os.path.join(REVOICED_FOLDER, revoiced_filename)
        
        response = {
            'video_id': video_id,
            'status': session_data.get('status', 'processing'),
            'original_filename': session_data.get('original_filename'),
            'upload_time': session_data.get('upload_time'),
            'timestamp': time.time()
        }
        
        if os.path.exists(revoiced_path):
            response['status'] = 'completed'
            response['revoice_available'] = True
            response['download_url'] = f"/videos/revoiced/{revoiced_filename}"
        else:
            response['status'] = 'processing'
            response['revoice_available'] = False
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/videos/<folder>/<path:filename>')
def serve_video(folder, filename):
    """Serve videos from local volumes"""
    folder_map = {
        'uploads': UPLOAD_FOLDER,
        'cutdowns': CUTDOWNS_FOLDER,
        'screenshots': SCREENSHOTS_FOLDER,
        'revoiced': REVOICED_FOLDER,
        'separated': SEPARATED_FOLDER
    }
    
    if folder in folder_map:
        return send_from_directory(folder_map[folder], filename)
    else:
        return jsonify({'error': 'Invalid folder'}), 404

@app.route('/sessions')
def list_sessions():
    """List all video sessions"""
    return jsonify({
        'sessions': list(video_sessions.values()),
        'total': len(video_sessions)
    })

@app.route('/lip-sync-status', methods=['POST'])
def lip_sync_status():
    data = request.get_json()
    video_id = data.get('video_id')
    if not video_id:
        return jsonify({'error': 'video_id fehlt'}), 400

    # Anfrage an n8n weiterleiten
    try:
        n8n_url = "http://n8n:5678/webhook/lip-sync-status"
        n8n_response = requests.post(
            n8n_url,
            json={"video_id": video_id},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if n8n_response.status_code == 200:
            return jsonify(n8n_response.json())
        else:
            return jsonify({'status': 'processing', 'message': 'n8n antwortet nicht wie erwartet'}), n8n_response.status_code
    except Exception as e:
        return jsonify({'status': 'processing', 'error': str(e)}), 200

@app.route('/n8n-health')
def n8n_health():
    """Health-Check: Kann der revoice-Service n8n im Docker-Netzwerk erreichen?"""
    test_id = "healthcheck_dummy_id"
    n8n_url = "http://n8n:5678/webhook/lip-sync-status"
    try:
        resp = requests.post(
            n8n_url,
            json={"video_id": test_id},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        return jsonify({
            "status_code": resp.status_code,
            "response": resp.json() if resp.content else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            
            return send_from_directory(TEMP_FOLDER, audio_filename, mimetype='audio/mpeg')
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
    app.run(host='0.0.0.0', port=5679, debug=True) 