import threading
from pynput import keyboard

from phonexi.audio import record, transcribe
from phonexi.processor import GroqAPIError, GroqNotConfiguredError, process, process_text
from phonexi.screenshot import capture
from phonexi.ui import ResultWindow


class HotkeyListener:
    _TRIGGER_CHAR = "p"
    _SCREENSHOT_MOD = keyboard.Key.shift_r   # Right Shift + P → screenshot
    _AUDIO_MOD      = keyboard.Key.alt_r     # Right Alt   + P → push-to-talk

    def __init__(self, tk_root) -> None:
        self._tk_root = tk_root
        self._pressed: set = set()
        self._lock = threading.Lock()
        self._current_window = None

        self._recording = False
        self._record_stop: threading.Event | None = None

    # ── key events ──────────────────────────────────────────────────────────

    def _on_press(self, key) -> None:
        with self._lock:
            self._pressed.add(key)

        p_down = self._p_held()

        if self._SCREENSHOT_MOD in self._pressed and p_down:
            self._on_screenshot_hotkey()
        elif self._AUDIO_MOD in self._pressed and p_down and not self._recording:
            self._on_audio_start()

    def _on_release(self, key) -> None:
        with self._lock:
            self._pressed.discard(key)

        released_audio_key = key in (self._AUDIO_MOD,) or (
            hasattr(key, "char") and key.char and key.char.lower() == self._TRIGGER_CHAR
        )
        if self._recording and released_audio_key:
            self._on_audio_stop()

    def _p_held(self) -> bool:
        return any(
            hasattr(k, "char") and k.char and k.char.lower() == self._TRIGGER_CHAR
            for k in self._pressed
        )

    # ── screenshot flow (Right Shift + P) ───────────────────────────────────

    def _on_screenshot_hotkey(self) -> None:
        self._tk_root.after(0, self._start_capture)

    def _start_capture(self) -> None:
        self._close_current()
        path = capture()
        win = ResultWindow(self._tk_root)
        self._current_window = win
        threading.Thread(target=self._stream_image, args=(path, win), daemon=True).start()

    def _stream_image(self, path, win) -> None:
        try:
            win.show(process(path))
        except GroqNotConfiguredError:
            self._tk_root.after(0, win.show_error, "GROQ_API_KEY not set — add it to .env")
        except GroqAPIError as exc:
            self._tk_root.after(0, win.show_error, f"Groq error: {exc}")
        except Exception as exc:
            self._tk_root.after(0, win.show_error, f"Error: {exc}")

    # ── audio flow (Right Alt + P, push-to-talk) ────────────────────────────

    def _on_audio_start(self) -> None:
        self._recording = True
        self._record_stop = threading.Event()
        self._tk_root.after(0, self._open_recording_popup)
        threading.Thread(
            target=self._record_worker,
            args=(self._record_stop,),
            daemon=True,
        ).start()

    def _open_recording_popup(self) -> None:
        self._close_current()
        win = ResultWindow(self._tk_root)
        self._current_window = win
        win.show_status("🎙 Recording… release Alt+P to send")

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
                self._tk_root.after(0, win.show_error, f"Audio capture error: {exc}")
            return

        win = self._current_window
        if win is None:
            return

        self._tk_root.after(0, win.show_status, "⏳ Transcribing…")

        try:
            text = transcribe(wav_bytes)
        except Exception as exc:
            self._tk_root.after(0, win.show_error, f"Transcription error: {exc}")
            return

        if not text:
            self._tk_root.after(0, win.show_error, "No speech detected")
            return

        self._tk_root.after(0, win.show_status, f"❓ {text}\n")
        try:
            win.show(process_text(text))
        except GroqNotConfiguredError:
            self._tk_root.after(0, win.show_error, "GROQ_API_KEY not set — add it to .env")
        except GroqAPIError as exc:
            self._tk_root.after(0, win.show_error, f"Groq error: {exc}")
        except Exception as exc:
            self._tk_root.after(0, win.show_error, f"Error: {exc}")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _close_current(self) -> None:
        if self._current_window is not None:
            try:
                self._current_window._win.destroy()
            except Exception:
                pass
            self._current_window = None

    def start(self) -> None:
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
