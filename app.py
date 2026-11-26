from pathlib import Path
from uuid import uuid4
import json, shutil, subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
VOICE_DIR, OUTPUT_DIR, STATIC_DIR = BASE/"voices", BASE/"generated", BASE/"static"
VOICE_DIR.mkdir(exist_ok=True); OUTPUT_DIR.mkdir(exist_ok=True)
app = FastAPI(title="EchoVoice")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = "en_US-lessac-medium"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    noise: float = Field(default=0.667, ge=0.0, le=1.5)

def installed_voices():
    result=[]
    for model in VOICE_DIR.glob("*.onnx"):
        cfg=model.with_suffix(".onnx.json")
        if cfg.exists():
            try:
                data=json.loads(cfg.read_text())
                result.append({"id":model.stem,"name":model.stem.replace("_"," "),"language":data.get("language",{}).get("name_english","Unknown")})
            except Exception: pass
    return result

@app.get("/", response_class=HTMLResponse)
def home(): return (STATIC_DIR/"index.html").read_text(encoding="utf-8")

@app.get("/api/voices")
def voices(): return installed_voices()

@app.post("/api/synthesize")
def synthesize(req:SynthesisRequest):
    if not req.text.strip(): raise HTTPException(400,"Please enter some text.")
    model=VOICE_DIR/f"{req.voice}.onnx"
    if not model.exists(): raise HTTPException(404,"Voice model is not installed.")
    exe=shutil.which("piper")
    if not exe: raise HTTPException(500,"Piper is unavailable.")
    out=OUTPUT_DIR/f"{uuid4().hex}.wav"
    cmd=[exe,"--model",str(model),"--output_file",str(out),"--length_scale",str(1/req.speed),"--noise_scale",str(req.noise)]
    try: p=subprocess.run(cmd,input=req.text,text=True,capture_output=True,timeout=3600)
    except subprocess.TimeoutExpired: raise HTTPException(504,"Generation timed out; try a shorter passage.")
    if p.returncode or not out.exists(): raise HTTPException(500,(p.stderr or "Speech generation failed.")[-1200:])
    return {"audio_url":f"/api/audio/{out.name}","filename":out.name}

@app.get("/api/audio/{filename}")
def audio(filename:str):
    if Path(filename).name!=filename or not filename.endswith(".wav"): raise HTTPException(404,"Not found")
    p=OUTPUT_DIR/filename
    if not p.exists(): raise HTTPException(404,"Not found")
    return FileResponse(p,media_type="audio/wav",filename=filename)

@app.get("/api/health")
def health(): return {"status":"ok","voices":len(installed_voices())}
