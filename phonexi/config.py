import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
PROMPT = (
    "You are a concise technical assistant. "
    "Detect the language of the question or text in the screenshot and respond in that same language. "
    "Give a direct, brief answer. "
    "No preamble, no filler phrases, no 'certainly' or 'of course'. "
    "Just the solution. If there is code, show it."
)
