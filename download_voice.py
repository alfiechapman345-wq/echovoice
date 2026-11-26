from pathlib import Path
from urllib.request import urlretrieve

VOICE_DIR = Path("voices")
VOICE_DIR.mkdir(exist_ok=True)
base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium"
for suffix in (".onnx", ".onnx.json"):
    target = VOICE_DIR / ("en_US-lessac-medium" + suffix)
    if not target.exists():
        print(f"Downloading {target.name} ...")
        urlretrieve(base + suffix, target)
print("Voice ready.")
