import json
import os
import re
import logging
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen2.5-7B-Instruct")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")
REQUEST_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "60"))

SYSTEM_PROMPT = """Anda adalah asisten pembuat soal pilihan ganda. Anda HARUS merespon HANYA dengan JSON array yang valid, tanpa teks lain, tanpa markdown, tanpa pembungkus.

Setiap soal memiliki format:
{
  "question_text": "teks soal",
  "options": ["Opsi A", "Opsi B", "Opsi C", "Opsi D"],
  "correct_answer": "salah satu dari opsi di atas",
  "explanation": "penjelasan mengapa jawaban itu benar"
}

Pastikan correct_answer persis sama dengan salah satu string dalam options."""


class VllmClient:

    @staticmethod
    def generate(
        prompt: str,
        num_questions: int = 5,
        temperature: float = 0.3,
    ) -> Optional[List[Dict[str, Any]]]:
        user_prompt = (
            f"Buatkan {num_questions} soal pilihan ganda tentang: \"{prompt}\".\n"
            f"Output JSON array dengan tepat {num_questions} soal."
        )

        headers = {"Content-Type": "application/json"}
        if VLLM_API_KEY:
            headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

        payload = {
            "model": VLLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": 4096,
        }

        try:
            with httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT)) as client:
                resp = client.post(
                    f"{VLLM_URL.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                logger.error("vLLM returned empty content")
                return None

            content = content.strip()
            # Strip Qwen3-style <think>...</think> reasoning blocks so JSON parses
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(
                    line for line in lines if not line.strip().startswith("```")
                )

            questions = json.loads(content)

            if not isinstance(questions, list):
                logger.error(f"vLLM returned non-list: {type(questions)}")
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

            logger.info(f"vLLM generated {len(validated)} questions for topic: {prompt}")
            return validated[:num_questions]

        except httpx.TimeoutException:
            logger.error(f"vLLM request timed out after {REQUEST_TIMEOUT}s")
            return None
        except httpx.ConnectError:
            logger.error(f"Cannot connect to vLLM at {VLLM_URL}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"vLLM returned HTTP {e.response.status_code}: {e.response.text}"
            )
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse vLLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling vLLM: {e}")
            return None

    @staticmethod
    def generate_content(
        prompt: str,
        num_sections: int = 4,
        temperature: float = 0.4,
    ) -> Optional[List[Dict[str, Any]]]:
        user_prompt = (
            f"Buatkan materi pembelajaran tentang: \"{prompt}\" dalam {num_sections} bagian.\n"
            f"Output JSON array dengan tepat {num_sections} section. "
            f"Setiap section memiliki format:\n"
            f"{{\n"
            f"  \"title\": \"judul section\",\n"
            f"  \"content\": \"teks materi yang panjang dan informatif (min 3 paragraf)\",\n"
            f"  \"image_prompt\": \"deskripsi prompt untuk ilustrasi gambar section ini\"\n"
            f"}}\n"
            f"Gunakan bahasa Indonesia yang baik dan benar."
        )
        content_system = (
            "Anda adalah asisten pembuat materi pembelajaran. "
            "Anda HARUS merespon HANYA dengan JSON array yang valid, tanpa teks lain, tanpa markdown. "
            "Buat materi yang informatif, mudah dipahami, dengan contoh-contoh relevan."
        )
        return VllmClient._call_vllm(user_prompt, content_system, temperature, 4096)

    @staticmethod
    def generate_exercises(
        prompt: str,
        num_exercises: int = 6,
        temperature: float = 0.3,
    ) -> Optional[List[Dict[str, Any]]]:
        user_prompt = (
            f"Buatkan {num_exercises} latihan interaktif tentang: \"{prompt}\".\n"
            f"Output JSON array dengan tepat {num_exercises} latihan.\n\n"
            f"Variasi tipe latihan:\n"
            f"1. multiple_choice: pilihan ganda dengan 4 opsi, jawaban tepat salah satu opsi\n"
            f"2. fill_blank: isian singkat (______), jawaban adalah kata/frasa yang tepat\n"
            f"3. true_false: pernyataan benar/salah, options: [\"Benar\", \"Salah\"]\n"
            f"4. matching: menjodohkan, options berupa object {{\"left\": [...], \"right\": [...]}}, "
            f"correct_answer berupa string \"kiri1-kanan1;kiri2-kanan2;...\"\n"
            f"5. ordering: mengurutkan, options berupa array item yang perlu diurutkan, "
            f"correct_answer berupa string \"1;2;3;...\"\n\n"
            f"Setiap latihan memiliki format:\n"
            f"{{\n"
            f"  \"exercise_type\": \"multiple_choice/fill_blank/true_false/matching/ordering\",\n"
            f"  \"question_text\": \"teks soal\",\n"
            f"  \"options\": [... atau null untuk fill_blank],\n"
            f"  \"correct_answer\": \"jawaban benar\",\n"
            f"  \"explanation\": \"penjelasan jawaban\",\n"
            f"  \"points\": 10\n"
            f"}}\n"
            f"Gunakan bahasa Indonesia. Variasikan tipe latihan secara merata."
        )
        exercise_system = (
            "Anda adalah asisten pembuat latihan interaktif gaya Duolingo. "
            "Anda HARUS merespon HANYA dengan JSON array yang valid, tanpa teks lain, tanpa markdown. "
            "Buat latihan yang menantang namun menyenangkan."
        )
        return VllmClient._call_vllm(user_prompt, exercise_system, temperature, 4096)

    @staticmethod
    def _call_vllm(
        user_prompt: str,
        system_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Optional[List[Dict[str, Any]]]:
        headers = {"Content-Type": "application/json"}
        if VLLM_API_KEY:
            headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

        payload = {
            "model": VLLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT)) as client:
                resp = client.post(
                    f"{VLLM_URL.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                logger.error("vLLM returned empty content")
                return None

            content = content.strip()
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(
                    line for line in lines if not line.strip().startswith("```")
                )

            result = json.loads(content)

            if not isinstance(result, list):
                logger.error(f"vLLM returned non-list: {type(result)}")
                return None

            logger.info(f"vLLM generated {len(result)} items for topic: {prompt}")
            return result

        except httpx.TimeoutException:
            logger.error(f"vLLM request timed out after {REQUEST_TIMEOUT}s")
            return None
        except httpx.ConnectError:
            logger.error(f"Cannot connect to vLLM at {VLLM_URL}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"vLLM returned HTTP {e.response.status_code}: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse vLLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling vLLM: {e}")
            return None
