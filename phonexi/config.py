import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# Vision model: only Groq free-tier model that accepts images (screenshot mode).
GROQ_MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
# Text model: larger, more human/precise wording (text + audio mode).
GROQ_MODEL_TEXT = "llama-3.3-70b-versatile"
# Backward-compatible alias (vision model) — used by process() and tests.
GROQ_MODEL = GROQ_MODEL_VISION

PROMPT = (
    "Answer this technical interview question as a strong senior developer would — "
    "directly and precisely, the way a knowledgeable person explains to a peer.\n"
    "Rules:\n"
    "- Respond in the SAME language as the question.\n"
    "- Lead with the answer. No greetings, no filler, no 'in summary', "
    "no restating the question.\n"
    "- Sound human and natural, not robotic or academic. Confident, not hedgy.\n"
    "- Bold the key terms and concepts (**like this**) so they stand out at a glance.\n"
    "- Be concise: say what matters and stop. Length matches the question's depth. "
    "Do NOT add a closing recap or conclusion. Never start a sentence with "
    "'En resumen', 'En conclusión', 'In summary', 'In conclusion' or similar — "
    "end on the last real point.\n"
    "- Always explain in prose FIRST, then put any code block at the END. "
    "Never start with code before the explanation.\n"
    "- Code: comment only the non-obvious parts and the WHY, not every line. "
    "Comments in the question's language.\n"
    "- ONLY if the input literally contains several distinct questions, split them into "
    "numbered sections ('1.', '2.') divided by '---'. A single question = ONE answer, "
    "no numbering, no '---'."
)
