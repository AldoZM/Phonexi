import re
import threading
import tkinter as tk
import tkinter.font as tkfont
from typing import Iterator

import mss
from pygments import lex
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token


class ResultWindow:
    _BG = "#0d0d0d"
    _CODE_BG = "#141414"
    _FG = "#e0e0e0"
    _ERR_FG = "#ff5555"
    _WIDTH = 740
    _HEIGHT = 500
    _FONT_CANDIDATES = ("Cascadia Code", "Consolas", "Courier New")

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._win = tk.Toplevel(root)
        self._win.title("Phonexi")
        self._win.configure(bg=self._BG)
        self._win.attributes("-topmost", True)
        self._win.overrideredirect(True)
        self._win.bind("<Escape>", lambda _: self._win.destroy())

        self._font = self._resolve_font()

        self._text = tk.Text(
            self._win,
            bg=self._BG,
            fg=self._FG,
            font=self._font,
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=14,
            pady=14,
            insertbackground=self._FG,
            cursor="arrow",
            spacing1=2,
            spacing3=2,
        )
        self._text.pack(fill=tk.BOTH, expand=True)
        self._setup_tags()

        self._win.update_idletasks()
        mon = self._secondary_monitor()
        x = mon["left"] + (mon["width"] - self._WIDTH) // 2
        y = mon["top"] + (mon["height"] - self._HEIGHT) // 2
        self._win.geometry(f"{self._WIDTH}x{self._HEIGHT}+{x}+{y}")

    def _setup_tags(self) -> None:
        fn, fs = self._font
        self._text.tag_configure("status",   foreground="#6272a4")
        self._text.tag_configure("err",      foreground="#ff5555")
        self._text.tag_configure("h1",       foreground="#8be9fd", font=(fn, fs + 3, "bold"))
        self._text.tag_configure("h2",       foreground="#8be9fd", font=(fn, fs + 1, "bold"))
        self._text.tag_configure("h3",       foreground="#8be9fd", font=(fn, fs,     "bold"))
        self._text.tag_configure("bold",     foreground="#ffffff",  font=(fn, fs,     "bold"))
        self._text.tag_configure("italic",   foreground="#f8f8f2",  font=(fn, fs,     "italic"))
        self._text.tag_configure("icode",    foreground="#50fa7b",  background="#1c1c1c")
        self._text.tag_configure("code_bg",  background=self._CODE_BG,
                                 lmargin1=10, lmargin2=10, rmargin=10)
        # Syntax colours (Dracula-inspired)
        self._text.tag_configure("s_kw",    foreground="#ff79c6")
        self._text.tag_configure("s_str",   foreground="#f1fa8c")
        self._text.tag_configure("s_cmt",   foreground="#6272a4")
        self._text.tag_configure("s_num",   foreground="#bd93f9")
        self._text.tag_configure("s_func",  foreground="#50fa7b")
        self._text.tag_configure("s_cls",   foreground="#8be9fd")
        self._text.tag_configure("s_op",    foreground="#ff79c6")
        self._text.tag_configure("s_bi",    foreground="#8be9fd")
        self._text.tag_configure("s_dec",   foreground="#50fa7b")

    def _secondary_monitor(self) -> dict:
        with mss.mss() as sct:
            monitors = sct.monitors
            if len(monitors) > 2:
                return monitors[2]
            return monitors[1]

    def _resolve_font(self) -> tuple:
        available = tkfont.families()
        for name in self._FONT_CANDIDATES:
            if name in available:
                return (name, 11)
        return ("Courier New", 11)

    # ── low-level insert ────────────────────────────────────────────────────

    def _ins(self, text: str, *tags) -> None:
        try:
            self._text.configure(state=tk.NORMAL)
            self._text.insert(tk.END, text, tags if tags else "")
            self._text.see(tk.END)
            self._text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    # ── markdown renderer ────────────────────────────────────────────────────

    _CODE_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    _INLINE_RE  = re.compile(r"\*\*(.*?)\*\*|\*(.*?)\*|`([^`]+)`")
    _HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)")

    def _render_markdown(self, text: str) -> None:
        last = 0
        for m in self._CODE_FENCE.finditer(text):
            self._render_prose(text[last:m.start()])
            self._render_code_block(m.group(1) or "text", m.group(2))
            last = m.end()
        self._render_prose(text[last:])

    def _render_prose(self, text: str) -> None:
        for line in text.split("\n"):
            hm = self._HEADING_RE.match(line)
            if hm:
                level = len(hm.group(1))
                tag = f"h{level}"
                self._ins(hm.group(2) + "\n", tag)
                continue
            pos = 0
            for m in self._INLINE_RE.finditer(line):
                if m.start() > pos:
                    self._ins(line[pos:m.start()])
                if m.group(1) is not None:
                    self._ins(m.group(1), "bold")
                elif m.group(2) is not None:
                    self._ins(m.group(2), "italic")
                else:
                    self._ins(m.group(3), "icode")
                pos = m.end()
            if pos < len(line):
                self._ins(line[pos:])
            self._ins("\n")

    def _render_code_block(self, lang: str, code: str) -> None:
        self._ins("\n")
        try:
            lexer = get_lexer_by_name(lang, stripall=False)
        except Exception:
            lexer = TextLexer()

        _MAP = {
            Token.Keyword:          "s_kw",
            Token.Keyword.Type:     "s_kw",
            Token.Name.Function:    "s_func",
            Token.Name.Class:       "s_cls",
            Token.Name.Decorator:   "s_dec",
            Token.Name.Builtin:     "s_bi",
            Token.Literal.String:   "s_str",
            Token.Literal.Number:   "s_num",
            Token.Comment:          "s_cmt",
            Token.Operator:         "s_op",
        }

        self._text.configure(state=tk.NORMAL)
        for ttype, value in lex(code, lexer):
            tag = None
            for base, t in _MAP.items():
                if ttype in base:
                    tag = t
                    break
            if tag:
                self._text.insert(tk.END, value, (tag, "code_bg"))
            else:
                self._text.insert(tk.END, value, "code_bg")
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)
        self._ins("\n")

    # ── public API ───────────────────────────────────────────────────────────

    def show(self, iterator: Iterator[str]) -> None:
        self._root.after(0, self._ins, "> Analyzing screenshot...\n", "status")

        def _stream() -> None:
            buf: list[str] = []
            try:
                for token in iterator:
                    buf.append(token)
            except Exception as exc:
                self._root.after(0, self._ins, f"\n[error: {exc}]", "err")
                return
            self._root.after(0, self._do_render, "".join(buf))

        threading.Thread(target=_stream, daemon=True).start()

    def _do_render(self, text: str) -> None:
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.configure(state=tk.DISABLED)
        self._render_markdown(text)

    def show_status(self, msg: str) -> None:
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.configure(state=tk.DISABLED)
        self._ins(f"> {msg}\n", "status")

    def show_error(self, msg: str) -> None:
        self._ins(f"> {msg}", "err")
