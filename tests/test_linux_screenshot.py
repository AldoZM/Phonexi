from phonexi.backends.linux import LinuxScreenshotBackend


def test_build_pipeline_desc_embeds_fd_and_node():
    desc = LinuxScreenshotBackend()._build_pipeline_desc(fd=7, node_id=42)
    assert "pipewiresrc" in desc
    assert "fd=7" in desc
    assert "path=42" in desc
    # PNG-encoded frames pulled from a latest-frame appsink
    assert "pngenc" in desc
    assert "appsink" in desc
    assert "max-buffers=1" in desc
    assert "drop=true" in desc


def test_capture_without_start_raises():
    b = LinuxScreenshotBackend()
    try:
        b.capture()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "start" in str(exc).lower()
