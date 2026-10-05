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

    def __init__(self, root: tk.Tk, use_primary: bool = False) -> None:
        self._root = root
        self._use_primary = use_primary
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
        mon = self._target_monitor()
        x = mon["left"] + (mon["width"] - self._WIDTH) // 2
        y = mon["top"] + (mon["height"] - self._HEIGHT) // 2
        self._win.geometry(f"{self._WIDTH}x{self._HEIGHT}+{x}+{y}")

        self._drag_x = 0
        self._drag_y = 0
        for widget in (self._win, self._text):
            widget.bind("<ButtonPress-1>", self._on_drag_start, add="+")
            widget.bind("<B1-Motion>",     self._on_drag_motion, add="+")

    def _setup_tags(self) -> None:
        fn, fs = self._font
        self._text.tag_configure("status",   foreground="#6272a4")
        self._text.tag_configure("err",      foreground="#ff5555")
        self._text.tag_configure("h1",       foreground="#8be9fd", font=(fn, fs + 3, "bold"))
        self._text.tag_configure("h2",       foreground="#8be9fd", font=(fn, fs + 1, "bold"))
        self._text.tag_configure("h3",       foreground="#8be9fd", font=(fn, fs,     "bold"))
        # Bold is a highlighter, one colour per distinct term, so the two sides
        # of an "A vs B" answer can be told apart at a glance.
        for i, color in enumerate(self._HIGHLIGHTS):
            self._text.tag_configure(f"hl{i}", foreground="#282a36", background=color,
                                     font=(fn, fs, "bold"))
        # ==key phrase==: the words to say, always the same colour.
        self._text.tag_configure("key", foreground="#282a36", background=self._HIGHLIGHTS[0],
                                 font=(fn, fs, "bold"))
        # Bold that is not a compared term (a bullet label) stays plain bold.
        self._text.tag_configure("strong", foreground="#f8f8f2", font=(fn, fs, "bold"))
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
        self._text.tag_configure("divider", foreground="#8be9fd")

    def _target_monitor(self) -> dict:
        with mss.MSS() as sct:
            monitors = sct.monitors[1:]  # skip virtual combined (index 0)
            if self._use_primary:
                for mon in monitors:
                    if mon.get("is_primary", False):
                        return mon
                return monitors[0]  # fallback: single-display machine
            for mon in monitors:
                if not mon.get("is_primary", False):
                    return mon
            return monitors[0]  # fallback: single-display machine

    def _resolve_font(self) -> tuple:
        available = tkfont.families()
        for name in self._FONT_CANDIDATES:
            if name in available:
                return (name, 11)
        return ("Courier New", 11)

    # ── drag ────────────────────────────────────────────────────────────────

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self._win.winfo_x()
        self._drag_y = event.y_root - self._win.winfo_y()

    def _on_drag_motion(self, event: tk.Event) -> None:
        self._win.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

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

    _CODE_FENCE  = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    # The last group is a ==key phrase==; no space inside the marks, so an
    # equality like "a == b" in prose stays text.
    _INLINE_RE   = re.compile(r"\*\*(.*?)\*\*|\*(.*?)\*|`([^`]+)`|==(?=\S)(.+?)(?<=\S)==")
    _HEADING_RE  = re.compile(r"^(#{1,3})\s+(.*)")
    _DIVIDER_RE  = re.compile(r"^[-/]{3,}\s*$")
    _STAR_BULLET_RE = re.compile(r"^(\s*)\* ")
    # Dracula yellow, cyan, pink, green, orange.
    _HIGHLIGHTS  = ("#f1fa8c", "#8be9fd", "#ff79c6", "#50fa7b", "#ffb86c")

    def _highlight_tag(self, term: str) -> str:
        # "TCP", "tcp" and "TCP:" are the same term and share a colour.
        key = term.strip().rstrip(":").strip().lower()
        if key not in self._term_colors:
            self._term_colors[key] = len(self._term_colors) % len(self._HIGHLIGHTS)
        return f"hl{self._term_colors[key]}"

    def _render_markdown(self, text: str) -> None:
        self._term_colors: dict[str, int] = {}
        # An answer that marks key phrases is not a comparison, so its bold is a
        # label and gets no colour; only comparisons colour bold per term.
        prose = self._CODE_FENCE.sub("", text)
        self._has_key_phrases = any(m.group(4) for m in self._INLINE_RE.finditer(prose))
        last = 0
        for m in self._CODE_FENCE.finditer(text):
            self._render_prose(text[last:m.start()])
            self._render_code_block(m.group(1) or "text", m.group(2))
            last = m.end()
        self._render_prose(text[last:])

    def _render_prose(self, text: str) -> None:
        for line in text.split("\n"):
            if self._DIVIDER_RE.match(line):
                self._ins(line + "\n", "divider")
                continue
            hm = self._HEADING_RE.match(line)
            if hm:
                level = len(hm.group(1))
                tag = f"h{level}"
                self._ins(hm.group(2) + "\n", tag)
                continue
            # A '* ' bullet would open an italic run and swallow the bold after it.
            line = self._STAR_BULLET_RE.sub(r"\1- ", line)
            pos = 0
            for m in self._INLINE_RE.finditer(line):
                if m.start() > pos:
                    self._ins(line[pos:m.start()])
                if m.group(1) is not None:
                    # Models nest code or italics in bold (**`acks=all`:**,
                    # **(*key salting*)**); the highlight already marks it.
                    term = m.group(1).replace("`", "").replace("*", "")
                    tag = "strong" if self._has_key_phrases else self._highlight_tag(term)
                    self._ins(term, tag)
                elif m.group(2) is not None:
                    self._ins(m.group(2), "italic")
                elif m.group(3) is not None:
                    self._ins(m.group(3), "icode")
                else:
                    self._ins(m.group(4).replace("`", "").replace("*", ""), "key")
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
        self.show_and_collect(iterator)

    def show_and_collect(self, iterator: Iterator[str],
                         status: str = "Analyzing screenshot...") -> str:
        result: list[str] = []
        done = threading.Event()
        self._root.after(0, self._ins, f"> {status}\n", "status")

        def _stream() -> None:
            buf: list[str] = []
            try:
                for token in iterator:
                    # Raw text now, formatting at the end: waiting for the last
                    # token hid a first word that arrives in ~1.5 s behind a
                    # blank popup for the whole answer.
                    self._root.after(0, self._append_live, token, not buf)
                    buf.append(token)
            except Exception as exc:
                self._root.after(0, self._ins, f"\n[error: {exc}]", "err")
                done.set()
                return
            full = "".join(buf)
            result.append(full)
            self._root.after(0, self._do_render, full)
            done.set()

        threading.Thread(target=_stream, daemon=True).start()
        done.wait()
        return result[0] if result else ""

    def _clear(self) -> bool:
        """Empty the widget. False when the popup is already gone.

        The answer can land long after the window closed — a CLI engine takes
        9 to 30 seconds, so Escape or a second capture lands mid-stream often.
        """
        try:
            self._text.configure(state=tk.NORMAL)
            self._text.delete("1.0", tk.END)
            self._text.configure(state=tk.DISABLED)
            return True
        except tk.TclError:
            return False

    def _append_live(self, token: str, first: bool) -> None:
        # The first token replaces the "Analyzing" status line.
        if first and not self._clear():
            return
        self._ins(token)

    def _do_render(self, text: str) -> None:
        if not self._clear():
            return
        self._render_markdown(text)
        try:
            self._text.see("1.0")
        except tk.TclError:
            pass

    def show_status(self, msg: str) -> None:
        if not self._clear():
            return
        self._ins(f"> {msg}\n", "status")

    def show_error(self, msg: str) -> None:
        self._ins(f"> {msg}", "err")

    def close(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass
