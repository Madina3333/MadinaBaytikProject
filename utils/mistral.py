# utils/mistral.py
import os
import httpx
import math
from typing import List

MISTRAL_API_KEY = "9K6hr7S7RwzCFgCddK7MJ4T3FuFP089s"
EMBEDDING_MODEL = "mistral-embed"
MISTRAL_API_URL = "https://api.mistral.ai/v1/embeddings"


async def get_embedding(text: str) -> List[float]:

    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY не установлен. Проверьте файл .env")

    text = text[:2000].strip()
    if not text:
        text = " "

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            MISTRAL_API_URL,
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": text,
            }
        )
        if response.status_code != 200:
            raise RuntimeError(f"Mistral API error: {response.status_code} – {response.text}")

        data = response.json()
        return data["data"][0]["embedding"]


def cosine_similarity(a: List[float], b: List[float]) -> float:

    if len(a) != len(b):
        raise ValueError("Векторы должны быть одинаковой длины")

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)