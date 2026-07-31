import pytest

from phonexi import backends


def test_get_audio_backend_linux_has_record():
    b = backends.get_audio_backend(platform="linux")
    assert hasattr(b, "record")


def test_get_audio_backend_windows_selectable_on_any_platform():
    # Selecting the Windows backend must not import Windows-only deps at
    # selection time — only calling record() would need them.
    b = backends.get_audio_backend(platform="win32")
    assert hasattr(b, "record")


def test_get_audio_backend_unknown_platform_raises():
    with pytest.raises(RuntimeError, match="Unsupported platform"):
        backends.get_audio_backend(platform="sunos")


def test_get_input_backend_selectable_per_platform():
    assert hasattr(backends.get_input_backend(platform="win32"), "run")
    assert hasattr(backends.get_input_backend(platform="linux"), "run")


def test_get_input_backend_unknown_platform_raises():
    with pytest.raises(RuntimeError, match="Unsupported platform"):
        backends.get_input_backend(platform="sunos")
