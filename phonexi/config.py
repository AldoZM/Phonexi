import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
PROMPT = (
    "Respond in the same language as the question. "
    "Be extremely brief. Answer only what is asked. "
    "No greetings, no explanations of what you are about to do, no summaries at the end. "
    "Code only when needed. One sentence max for simple questions."
)
