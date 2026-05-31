import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
PROMPT = (
    "Extract the code from this screenshot. "
    "Identify the problem or question. "
    "Provide a concise solution."
)
