import threading
import tkinter as tk
import tkinter.font as tkfont
from typing import Iterator


class ResultWindow:
    _FONT_CANDIDATES = ("Cascadia Code", "Consolas", "Courier New")
    _BG = "#0d0d0d"
    _FG = "#e0e0e0"
    _ERR_FG = "#ff5555"
    _WIDTH = 700
    _HEIGHT = 480

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._win = tk.Toplevel(root)
        self._win.title("Phonexi")
        self._win.configure(bg=self._BG)
        self._win.attributes("-topmost", True)
        self._win.bind("<Escape>", lambda _: self._win.destroy())
        self._win.protocol("WM_DELETE_WINDOW", self._win.destroy)

        font = self._resolve_font()
        self._text = tk.Text(
            self._win,
            bg=self._BG,
            fg=self._FG,
            font=font,
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=12,
            pady=12,
            insertbackground=self._FG,
        )
        self._text.tag_configure("err", foreground=self._ERR_FG)
        self._text.pack(fill=tk.BOTH, expand=True)

        self._win.update_idletasks()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x = (sw - self._WIDTH) // 2
        y = (sh - self._HEIGHT) // 2
        self._win.geometry(f"{self._WIDTH}x{self._HEIGHT}+{x}+{y}")

    def _resolve_font(self) -> tuple:
        available = tkfont.families()
        for name in self._FONT_CANDIDATES:
            if name in available:
                return (name, 11)
        return ("Courier New", 11)

    def _insert(self, text: str, tag: str = "") -> None:
        self._text.configure(state=tk.NORMAL)
        if tag:
            self._text.insert(tk.END, text, tag)
        else:
            self._text.insert(tk.END, text)
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)

    def show(self, iterator: Iterator[str]) -> None:
        self._root.after(0, self._insert, "> Analyzing screenshot...\n\n")

        def _stream() -> None:
            try:
                for token in iterator:
                    self._root.after(0, self._insert, token)
            except Exception as exc:
                self._root.after(0, self._insert, f"\n[error: {exc}]")

        threading.Thread(target=_stream, daemon=True).start()

    def show_error(self, msg: str) -> None:
        self._insert(f"> {msg}", "err")
