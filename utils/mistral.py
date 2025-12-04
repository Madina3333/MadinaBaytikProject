# utils/mistral.py
import os
import httpx
from typing import List, Optional

MISTRAL_API_KEY = "9K6hr7S7RwzCFgCddK7MJ4T3FuFP089s"
CHAT_MODEL = "mistral-large-latest"  # или "open-mistral-7b" для бесплатного

async def extract_interests_from_bio(bio: str) -> Optional[str]:
    if not MISTRAL_API_KEY:
        print("❌ MISTRAL_API_KEY не задан")
        return None

    prompt = (
        f"Извлеки до 5 ключевых интересов пользователя из текста ниже. "
        f"Ответь только списком слов или коротких фраз через запятую, без пояснений.\n\n"
        f"Текст: {bio}"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CHAT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.3,
                },
            )
            if response.status_code == 200:
                data = response.json()
                interests = data["choices"][0]["message"]["content"].strip()
                # Очистка от лишнего
                interests = interests.split("\n")[0]  # только первая строка
                interests = interests.replace(".", "").strip()
                print(f"✅ Interests extracted: {interests}")
                return interests
            else:
                print(f"❌ Mistral Chat error {response.status_code}: {response.text}")
                return None
    except Exception as e:
        print(f"❌ Ошибка при извлечении интересов: {e}")
        return None


def jaccard_similarity(interests1: str, interests2: str) -> float:
    if not interests1 or not interests2:
        return 0.0
    set1 = set(tag.strip().lower() for tag in interests1.split(",") if tag.strip())
    set2 = set(tag.strip().lower() for tag in interests2.split(",") if tag.strip())
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)