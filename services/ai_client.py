import json
import os
import logging
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
AI_MODEL = os.getenv("AI_MODEL", "qwen3.5:latest")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# build your personal model
SYSTEM_PROMPT = (
    "Anda adalah seorang guru profesional yang membuat soal pilihan ganda berkualitas tinggi.\n\n"
    "Anda harus menghasilkan soal dalam Bahasa Indonesia yang:\n"
    "1. Sesuai dengan topik yang diminta\n"
    "2. Memiliki 4 pilihan jawaban (A, B, C, D)\n"
    "3. Memiliki satu jawaban yang benar\n"
    "4. Dilengkapi dengan penjelasan singkat mengapa jawaban tersebut benar\n\n"
    'Output HARUS berupa JSON array (format JSON valid, tanpa teks lain):\n'
    "[\n"
    '  {\n'
    '    "question_text": "teks soal",\n'
    '    "options": ["pilihan A", "pilihan B", "pilihan C", "pilihan D"],\n'
    '    "correct_answer": "pilihan yang benar (salah satu dari options)",\n'
    '    "explanation": "penjelasan singkat"\n'
    "  }\n"
    "]\n\n"
    "Pastikan correct_answer persis sama dengan salah satu string di options.\n"
    "Hanya output JSON array, tanpa markdown, tanpa pembatas apapun."
)


class OllamaClient:

    @staticmethod
    def generate(
        prompt: str,
        num_questions: int = 5,
        temperature: float = 0.7,
    ) -> Optional[List[Dict[str, Any]]]:
        user_prompt = (
            f"Buatkan {num_questions} soal pilihan ganda tentang: \"{prompt}\".\n"
            f"Output JSON array dengan tepat {num_questions} soal."
        )

        payload = {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 4096,
            },
        }

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                resp = client.post(f"{OLLAMA_URL}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()

            content = data.get("message", {}).get("content", "")
            if not content:
                logger.error("Ollama returned empty content")
                return None

            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(
                    line for line in lines if not line.strip().startswith("```")
                )

            questions = json.loads(content)

            if not isinstance(questions, list):
                logger.error(f"Ollama returned non-list: {type(questions)}")
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

            return validated[:num_questions]

        except httpx.TimeoutException:
            logger.error(f"Ollama request timed out after {REQUEST_TIMEOUT}s")
            return None
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {OLLAMA_URL}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Ollama returned HTTP {e.response.status_code}: {e.response.text}"
            )
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama: {e}")
            return None
