import threading

from phonexi import audio


def test_audio_module_imports_without_windows_deps():
    # Importing the module must not require pyaudiowpatch (Windows-only).
    assert hasattr(audio, "record")
    assert hasattr(audio, "transcribe")


def test_record_delegates_to_selected_backend(monkeypatch):
    seen = {}

    class FakeBackend:
        def record(self, stop_event):
            seen["stop_event"] = stop_event
            return b"WAVBYTES"

    monkeypatch.setattr(audio, "get_audio_backend", lambda: FakeBackend())
    ev = threading.Event()

    result = audio.record(ev)

    assert result == b"WAVBYTES"
    assert seen["stop_event"] is ev


def test_to_mono_16k_downsamples_stereo_48k():
    # Two stereo frames at 48kHz -> mono, decimated toward 16kHz.
    import array

    raw = array.array("h", [100, 200, 300, 400]).tobytes()  # 2 stereo samples
    pcm, rate = audio._to_mono_16k(raw, channels=2, samplerate=48000)

    assert rate == 16000
    # step = round(48000/16000) = 3; mono = [150, 350]; decimated [::3] = [150]
    assert array.array("h", pcm).tolist() == [150]
