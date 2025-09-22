# config.py
import os

# Directory configuration
UPLOAD_DIR = "/app/videos/uploads"
OUTPUT_DIR = "/app/videos/cutdowns"
SEPARATED_DIR = "/app/videos/separated"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SEPARATED_DIR, exist_ok=True)

# Application configuration
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Model configuration
MODELS_LOADED = False
