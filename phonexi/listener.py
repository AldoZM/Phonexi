import threading

from phonexi.audio import record, transcribe
from phonexi.backends import get_input_backend, get_screenshot_backend
from phonexi.processor import Context, GroqAPIError, GroqNotConfiguredError, process, process_text
from phonexi.ui import ResultWindow


class HotkeyListener:
    def __init__(self, tk_root=None, use_primary: bool = False, view_factory=None,
                 input_backend=None, screenshot_backend=None) -> None:
        self._tk_root = tk_root
        self._use_primary = use_primary
        self._view_factory = view_factory or (
            lambda: ResultWindow(self._tk_root, use_primary=self._use_primary)
        )
        self._input_backend = input_backend or get_input_backend()
        self._screenshot_backend = screenshot_backend or get_screenshot_backend()
        self._current_window = None

        self._recording = False
        self._record_stop: threading.Event | None = None
        self._context: Context | None = None

    def _schedule(self, fn, *args) -> None:
        if self._tk_root is not None:
            self._tk_root.after(0, fn, *args)
        else:
            fn(*args)

    # ── hotkey callbacks (invoked by the input backend) ──────────────────────

    def _on_close(self) -> None:
        self._schedule(self._close_current)

    def _on_audio_toggle(self) -> None:
        if self._recording:
            self._on_audio_stop()
        else:
            self._on_audio_start()

    # ── screenshot flow (Right Shift + P) ───────────────────────────────────

    def _on_screenshot_hotkey(self) -> None:
        self._schedule(self._start_capture)

    def _start_capture(self) -> None:
        self._close_current()
        path = self._screenshot_backend.capture()
        win = self._view_factory()
        self._current_window = win
        threading.Thread(target=self._stream_image, args=(path, win), daemon=True).start()

    def _stream_image(self, path, win) -> None:
        try:
            response = win.show_and_collect(process(path))
            if response:
                self._context = Context(
                    user_turn="[Screenshot of interview question]",
                    assistant_turn=response,
                )
        except GroqNotConfiguredError:
            self._schedule(win.show_error, "GROQ_API_KEY not set — add it to .env")
        except GroqAPIError as exc:
            self._schedule(win.show_error, f"Groq error: {exc}")
        except Exception as exc:
            self._schedule(win.show_error, f"Error: {exc}")

    # ── audio flow (Right Alt + P, toggle) ──────────────────────────────────

    def _on_audio_start(self) -> None:
        self._recording = True
        self._record_stop = threading.Event()
        self._schedule(self._open_recording_popup)
        threading.Thread(
            target=self._record_worker,
            args=(self._record_stop,),
            daemon=True,
        ).start()

    def _open_recording_popup(self) -> None:
        self._close_current()
        win = self._view_factory()
        self._current_window = win
        win.show_status("🎙 Listening...")

    def _on_audio_stop(self) -> None:
        if self._record_stop:
            self._record_stop.set()
        self._recording = False

    def _record_worker(self, stop_event: threading.Event) -> None:
        try:
            wav_bytes = record(stop_event)
        except Exception as exc:
            win = self._current_window
            if win:
                self._schedule(win.show_error, f"Audio capture error: {exc}")
            return

        win = self._current_window
        if win is None:
            return

        self._schedule(win.show_status, "⏳ Analyzing...")

        try:
            text = transcribe(wav_bytes)
        except Exception as exc:
            if win is self._current_window:
                self._schedule(win.show_error, f"Transcription error: {exc}")
            return

        if not text:
            if win is self._current_window:
                self._schedule(win.show_error, "No speech detected")
            return

        if win is self._current_window:
            self._schedule(win.show_status, f"❓ {text}\n")
        try:
            response = win.show_and_collect(process_text(text, context=self._context))
            if response:
                self._context = Context(user_turn=text, assistant_turn=response)
        except GroqNotConfiguredError:
            self._schedule(win.show_error, "GROQ_API_KEY not set — add it to .env")
        except GroqAPIError as exc:
            self._schedule(win.show_error, f"Groq error: {exc}")
        except Exception as exc:
            self._schedule(win.show_error, f"Error: {exc}")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _close_current(self) -> None:
        if self._current_window is not None:
            try:
                self._current_window.close()
            except Exception:
                pass
            self._current_window = None

    def start(self) -> None:
        self._screenshot_backend.start()
        try:
            self._input_backend.run(
                self._on_screenshot_hotkey,
                self._on_audio_toggle,
                self._on_close,
            )
        finally:
            self._screenshot_backend.stop()
