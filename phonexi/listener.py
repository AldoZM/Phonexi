import threading
from pynput import keyboard

from phonexi.audio import record, transcribe
from phonexi.processor import Context, GroqAPIError, GroqNotConfiguredError, process, process_text
from phonexi.screenshot import capture
from phonexi.ui import ResultWindow


class HotkeyListener:
    _TRIGGER_CHAR = "p"
    _SCREENSHOT_MOD = keyboard.Key.shift_r   # Right Shift + P → screenshot
    _AUDIO_MOD      = keyboard.Key.alt_gr    # Right Alt   + P → toggle recording

    def __init__(self, tk_root=None, use_primary: bool = False, view_factory=None) -> None:
        self._tk_root = tk_root
        self._use_primary = use_primary
        self._view_factory = view_factory or (
            lambda: ResultWindow(self._tk_root, use_primary=self._use_primary)
        )
        self._pressed: set = set()
        self._lock = threading.Lock()
        self._current_window = None

        self._recording = False
        self._record_stop: threading.Event | None = None
        self._hotkey_cooldown = False
        self._screenshot_cooldown = False
        self._context: Context | None = None

    def _schedule(self, fn, *args) -> None:
        if self._tk_root is not None:
            self._tk_root.after(0, fn, *args)
        else:
            fn(*args)

    # ── key events ──────────────────────────────────────────────────────────

    def _on_press(self, key) -> None:
        with self._lock:
            self._pressed.add(key)

        if key == keyboard.Key.esc:
            self._schedule(self._close_current)
            return

        # Only trigger when P itself is pressed — avoids firing on modifier-only press
        if not self._is_p(key):
            return

        if self._SCREENSHOT_MOD in self._pressed and not self._screenshot_cooldown:
            self._screenshot_cooldown = True
            self._on_screenshot_hotkey()
        elif self._AUDIO_MOD in self._pressed and not self._hotkey_cooldown:
            self._hotkey_cooldown = True
            if self._recording:
                self._on_audio_stop()
            else:
                self._on_audio_start()

    def _on_release(self, key) -> None:
        with self._lock:
            self._pressed.discard(key)

        if key == self._SCREENSHOT_MOD:
            self._screenshot_cooldown = False
        if key == self._AUDIO_MOD:
            self._hotkey_cooldown = False

    _P_VK = 80  # Virtual key code for 'P' on Windows (used when AltGr suppresses char)

    def _is_p(self, key) -> bool:
        """True if the given key event is the P key."""
        return (
            (hasattr(key, "char") and key.char and key.char.lower() == self._TRIGGER_CHAR)
            or (hasattr(key, "vk") and key.vk == self._P_VK)
        )

    # ── screenshot flow (Right Shift + P) ───────────────────────────────────

    def _on_screenshot_hotkey(self) -> None:
        self._schedule(self._start_capture)

    def _start_capture(self) -> None:
        self._close_current()
        path = capture()
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
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
