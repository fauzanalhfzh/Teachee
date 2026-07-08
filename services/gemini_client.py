import json
import os
import logging
from typing import List, Dict, Any, Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

SYSTEM_PROMPT = """Anda adalah asisten pembuat soal pilihan ganda. Anda HARUS merespon HANYA dengan JSON array yang valid, tanpa teks lain, tanpa markdown, tanpa pembungkus.

Setiap soal memiliki format:
{
  "question_text": "teks soal",
  "options": ["Opsi A", "Opsi B", "Opsi C", "Opsi D"],
  "correct_answer": "salah satu dari opsi di atas",
  "explanation": "penjelasan mengapa jawaban itu benar"
}

Pastikan correct_answer persis sama dengan salah satu string dalam options."""


class GeminiClient:

    @staticmethod
    def generate(
        prompt: str,
        num_questions: int = 5,
        temperature: float = 0.3,
    ) -> Optional[List[Dict[str, Any]]]:
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not set")
            return None

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(
                GEMINI_MODEL,
                system_instruction=SYSTEM_PROMPT,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )

            user_prompt = (
                f"Buatkan {num_questions} soal pilihan ganda tentang: \"{prompt}\".\n"
                f"Output JSON array dengan tepat {num_questions} soal."
            )

            resp = model.generate_content(user_prompt)
            content = resp.text.strip()

            questions = json.loads(content)

            if not isinstance(questions, list):
                logger.error(f"Gemini returned non-list: {type(questions)}")
                return None

            validated = []
            for q in questions:
                if all(k in q for k in ("question_text", "options", "correct_answer")):
                    if q["correct_answer"] not in q["options"]:
                        logger.warning(
                            f"correct_answer '{q['correct_answer']}' not in options, using first option"
                        )
                        if q["options"]:
                            q["correct_answer"] = q["options"][0]
                    validated.append(q)

            logger.info(f"Gemini generated {len(validated)} questions for topic: {prompt}")
            return validated[:num_questions]

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
