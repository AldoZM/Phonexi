import io
import threading
import wave

import numpy as np
import sounddevice as sd
from groq import Groq

from phonexi.config import GROQ_API_KEY

_SAMPLERATE = 16000
_WHISPER_MODEL = "whisper-large-v3-turbo"


def record(stop_event: threading.Event) -> bytes:
    frames: list[np.ndarray] = []

    def _cb(indata, _frames, _time, _status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=_SAMPLERATE, channels=1, dtype="int16", callback=_cb):
        stop_event.wait()

    audio = np.concatenate(frames, axis=0) if frames else np.zeros((0, 1), dtype="int16")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_SAMPLERATE)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def transcribe(wav_bytes: bytes) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    result = client.audio.transcriptions.create(
        file=("audio.wav", wav_bytes),
        model=_WHISPER_MODEL,
        response_format="text",
    )
    return result.strip() if isinstance(result, str) else result.text.strip()
