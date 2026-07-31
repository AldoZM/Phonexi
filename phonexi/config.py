import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# Text model — used by all modes. Screenshot mode OCRs the image (tesseract) and
# sends the extracted text here; Groq no longer offers a free-tier vision model.
GROQ_MODEL_TEXT = "llama-3.3-70b-versatile"
# Backward-compatible alias.
GROQ_MODEL = GROQ_MODEL_TEXT

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
    "- Be concise and direct. No filler, no restating the problem, no closing summary."
)
