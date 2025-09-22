from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import whisper
import os
import tempfile

app = FastAPI()

# Load Whisper model
model = whisper.load_model("base")

@app.post("/asr")
async def transcribe_audio(audio_file: UploadFile = File(...), language_code: str = Form(None)):
    """
    Transcribe audio file using Whisper
    """
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            content = await audio_file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Transcribe with Whisper
            if language_code:
                result = model.transcribe(tmp_file_path, language=language_code)
            else:
                result = model.transcribe(tmp_file_path)
            
            return {
                "text": result["text"],
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", [])
            }
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 