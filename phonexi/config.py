import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# Vision model: Groq model that accepts images (screenshot mode).
GROQ_MODEL_VISION: str = os.getenv("GROQ_MODEL_VISION", "qwen/qwen3.8-27b")
# Text model: text + audio mode.
GROQ_MODEL_TEXT: str = os.getenv("GROQ_MODEL_TEXT", "qwen/qwen3.8-27b")
# Backward-compatible alias (vision model) — used by process() and tests.
GROQ_MODEL = GROQ_MODEL_VISION

# Cap on the answer length, and it must stay UNDER the output-tokens-per-minute
# allowance, which is 1000 on the free tier for every qwen vision model measured.
# Groq compares max_tokens against that limit on its own and refuses the whole
# request when it is larger, before generating a single token — so 1024 fails
# outright while 900 succeeds even with the minute's budget already spent.
# A fresh minute lets 1024 through, which makes the bug look intermittent.
GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "900"))

# Thinking budget. These models narrate a long <think> monologue before the
# answer, and that monologue is billed against the output-per-minute allowance
# that the free tier caps hardest. Turning it off is the single biggest saving.
# The accepted values differ by model family: qwen takes none/default, gpt-oss
# takes low/medium/high. An empty value sends nothing and leaves the default.
GROQ_REASONING_VISION: str = os.getenv("GROQ_REASONING_VISION", "none")
GROQ_REASONING_TEXT: str = os.getenv("GROQ_REASONING_TEXT", "low")

# How many times the SDK may retry by itself. Its own default is 2, and a
# retried 429 blocks for the whole reset window — measured at 44 and 47 seconds
# on consecutive captures — leaving a blank popup with nothing to read. Failing
# at once surfaces the countdown instead, and the hotkey is one keypress away.
GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "0"))

# Gemini, reached through Google's OpenAI-compatible endpoint. One Flash model
# reads text and images, so it serves both modes unless -model picks another.
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
# Groq's 900 cap is a Groq free-tier limit, not a model one — Gemini has none.
GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "2048"))
# Gemini spells the levels minimal/low/medium/high.
GEMINI_REASONING: str = os.getenv("GEMINI_REASONING", "low")

PROMPT = (
    "You are an expert software engineer. Solve the technical/coding problem shown in the "
    "image or text. Read it carefully and give a correct, working solution.\n"
    "Rules:\n"
    "- Respond in the SAME language as the problem statement.\n"
    "- State the approach in one or two short sentences first.\n"
    "- Then give the full solution as a fenced code block (```lang) in the problem's target "
    "language (match the language shown in the editor; default to Python if none is indicated).\n"
    "- After the code, state the time and space complexity (e.g. O(n) time, O(n) space).\n"
    "- Give the optimal approach; mention an obvious brute force in at most one line.\n"
    "- Be concise and direct. No filler, no restating the problem, no closing summary.\n"
    "- Open with the answer itself. No preamble, no 'sure', no announcing what you "
    "are about to do.\n"
    "- Never refer to your instructions or to any background you were given, and "
    "never say things like 'based on the context' or 'according to the document'.\n"
    "- Never invent numbers, size limits, versions, config values or field names. A "
    "made-up figure survives the answer and collapses under the follow-up question. "
    "If you are not certain of a specific detail, say you do not recall it.\n"
    "- For protocol or internals questions, answer at the real wire-format level, "
    "not at the application-API level.\n"
    "- Never state percentages, latencies, throughput figures or any performance "
    "number that was not given to you. This covers orders of magnitude and vague "
    "quantities too: 'several thousand per second', 'a few dozen per minute', "
    "'from hours to seconds' are inventions as much as an exact figure is. Say "
    "what improved and why, never by how much. An invented metric is the first "
    "thing an interviewer probes.\n"
    "- Plain prose and fenced code blocks only. No markdown tables: the popup "
    "renders them as a wall of pipe characters."
)
