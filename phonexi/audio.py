import io
import threading
import wave

import pyaudiowpatch as pyaudio
from groq import Groq

from phonexi.config import GROQ_API_KEY

_CHUNK = 512
_WHISPER_MODEL = "whisper-large-v3-turbo"


def _get_loopback_device(p: pyaudio.PyAudio) -> dict:
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])

    if default_speakers.get("isLoopbackDevice"):
        return default_speakers

    for loopback in p.get_loopback_device_info_generator():
        if default_speakers["name"] in loopback["name"]:
            return loopback

    raise RuntimeError("No WASAPI loopback device found for default output")


def record(stop_event: threading.Event) -> bytes:
    """Capture system audio (loopback) until stop_event is set. Returns WAV bytes."""
    with pyaudio.PyAudio() as p:
        device = _get_loopback_device(p)
        channels = device["maxInputChannels"]
        samplerate = int(device["defaultSampleRate"])

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=samplerate,
            input=True,
            input_device_index=device["index"],
            frames_per_buffer=_CHUNK,
        )

        frames = []
        while not stop_event.is_set():
            data = stream.read(_CHUNK, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


def transcribe(wav_bytes: bytes) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    result = client.audio.transcriptions.create(
        file=("audio.wav", wav_bytes),
        model=_WHISPER_MODEL,
        response_format="text",
    )
    return result.strip() if isinstance(result, str) else result.text.strip()
