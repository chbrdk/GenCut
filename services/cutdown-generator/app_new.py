# app_new.py - Refactored cutdown generator with shared libraries
from flask import Flask, request, jsonify, render_template_string
import os
import uuid
import requests
import logging
import time
from werkzeug.utils import secure_filename
from typing import Dict, Any

# Import shared libraries
import sys
sys.path.append('/app/shared')
from elevenlabs_client import get_elevenlabs_client, ElevenLabsError
from utils.error_handler import register_error_handlers, UploadError, FileNotFoundError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = '/app/videos/uploads'
CUTDOWN_FOLDER = '/app/videos/cutdowns'
TEMP_FOLDER = '/app/temp'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024  # 5GB

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

# Register error handlers
register_error_handlers(app)

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CUTDOWN_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_video_id():
    return str(uuid.uuid4())

@app.route('/')
def index():
    """Main upload interface"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GenCut - Video Cutdown Generator</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold text-center mb-8 text-gray-800">GenCut Video Cutdown Generator</h1>
        
        <div class="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-6">
            <form id="uploadForm" enctype="multipart/form-data" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Video-Datei auswählen</label>
                    <input type="file" name="video" accept="video/*" required 
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Cutdown-Länge (Sekunden)</label>
                        <input type="number" name="length" value="60" min="10" max="300" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Stil</label>
                        <select name="style" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <option value="highlight">Highlight</option>
                            <option value="action">Action</option>
                            <option value="dramatic">Dramatic</option>
                            <option value="comedy">Comedy</option>
                        </select>
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Prompt (optional)</label>
                    <textarea name="prompt" rows="3" placeholder="Beschreibe den gewünschten Cutdown-Stil..."
                              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
                </div>
                
                <button type="submit" 
                        class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    Video hochladen und Cutdown generieren
                </button>
            </form>
            
            <div id="status" class="mt-4 hidden">
                <div class="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded">
                    <p id="statusText"></p>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const statusDiv = document.getElementById('status');
            const statusText = document.getElementById('statusText');
            
            statusDiv.classList.remove('hidden');
            statusText.textContent = 'Video wird hochgeladen...';
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    statusText.textContent = `Upload erfolgreich! Video-ID: ${result.video_id}`;
                    statusDiv.className = 'mt-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded';
                } else {
                    statusText.textContent = `Fehler: ${result.error}`;
                    statusDiv.className = 'mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded';
                }
            } catch (error) {
                statusText.textContent = `Fehler: ${error.message}`;
                statusDiv.className = 'mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded';
            }
        });
    </script>
</body>
</html>
    ''')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload video file for cutdown generation"""
    try:
        if 'video' not in request.files:
            raise UploadError("Keine Video-Datei gefunden")
        
        file = request.files['video']
        if file.filename == '':
            raise UploadError("Keine Datei ausgewählt")
        
        if not allowed_file(file.filename):
            raise UploadError("Dateiformat nicht unterstützt")
        
        # Generate unique filename
        video_id = generate_video_id()
        filename = secure_filename(file.filename)
        unique_filename = f"{video_id}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Save file
        file.save(file_path)
        
        # Get form data
        cutdown_options = {
            'length': request.form.get('length', '60'),
            'style': request.form.get('style', 'highlight'),
            'focus': request.form.getlist('focus')
        }
        prompt = request.form.get('prompt', '')
        
        # Send to n8n webhook
        webhook_data = {
            'video_id': video_id,
            'filename': unique_filename,
            'file_path': file_path,
            'cutdown_options': cutdown_options,
            'prompt': prompt
        }
        
        try:
            webhook_response = requests.post(
                'http://n8n:5678/webhook/video',
                json=webhook_data,
                timeout=30
            )
            webhook_status = "success" if webhook_response.status_code == 200 else "failed"
        except Exception as e:
            logger.warning(f"Webhook call failed: {e}")
            webhook_status = "failed"
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'filename': unique_filename,
            'status': 'uploaded',
            'webhook_status': webhook_status
        })
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise UploadError(f"Upload failed: {str(e)}")

@app.route('/check-status', methods=['POST'])
def check_status():
    """Check processing status of video"""
    try:
        data = request.get_json()
        video_id = data.get('video_id')
        
        if not video_id:
            raise UploadError("Video-ID erforderlich")
        
        # Check if cutdown exists
        cutdown_path = os.path.join(CUTDOWN_FOLDER, f"{video_id}_cutdown.mp4")
        
        if os.path.exists(cutdown_path):
            return jsonify({
                'status': 'completed',
                'message': 'Cutdown erfolgreich generiert',
                'cutdown_path': f'/videos/cutdowns/{os.path.basename(cutdown_path)}'
            })
        else:
            return jsonify({
                'status': 'processing',
                'message': 'Video wird noch verarbeitet...'
            })
            
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise UploadError(f"Status check failed: {str(e)}")

@app.route('/elevenlabs/voices')
def get_elevenlabs_voices():
    """Get list of available ElevenLabs voices"""
    try:
        client = get_elevenlabs_client()
        voices = client.get_voices()
        return jsonify(voices)
    except Exception as e:
        logger.error(f"ElevenLabs voices error: {e}")
        raise ElevenLabsError(f"Failed to fetch voices: {str(e)}")

@app.route('/elevenlabs/preview', methods=['POST'])
def preview_elevenlabs_voice():
    """Preview ElevenLabs voice"""
    try:
        data = request.get_json()
        voice_id = data.get('voice_id')
        text = data.get('text', 'Hallo, das ist ein Test.')
        
        if not voice_id:
            raise ElevenLabsError("Voice-ID erforderlich")
        
        client = get_elevenlabs_client()
        audio_data = client.preview_voice(voice_id, text)
        
        return jsonify({
            'success': True,
            'audio_data': audio_data.hex()  # Convert to hex string for JSON
        })
    except Exception as e:
        logger.error(f"ElevenLabs preview error: {e}")
        raise ElevenLabsError(f"Preview failed: {str(e)}")

@app.route('/elevenlabs/generate', methods=['POST'])
def generate_elevenlabs_audio():
    """Generate audio with ElevenLabs"""
    try:
        data = request.get_json()
        voice_id = data.get('voice_id')
        text = data.get('text')
        model_id = data.get('model_id', 'eleven_multilingual_v2')
        
        if not voice_id or not text:
            raise ElevenLabsError("Voice-ID und Text erforderlich")
        
        client = get_elevenlabs_client()
        audio_data = client.generate_audio(voice_id, text, model_id)
        
        return jsonify({
            'success': True,
            'audio_data': audio_data.hex()  # Convert to hex string for JSON
        })
    except Exception as e:
        logger.error(f"ElevenLabs generation error: {e}")
        raise ElevenLabsError(f"Generation failed: {str(e)}")

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'cutdown-generator',
        'timestamp': time.time(),
        'debug_mode': DEBUG
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5679, debug=DEBUG)
