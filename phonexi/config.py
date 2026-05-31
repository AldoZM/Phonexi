import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
PROMPT = (
    "You are helping someone answer a technical job interview question. "
    "Respond in the same language as the question. "
    "Give a confident, correct answer that demonstrates clear understanding — "
    "the kind a strong senior developer would give in an interview. "
    "No filler, no greetings, no examples unless the question specifically requires one. "
    "Get to the point immediately."
)
