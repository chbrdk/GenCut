# shared/elevenlabs_client.py
import os
import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ElevenLabsClient:
    """Gemeinsamer ElevenLabs API-Client für alle Services"""
    
    def __init__(self):
        self.api_key = os.environ.get('ELEVENLABS_API_KEY')
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY Umgebungsvariable ist erforderlich")
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            'xi-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def get_voices(self) -> List[Dict]:
        """Hole verfügbare Stimmen"""
        try:
            response = requests.get(f"{self.base_url}/voices", headers=self.headers)
            response.raise_for_status()
            return response.json().get('voices', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch voices: {e}")
            raise Exception(f"ElevenLabs API error: {e}")
    
    def preview_voice(self, voice_id: str, text: str) -> bytes:
        """Generiere Audio-Preview für Stimme"""
        try:
            url = f"{self.base_url}/text-to-speech/{voice_id}/preview"
            data = {"text": text}
            
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to preview voice: {e}")
            raise Exception(f"ElevenLabs preview error: {e}")
    
    def generate_audio(self, voice_id: str, text: str, model_id: str = "eleven_multilingual_v2") -> bytes:
        """Generiere Audio mit ElevenLabs"""
        try:
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            data = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to generate audio: {e}")
            raise Exception(f"ElevenLabs generation error: {e}")
    
    def get_voice_by_id(self, voice_id: str) -> Optional[Dict]:
        """Hole spezifische Stimme nach ID"""
        try:
            voices = self.get_voices()
            for voice in voices:
                if voice.get('voice_id') == voice_id:
                    return voice
            return None
        except Exception as e:
            logger.error(f"Failed to get voice by ID: {e}")
            raise Exception(f"ElevenLabs voice lookup error: {e}")

# Singleton instance
_elevenlabs_client = None

def get_elevenlabs_client() -> ElevenLabsClient:
    """Get singleton ElevenLabs client instance"""
    global _elevenlabs_client
    if _elevenlabs_client is None:
        _elevenlabs_client = ElevenLabsClient()
    return _elevenlabs_client
