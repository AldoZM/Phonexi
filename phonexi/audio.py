import io
import threading
import wave

import numpy as np
import sounddevice as sd
from groq import Groq

from phonexi.config import GROQ_API_KEY

_SAMPLERATE = 16000
_WHISPER_MODEL = "whisper-large-v3-turbo"


def _loopback_device() -> tuple[int, int]:
    """Return (device_index, channels) for WASAPI loopback of the default output device."""
    for api in sd.query_hostapis():
        if "WASAPI" in api["name"]:
            dev_idx = api["default_output_device"]
            channels = max(1, sd.query_devices(dev_idx)["max_output_channels"])
            return dev_idx, channels
    raise RuntimeError("WASAPI not found — required for system audio loopback on Windows")


def record(stop_event: threading.Event) -> bytes:
    """Capture system audio (loopback) until stop_event is set. Returns WAV bytes."""
    frames: list[np.ndarray] = []

    def _cb(indata, _frames, _time, _status):
        frames.append(indata.copy())

    device, channels = _loopback_device()

    with sd.InputStream(
        device=device,
        samplerate=_SAMPLERATE,
        channels=channels,
        dtype="int16",
        extra_settings=sd.WasapiSettings(loopback=True),
        callback=_cb,
    ):
        stop_event.wait()

    audio = np.concatenate(frames, axis=0) if frames else np.zeros((0, channels), dtype="int16")

    # Mix down to mono for Whisper
    if channels > 1:
        audio = audio.mean(axis=1, keepdims=True).astype("int16")

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
