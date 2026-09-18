"""Section selection for the prior-context file (-c/--context).

The whole ficha costs ~4,200 tokens on every call and Groq's free tier allows
8,000 per minute, so sending it whole means one question per minute. A question
about consumer lag needs two or three of its thirteen sections, not all of them.
This module picks those and drops the rest, keeping the usage rules that sit
above the first section — they are what stop the model from answering with the
nearest topic instead of the one asked about.
"""

import re
import unicodedata

# Roughly 1,300 tokens of ficha at the measured 4.48 characters per token,
# which leaves room for the system prompt, the question and the answer.
MAX_CHARS = 6_000

# A section header is a separator line, a numbered title, another separator.
# Requiring the number keeps the banner at the top of the file out: it carries
# no number, so it stays in the preamble together with the usage rules, which
# are the part that stops the model from answering with the nearest topic.
# A ficha with unnumbered sections matches nothing and is sent whole — less
# saving, but never a silently truncated context.
_HEADER = re.compile(r"^={40,}\n(\d+\.[^\n]*)\n={40,}$", re.MULTILINE)

_WORD = re.compile(r"[a-z0-9]+")

# Words too common in a Spanish or English question to say anything about which
# section answers it.
_STOPWORDS = frozenset("""
que cual cuales como cuando donde quien porque por para con sin sobre entre
del las los una uno unos unas eso esa ese esta este esto estos estas
tus tus mis sus nos les lee dime hablame cuentame explicame
son ser estar tiene tienen hace hacen hizo hiciste haces puedes puede
mas menos muy tan tanto todo toda todos todas algo alguna alguno
the what which how when where who why for with without about from
you your are was were did does have has had can could would should
and but not any all some this that these those there their
""".split())


def _fold(text: str) -> str:
    """Lowercase and strip accents so 'INDICES' matches 'índices'."""
    stripped = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in stripped if unicodedata.category(c) != "Mn")


def _words(text: str) -> set:
    return {
        w for w in _WORD.findall(_fold(text))
        if len(w) >= 3 and w not in _STOPWORDS
    }


def select(briefing: str, question: str, max_chars: int = MAX_CHARS) -> str:
    """Return the preamble plus the sections that answer `question`.

    A briefing without section headers is returned unchanged: there is nothing
    to choose between, and truncating it would cut mid-sentence.
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")

    headers = list(_HEADER.finditer(briefing))
    if not headers:
        return briefing

    preamble = briefing[:headers[0].start()]

    sections = []
    for i, header in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(briefing)
        sections.append((i, header.group(1).strip(), briefing[header.start():end]))

    asked = _words(question)
    scored = sorted(
        (
            # A hit in the title says more than a hit buried in the body.
            -(len(asked & _words(title)) * 2 + len(asked & _words(text))),
            order,
            text,
        )
        for order, title, text in sections
    )

    # Only sections the question actually touches. Carrying the rest along
    # because there is budget left would defeat the point of choosing.
    ranked = [s for s in scored if s[0] < 0]
    if not ranked:
        # Nothing matched — a greeting, or a topic the ficha does not cover.
        # Document order puts the profile and the projects first.
        ranked = sorted(scored, key=lambda s: s[1])

    budget = max_chars - len(preamble)
    chosen = []
    for _, order, text in ranked:
        if len(text) <= budget:
            chosen.append((order, text))
            budget -= len(text)

    chosen.sort()
    return (preamble + "".join(text for _, text in chosen)).strip()
