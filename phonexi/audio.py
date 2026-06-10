import array as _array
import io
import threading
import wave

import pyaudiowpatch as pyaudio
from groq import Groq

from phonexi.config import GROQ_API_KEY

_CHUNK = 512
_WHISPER_MODEL = "whisper-large-v3-turbo"
_TARGET_RATE = 16000


def _to_mono_16k(raw: bytes, channels: int, samplerate: int) -> tuple[bytes, int]:
    """Downsample to mono 16kHz. Reduces WAV size ~6x for typical 48kHz stereo input."""
    samples = _array.array("h", raw)

    if channels > 1:
        mono = _array.array("h")
        for i in range(0, len(samples), channels):
            mono.append(sum(samples[i : i + channels]) // channels)
    else:
        mono = samples

    step = max(1, round(samplerate / _TARGET_RATE))
    decimated = _array.array("h", mono[::step])
    actual_rate = samplerate // step

    return decimated.tobytes(), actual_rate


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

    pcm, out_rate = _to_mono_16k(b"".join(frames), channels, samplerate)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(out_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def transcribe(wav_bytes: bytes) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    result = client.audio.transcriptions.create(
        file=("audio.wav", wav_bytes),
        model=_WHISPER_MODEL,
        response_format="text",
    )
    return result.strip() if isinstance(result, str) else result.text.strip()
