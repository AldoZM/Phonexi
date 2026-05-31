import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
PROMPT = (
    "Extract the code from this screenshot. "
    "Identify the problem or question. "
    "Provide a concise solution."
)
