from pathlib import Path
from uuid import uuid4
import html
import os
import re
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
OUTPUT_DIR, STATIC_DIR = BASE / "generated", BASE / "static"
OUTPUT_DIR.mkdir(exist_ok=True)
app = FastAPI(title="EchoVoice")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = "Amy"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)

def polly_client():
    # Credentials are supplied only through Render environment variables / IAM.
    return boto3.client("polly", region_name=os.getenv("AWS_REGION", "eu-west-2"))

def split_text(text, limit=5200):
    # Split on whitespace at sentence/paragraph boundaries so no Polly request exceeds its sync limit.
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    chunks, current = [], ""
    for part in parts:
        if not part:
            continue
        while len(part) > limit:
            if current:
                chunks.append(current); current = ""
            chunks.append(part[:limit]); part = part[limit:]
        candidate = (current + " " + part).strip()
        if len(candidate) > limit:
            if current: chunks.append(current)
            current = part
        else:
            current = candidate
    if current: chunks.append(current)
    return chunks

@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/voices")
def voices():
    return [{"id":"Amy","name":"Amy, Female","language":"English (United Kingdom)","engine":"Neural"}]

@app.post("/api/synthesize")
def synthesize(req: SynthesisRequest):
    if not req.text.strip():
        raise HTTPException(400, "Please enter some text.")
    if req.voice != "Amy":
        raise HTTPException(400, "Only the Amy voice is configured.")
    client = polly_client()
    rate = max(50, min(200, round(req.speed * 100)))
    chunks = split_text(req.text)
    output = bytearray()
    try:
        for chunk in chunks:
            safe_text = html.escape(chunk, quote=False)
            ssml = f'<speak><prosody rate="{rate}%">{safe_text}</prosody></speak>'
            response = client.synthesize_speech(
                Text=ssml,
                TextType="ssml",
                VoiceId="Amy",
                LanguageCode="en-GB",
                Engine="neural",
                OutputFormat="mp3",
                SampleRate="24000",
            )
            stream = response.get("AudioStream")
            if stream is None:
                raise HTTPException(502, "Amazon Polly returned no audio.")
            output.extend(stream.read())
            stream.close()
    except (BotoCoreError, ClientError) as exc:
        message = str(exc)
        if "UnrecognizedClient" in message or "AccessDenied" in message or "InvalidClientToken" in message:
            raise HTTPException(502, "AWS Polly credentials or permissions are not configured correctly. Check the Render environment variables and IAM policy.")
        raise HTTPException(502, f"Amazon Polly error: {message[:500]}")
    if not output:
        raise HTTPException(502, "Amazon Polly returned an empty audio file.")
    filename = f"{uuid4().hex}.mp3"
    (OUTPUT_DIR / filename).write_bytes(output)
    return {"audio_url": f"/api/audio/{filename}", "filename": filename, "format":"mp3", "voice":"Amy"}

@app.get("/api/audio/{filename}")
def audio(filename: str):
    if Path(filename).name != filename or not filename.endswith(".mp3"):
        raise HTTPException(404, "Not found")
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="audio/mpeg", filename=filename)

@app.get("/api/health")
def health():
    configured = bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
    return {"status":"ok", "provider":"Amazon Polly", "voice":"Amy", "aws_credentials_configured":configured}
