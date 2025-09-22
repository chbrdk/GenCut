import ffmpeg
import os
import subprocess

def cut_clip(input_path, output_path, start_time, end_time):
    try:
        # Calculate duration
        duration = end_time - start_time
        
        print(f"Cutting video: {input_path}")
        print(f"  Start time: {start_time}s")
        print(f"  End time: {end_time}s")
        print(f"  Duration: {duration}s")
        print(f"  Output: {output_path}")
        
        # Get video duration using ffprobe
        probe_cmd = [
            "ffprobe", 
            "-v", "quiet", 
            "-show_entries", "format=duration", 
            "-of", "csv=p=0", 
            input_path
        ]
        
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe_result.returncode == 0:
            video_duration = float(probe_result.stdout.strip())
            print(f"  Video duration: {video_duration}s")
            
            # Validate time ranges
            if start_time >= video_duration:
                print(f"  ERROR: Start time {start_time}s is beyond video duration {video_duration}s")
                return False
            
            if end_time > video_duration:
                print(f"  WARNING: End time {end_time}s is beyond video duration {video_duration}s, adjusting to {video_duration}s")
                end_time = video_duration
                duration = end_time - start_time
                print(f"  Adjusted duration: {duration}s")
        else:
            print(f"  WARNING: Could not determine video duration")
        
        # Use correct FFmpeg syntax for cutting video
        # The issue is that we need to use -ss for seeking and -t for duration correctly
        # We'll use subprocess directly for more control
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "ultrafast",
            "-crf", "23",
            "-y",  # Overwrite output
            output_path
        ]
        
        print(f"Running FFmpeg command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print(f"FFmpeg stdout: {result.stdout}")
        print(f"FFmpeg stderr: {result.stderr}")
        print(f"FFmpeg return code: {result.returncode}")
        
        # Check if output file exists and has content
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"  Success: Output file created with size {file_size} bytes")
            return True
        else:
            print(f"  Error: Output file not created")
            return False
            
    except Exception as e:
        print(f"FFmpeg error in cut_clip: {e}")
        return False

def extract_audio(video_path, output_dir):
    """
    Extrahiert Audio aus einem Video und speichert es als MP3.
    Falls kein Audiostream vorhanden ist, wird eine leere MP3-Datei (oder eine Fehlermeldung) zurückgegeben.
    Gibt den Pfad zur extrahierten Audiodatei (oder None) zurück.
    """
    try:
        # Prüfe, ob ein Audiostream vorhanden ist (z. B. mit ffmpeg.probe)
        probe = ffmpeg.probe(video_path)
        has_audio = any (s["codec_type"] == "audio" for s in probe["streams"])
        if not has_audio:
            print("No audio stream found in video – returning empty MP3 (or error).")
            # (Optional: Erstelle eine leere MP3-Datei – oder gib eine Fehlermeldung zurück.)
            video_filename = os.path.basename(video_path)
            audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
            audio_path = os.path.join(output_dir, audio_filename)
            # (Hier: Leere MP3-Datei erstellen – oder None zurückgeben.)
            return None

        # Erstelle den Ausgabedateinamen basierend auf dem Videodateinamen
        video_filename = os.path.basename(video_path)
        audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
        audio_path = os.path.join(output_dir, audio_filename)

        # Extrahiere Audio mit ffmpeg (nur wenn ein Audiostream vorhanden ist)
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, audio_path, acodec='libmp3lame', ab='192k')
        ffmpeg.run(stream, overwrite_output=True)

        return audio_path
    except Exception as e:
        print("FFmpeg error (or no audio stream) during audio extraction:", e)
        return None

def separate_video_audio(video_path, output_dir):
    """
    Trennt ein Video in separate Video- und Audiodateien.
    Falls kein Audiostream vorhanden ist (extract_audio gibt None zurück), wird nur der Video-Pfad (ohne Audio) zurückgegeben.
    Gibt ein Dictionary mit den Pfaden (oder nur video_path) zurück.
    """
    try:
        # Erstelle den Ausgabedateinamen basierend auf dem Videodateinamen
        video_filename = os.path.basename(video_path)
        base_name = os.path.splitext(video_filename)[0]

        # Pfade für die Ausgabedateien
        video_output = os.path.join(output_dir, f"{base_name}_video.mp4")
        audio_output = os.path.join(output_dir, f"{base_name}_audio.mp3")

        # Extrahiere Audio (falls vorhanden)
        audio_path = extract_audio(video_path, output_dir)
        if not audio_path:
            # Fallback: Nur Video (ohne Audio) zurückgeben
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(stream, video_output, vcodec='copy', an=None)
            ffmpeg.run(stream, overwrite_output=True)
            return { "video_path": video_output }

        # Kopiere Video ohne Audio (falls Audio extrahiert wurde)
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, video_output, vcodec='copy', an=None)
        ffmpeg.run(stream, overwrite_output=True)

        return { "video_path": video_output, "audio_path": audio_path }
    except Exception as e:
        print("FFmpeg error (or no audio stream) during separation:", e)
        return None
