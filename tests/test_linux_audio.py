import threading

import pytest

from phonexi.backends.linux import LinuxAudioBackend


def _dump_with_default_sink(value):
    return [
        {"type": "PipeWire:Interface:Metadata",
         "props": {"metadata.name": "default"},
         "metadata": [{"key": "default.audio.sink", "value": value}]},
    ]


def test_default_sink_name_from_object_value():
    dump = _dump_with_default_sink({"name": "bluez_output.AA_BB"})
    assert LinuxAudioBackend()._default_sink_name(dump) == "bluez_output.AA_BB"


def test_default_sink_name_from_json_string_value():
    dump = _dump_with_default_sink('{"name": "alsa_output.speaker"}')
    assert LinuxAudioBackend()._default_sink_name(dump) == "alsa_output.speaker"


def test_default_sink_name_missing_raises():
    with pytest.raises(RuntimeError, match="default audio sink"):
        LinuxAudioBackend()._default_sink_name([])


def test_record_captures_default_sink_monitor_and_returns_wav(monkeypatch):
    backend = LinuxAudioBackend()
    seen = {}

    monkeypatch.setattr(
        backend, "_dump_pipewire",
        lambda: _dump_with_default_sink({"name": "sink.default"}),
    )

    def fake_capture(target, stop_event):
        seen["target"] = target
        seen["stop_event"] = stop_event
        return b"WAVFROMPIPEWIRE"

    monkeypatch.setattr(backend, "_capture_to_wav", fake_capture)

    ev = threading.Event()
    result = backend.record(ev)

    assert result == b"WAVFROMPIPEWIRE"
    assert seen["target"] == "sink.default"
    assert seen["stop_event"] is ev
