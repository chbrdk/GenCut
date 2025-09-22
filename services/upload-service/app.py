import os
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import requests
import logging
import json
import time
import uuid

# Logging konfigurieren
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Konfiguration
UPLOAD_FOLDER = '/app/videos/uploads'
REVOICED_FOLDER = '/app/videos/revoiced' 
SCREENSHOTS_FOLDER = '/app/videos/screenshots'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024  # 5GB max file size

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    REVOICED_FOLDER=REVOICED_FOLDER,
    SCREENSHOTS_FOLDER=SCREENSHOTS_FOLDER,
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    DEBUG=True,
    ENV='development'
)

# Stelle sicher, dass die Verzeichnisse existieren
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REVOICED_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOTS_FOLDER, exist_ok=True)

# Speichere den Status der Lip-Sync-Verarbeitung
lip_sync_status = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_video_id():
    """Generate unique video ID for lip-sync"""
    timestamp = int(time.time())
    random_hex = uuid.uuid4().hex[:8]
    return f"revoice_{timestamp}_{random_hex}"

@app.route('/')
def upload_form():
    """Zeige das Upload-Formular"""
    return render_template('upload.html')

@app.route('/health')
def health_check():
    """Health Check Endpunkt"""
    return jsonify({
        'status': 'healthy',
        'service': 'video-upload-lip-sync-service',
        'timestamp': time.time(),
        'active_sessions': len(lip_sync_status)
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle Video Upload für Lip-Sync"""
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'Keine Video-Datei gefunden'}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': 'Keine Datei ausgewählt'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Dateityp nicht erlaubt'}), 400
        
        # Generate unique video ID and secure filename
        video_id = generate_video_id()
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        filename = f"{video_id}.{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save uploaded file
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        logger.info(f"Video uploaded: {filename}, Size: {file_size} bytes, Video ID: {video_id}")
        
        # Send webhook notification to n8n for Lip-Sync processing
        webhook_url = "http://n8n:5678/webhook/lip-sync"
        webhook_payload = {
            "filepath": "/app/videos/uploads/" + filename,
            "filename": filename,
            "original_filename": original_filename,
            "size": file_size,
            "video_id": video_id,
            "id": video_id
        }
        
        try:
            webhook_response = requests.post(
                webhook_url, 
                json=webhook_payload, 
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            logger.info(f"Webhook sent to n8n: {webhook_response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to send webhook to n8n: {e}")
            # Continue anyway, the webhook might not be available yet
        
        # Set initial status
        lip_sync_status[video_id] = {
            'status': 'processing',
            'message': 'Video wird für Lip-Sync verarbeitet'
        }
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'filename': filename,
            'original_filename': original_filename,
            'filepath': filepath,
            'size': file_size,
            'message': 'Video erfolgreich hochgeladen und Lip-Sync gestartet'
        })
        
    except Exception as e:
        logger.exception("Error during upload")
        return jsonify({'error': str(e)}), 500

@app.route('/lip-sync-status', methods=['POST'])
def check_lip_sync_status():
    """Proxy-Route für den n8n Webhook Lip-Sync Status-Check"""
    try:
        # Die video_id aus dem Request-Body nehmen
        data = request.get_json()
        video_id = data.get('video_id') if data else None
        
        if not video_id:
            return jsonify({
                'error': 'video_id fehlt im Request-Body'
            }), 400
        
        webhook_url = f"http://n8n:5678/webhook/lip-sync-status"
        logger.debug(f"Rufe n8n Lip-Sync Webhook auf: {webhook_url} mit video_id: {video_id}")
        
        response = requests.post(
            webhook_url, 
            json={"video_id": video_id},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        logger.debug(f"n8n Antwort Status: {response.status_code}")
        
        if response.status_code == 200:
            status_data = response.json()
            logger.debug(f"Lip-Sync Status-Daten: {status_data}")
            # Aktualisiere den lokalen Status-Cache
            lip_sync_status[video_id] = status_data
            return jsonify(status_data)
        
        logger.warning(f"Unerwarteter Status-Code von n8n: {response.status_code}")
        return jsonify({
            'status': 'processing',
            'message': 'Lip-Sync wird verarbeitet'
        }), response.status_code
        
    except requests.exceptions.RequestException as e:
        logger.exception("Fehler beim n8n Webhook-Aufruf")
        return jsonify({
            'status': 'processing',
            'message': 'Lip-Sync wird verarbeitet',
            'error': 'Webhook temporär nicht verfügbar'
        }), 200
        
    except Exception as e:
        logger.exception("Fehler beim Lip-Sync Status-Check")
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500

@app.route('/check-status/<video_id>')
def check_status_get(video_id):
    """Legacy GET endpoint für Status-Check"""
    try:
        if video_id in lip_sync_status:
            return jsonify(lip_sync_status[video_id])
        
        return jsonify({
            'status': 'processing',
            'message': 'Lip-Sync wird verarbeitet'
        })
        
    except Exception as e:
        logger.exception("Fehler beim Status-Check")
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500

@app.route('/videos/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded video files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/videos/revoiced/<path:filename>')
def serve_revoiced(filename):
    """Serve revoiced video files"""
    return send_from_directory(app.config['REVOICED_FOLDER'], filename)

@app.route('/videos/screenshots/<path:filename>')
def serve_screenshot(filename):
    """Serve screenshot files"""
    return send_from_directory(app.config['SCREENSHOTS_FOLDER'], filename)

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    static_folder = '/app/static'
    return send_from_directory(static_folder, filename)

if __name__ == '__main__':
    logger.info("Starting Video Lip-Sync Upload Service...")
    app.run(host='0.0.0.0', port=5679, debug=True) 