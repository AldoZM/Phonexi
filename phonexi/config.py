import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
PROMPT = (
    "Respond in the same language as the question. "
    "Be direct and clear — no filler, no greetings, no summaries. "
    "Give enough detail to fully understand the answer, but nothing extra. "
    "Include code when relevant."
)
