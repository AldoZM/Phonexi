"""Linux backends. Platform deps (evdev, GStreamer, PipeWire) are imported
lazily inside methods so this module imports cleanly on any OS."""
from __future__ import annotations

import json
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

_TARGET_RATE = 16000


class LinuxAudioBackend:
    """Capture system audio on Linux via PipeWire.

    Records the monitor of the default sink (what plays through the
    speakers/headphones) — i.e. the interviewer on a call, not the mic —
    mirroring the Windows WASAPI loopback backend. Uses `pw-record` targeting
    the default sink node, which connects the capture stream to its monitor.
    """

    def _dump_pipewire(self) -> list:
        raw = subprocess.run(
            ["pw-dump"], capture_output=True, text=True, check=True
        ).stdout
        return json.loads(raw)

    def _default_sink_name(self, pw_dump: list) -> str:
        for obj in pw_dump:
            if not str(obj.get("type", "")).endswith("Metadata"):
                continue
            if obj.get("props", {}).get("metadata.name") != "default":
                continue
            for entry in obj.get("metadata", []):
                if entry.get("key") != "default.audio.sink":
                    continue
                value = entry.get("value")
                if isinstance(value, dict):
                    return value["name"]
                if isinstance(value, str):
                    try:
                        return json.loads(value)["name"]
                    except (ValueError, KeyError, TypeError):
                        return value
        raise RuntimeError("No default audio sink found in pw-dump output")

    def _capture_to_wav(self, target: str, stop_event: threading.Event) -> bytes:
        """Run pw-record against the sink monitor until stop_event, return WAV bytes."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)
        try:
            proc = subprocess.Popen(
                [
                    "pw-record",
                    "--target", target,
                    "--rate", str(_TARGET_RATE),
                    "--channels", "1",
                    "--format", "s16",
                    str(wav_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            while not stop_event.is_set():
                if proc.poll() is not None:  # pw-record died on its own
                    break
                time.sleep(0.05)
            proc.send_signal(signal.SIGINT)  # flush + finalize WAV header
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            return wav_path.read_bytes()
        finally:
            wav_path.unlink(missing_ok=True)

    def record(self, stop_event: threading.Event) -> bytes:
        target = self._default_sink_name(self._dump_pipewire())
        return self._capture_to_wav(target, stop_event)


_SCREENSHOTS_DIR = Path(__file__).parent.parent.parent / "screenshots"


class LinuxScreenshotBackend:
    """Discreet screenshots on GNOME Wayland via the XDG ScreenCast portal.

    start() negotiates a ScreenCast session (one consent dialog: the user picks
    a monitor) and keeps it alive. Each capture() opens a fresh PipeWire remote
    and runs a short-lived GStreamer pipeline that pulls exactly one PNG frame,
    then tears it down — no further dialogs. stop() closes the session.

    A per-capture pipeline is deliberate: a single long-lived pipewiresrc
    pipeline delivers the first frame fine but dies with `not-negotiated`
    (renegotiation the static pngenc chain can't follow) on later pulls, so
    "start once / capture many" against one pipeline breaks after frame 1.
    """

    def __init__(self) -> None:
        self._conn = None
        self._session_handle: str | None = None
        self._node_id: int | None = None

    def _build_pipeline_desc(self, fd: int, node_id: int) -> str:
        return (
            f"pipewiresrc fd={fd} path={node_id} ! videoconvert ! pngenc "
            f"! appsink name=sink max-buffers=1 drop=true"
        )

    # ── portal negotiation ────────────────────────────────────────────────────

    def _portal_call(self, conn, method, params, fd_list=None):
        """Call a ScreenCast portal method and block until its Response arrives.

        Portal methods return a Request object path and deliver the result later
        via a Response signal on that path; we subscribe first, then run a
        GLib main loop until it fires. Returns the response `results` dict.
        """
        from gi.repository import GLib, Gio

        loop = GLib.MainLoop()
        result = {}

        def on_response(_conn, _sender, path, _iface, _signal, parameters):
            response_code, results = parameters.unpack()
            result["code"] = response_code
            result["results"] = results
            loop.quit()

        # Subscribe to Response on any request path for this session, then call.
        sub_id = conn.signal_subscribe(
            "org.freedesktop.portal.Desktop",
            "org.freedesktop.portal.Request",
            "Response",
            None, None,
            Gio.DBusSignalFlags.NONE,
            on_response,
        )
        try:
            if fd_list is not None:
                conn.call_with_unix_fd_list_sync(
                    "org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop",
                    "org.freedesktop.portal.ScreenCast",
                    method, params, None, Gio.DBusCallFlags.NONE, -1, fd_list, None,
                )
            else:
                conn.call_sync(
                    "org.freedesktop.portal.Desktop",
                    "/org/freedesktop/portal/desktop",
                    "org.freedesktop.portal.ScreenCast",
                    method, params, None, Gio.DBusCallFlags.NONE, -1, None,
                )
            loop.run()
        finally:
            conn.signal_unsubscribe(sub_id)

        if result.get("code") != 0:
            raise RuntimeError(f"ScreenCast portal {method} denied or cancelled")
        return result["results"]

    def start(self) -> None:
        from gi.repository import GLib, Gio

        conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        # 1. CreateSession
        opts = {
            "handle_token": GLib.Variant("s", "phonexi_req0"),
            "session_handle_token": GLib.Variant("s", "phonexi_sess"),
        }
        res = self._portal_call(conn, "CreateSession", GLib.Variant("(a{sv})", (opts,)))
        self._session_handle = res["session_handle"]

        # 2. SelectSources — a single monitor
        sel_opts = {
            "handle_token": GLib.Variant("s", "phonexi_req1"),
            "types": GLib.Variant("u", 1),        # 1 = MONITOR
            "multiple": GLib.Variant("b", False),
            "cursor_mode": GLib.Variant("u", 2),  # 2 = embedded cursor
        }
        self._portal_call(
            conn, "SelectSources",
            GLib.Variant("(oa{sv})", (self._session_handle, sel_opts)),
        )

        # 3. Start — shows the consent dialog; returns the PipeWire stream node id
        start_opts = {"handle_token": GLib.Variant("s", "phonexi_req2")}
        start_res = self._portal_call(
            conn, "Start",
            GLib.Variant("(osa{sv})", (self._session_handle, "", start_opts)),
        )
        streams = start_res["streams"]

        # Session stays alive for the process; each capture() builds its own
        # pipeline against a fresh PipeWire fd (see class docstring).
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)

        self._conn = conn
        self._node_id = streams[0][0]

    def _open_pipewire_fd(self) -> int:
        """Open a fresh PipeWire remote fd for the live ScreenCast session."""
        from gi.repository import GLib, Gio

        fd_res, fd_list = self._conn.call_with_unix_fd_list_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.ScreenCast",
            "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (self._session_handle, {})),
            GLib.VariantType("(h)"),
            Gio.DBusCallFlags.NONE, -1, None, None,
        )
        return fd_list.get(fd_res.unpack()[0])

    @staticmethod
    def _drain_bus_error(pipeline) -> str | None:
        from gi.repository import Gst

        if pipeline is None:
            return None
        bus = pipeline.get_bus()
        msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.WARNING)
        if msg is None:
            return None
        err, debug = (msg.parse_error() if msg.type == Gst.MessageType.ERROR
                      else msg.parse_warning())
        return f"{err.message} | {debug}"

    def capture(self) -> Path:
        if self._conn is None or self._session_handle is None:
            raise RuntimeError("Screenshot backend not started — call start() first")

        from gi.repository import Gst

        fd = self._open_pipewire_fd()
        pipeline = Gst.parse_launch(self._build_pipeline_desc(fd, self._node_id))
        appsink = pipeline.get_by_name("sink")
        pipeline.set_state(Gst.State.PLAYING)
        try:
            ret, _, _ = pipeline.get_state(10 * Gst.SECOND)
            if ret == Gst.StateChangeReturn.FAILURE:
                err = self._drain_bus_error(pipeline)
                raise RuntimeError(f"ScreenCast pipeline failed to start: {err or 'unknown'}")

            sample = appsink.emit("try-pull-sample", 10 * Gst.SECOND)
            if sample is None:
                err = self._drain_bus_error(pipeline)
                raise RuntimeError(
                    "No frame available from ScreenCast stream"
                    + (f" — bus: {err}" if err else " (no bus error reported)")
                )

            buf = sample.get_buffer()
            ok, mapinfo = buf.map(Gst.MapFlags.READ)
            if not ok:
                raise RuntimeError("Failed to map ScreenCast frame buffer")
            try:
                png_bytes = bytes(mapinfo.data)
            finally:
                buf.unmap(mapinfo)
        finally:
            pipeline.set_state(Gst.State.NULL)

        _SCREENSHOTS_DIR.mkdir(exist_ok=True)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = _SCREENSHOTS_DIR / f"capture_{timestamp}.png"
        output_path.write_bytes(png_bytes)
        return output_path

    def stop(self) -> None:
        self._conn = None
        self._session_handle = None
        self._node_id = None


# Linux input-event-codes (from <linux/input-event-codes.h>)
KEY_ESC = 1
KEY_P = 25
KEY_RIGHTSHIFT = 54
KEY_RIGHTALT = 100

# evdev key event values
_KEY_UP = 0
_KEY_DOWN = 1
# value 2 is autorepeat — deliberately ignored so a held hotkey fires once.


class _EvdevKeyStateMachine:
    """Turns a stream of raw (keycode, value) events into hotkey callbacks.

    Right Shift + P -> on_screenshot; Right Alt + P -> on_audio_toggle; Esc -> on_close.
    Only key-down (value 1) triggers; autorepeat (2) is ignored so a held key
    fires once. Modifier state tracks its own down/up.
    """

    def __init__(self, on_screenshot, on_audio_toggle, on_close):
        self._on_screenshot = on_screenshot
        self._on_audio_toggle = on_audio_toggle
        self._on_close = on_close
        self._pressed: set[int] = set()

    def process(self, code: int, value: int) -> None:
        if value == _KEY_UP:
            self._pressed.discard(code)
            return
        if value != _KEY_DOWN:  # autorepeat or unknown
            return

        self._pressed.add(code)

        if code == KEY_ESC:
            self._on_close()
        elif code == KEY_P:
            if KEY_RIGHTSHIFT in self._pressed:
                self._on_screenshot()
            elif KEY_RIGHTALT in self._pressed:
                self._on_audio_toggle()


class LinuxInputBackend:
    """Global hotkey detection via evdev (/dev/input).

    Works under Wayland and X11 (reads keys straight from the kernel). Requires
    the user to be in the 'input' group. Reads all keyboard-capable devices so
    the hotkeys work regardless of which physical keyboard is used.
    """

    def _keyboard_devices(self):
        import evdev

        devices = []
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            caps = dev.capabilities().get(evdev.ecodes.EV_KEY, [])
            if KEY_P in caps and KEY_ESC in caps:
                devices.append(dev)
        return devices

    def run(
        self,
        on_screenshot: Callable[[], None],
        on_audio_toggle: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        import select

        import evdev

        sm = _EvdevKeyStateMachine(on_screenshot, on_audio_toggle, on_close)
        devices = self._keyboard_devices()
        if not devices:
            raise RuntimeError(
                "No readable keyboard device found. Add your user to the 'input' "
                "group (sudo usermod -aG input $USER) and log back in."
            )

        fd_to_device = {dev.fd: dev for dev in devices}
        while True:
            ready, _, _ = select.select(fd_to_device, [], [])
            for fd in ready:
                for event in fd_to_device[fd].read():
                    if event.type == evdev.ecodes.EV_KEY:
                        sm.process(event.code, event.value)
