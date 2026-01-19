import os
import sys
import uuid
import subprocess
import certifi

# SSL sertifika yolu (Mac'te model indirme sorunlarını azaltır)
os.environ["SSL_CERT_FILE"] = certifi.where()

import whisper

def main():
    if len(sys.argv) < 3:
        # Kullanım: python transcribe_whisper.py <video_path> <out_txt>
        sys.exit(1)

    video_path = sys.argv[1]
    out_path = sys.argv[2]

    if not os.path.exists(video_path):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("")
        sys.exit(0)

    wav_path = f"_audio_{uuid.uuid4().hex}.wav"

    try:
        # MP4 -> WAV (PCM, mono, 16kHz)
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ac", "1",
            "-ar", "16000",
            "-vn",
            wav_path
        ]
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        # Whisper model (local)
        model = whisper.load_model("small")

        # HAM transcript (dil/çeviri yok)
        result = model.transcribe(
            wav_path,
            fp16=False
        )

        text = (result.get("text") or "").strip()

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

    except Exception:
        # Hata olursa boş yaz
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("")
    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except:
                pass

if __name__ == "__main__":
    main()
