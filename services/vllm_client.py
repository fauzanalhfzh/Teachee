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

SYSTEM_PROMPT = """Anda adalah asisten pembuat soal pilihan ganda berkualitas tinggi untuk siswa SMA/SMK.
Anda HARUS merespon HANYA dengan JSON object yang valid, tanpa teks lain, tanpa markdown, tanpa pembungkus.

ATURAN PENTING:
- Setiap soal harus SPESIFIK dan relevan dengan topik yang diberikan
- JANGAN gunakan placeholder generik seperti "Pernyataan A", "Faktor X", "Konsep A", "Metode A"
- JANGAN mengulang judul topik secara verbatim di dalam soal
- correct_answer harus PERSIS sama dengan salah satu string dalam options
- Variasikan tingkat kesulitan (mudah, sedang, sulit)

Format setiap soal:
{
  "question_text": "teks soal yang spesifik dan jelas",
  "options": ["Opsi A", "Opsi B", "Opsi C", "Opsi D"],
  "correct_answer": "salah satu dari opsi di atas",
  "explanation": "penjelasan singkat mengapa jawaban itu benar"
}

Bungkus array soal dalam object dengan key "questions": { "questions": [...] }"""


class VllmClient:

    @staticmethod
    def _clean_json_content(content: str) -> Optional[str]:
        content = content.strip()
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        content = re.sub(r"```[\w]*\n?", "", content).strip()
        if not content:
            return None
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1 and end > start:
            extracted = content[start:end + 1]
            try:
                json.loads(extracted)
                return extracted
            except json.JSONDecodeError:
                pass
        return content

    @staticmethod
    def generate(
        prompt: str,
        num_questions: int = 5,
        temperature: float = 0.3,
    ) -> Optional[List[Dict[str, Any]]]:
        user_prompt = (
            f"Buatkan {num_questions} soal pilihan ganda tentang \"{prompt}\".\n"
            f"Output JSON array dengan tepat {num_questions} soal.\n\n"
            f"PENTING:\n"
            f"- Soal harus spesifik dan relevan dengan \"{prompt}\"\n"
            f"- JANGAN gunakan pola generik seperti 'Pernyataan A tentang {prompt}'\n"
            f"- Setiap soal harus memiliki jawaban konkret (angka, nama tokoh, istilah spesifik)\n"
            f"- Variasikan tingkat kesulitan (mudah, sedang, sulit)"
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
            "response_format": {"type": "json_object"},
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

            raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not raw_content:
                logger.error("vLLM returned empty content")
                return None

            content = VllmClient._clean_json_content(raw_content)
            if not content:
                logger.error(f"vLLM response contains no JSON array. Raw: {raw_content[:500]}")
                return None

            parsed = json.loads(content)
            questions = parsed.get("questions") if isinstance(parsed, dict) else parsed

            if not isinstance(questions, list):
                logger.error(f"vLLM returned non-list: {type(questions)}. Raw: {raw_content[:500]}")
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
            raw = raw_content[:500] if raw_content else "(no raw content)"
            logger.error(f"Failed to parse vLLM response as JSON: {e}. Raw: {raw}")
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
            f"  \"title\": \"judul section yang spesifik\",\n"
            f"  \"content\": \"teks materi yang panjang dan informatif (min 3 paragraf) — berisi penjelasan konkret, bukan template generik\",\n"
            f"  \"image_prompt\": \"deskripsi prompt untuk ilustrasi gambar section ini\"\n"
            f"}}\n"
            f"PENTING: Konten harus spesifik tentang {prompt}. Jangan gunakan placeholder atau template generik. "
            f"Gunakan bahasa Indonesia yang baik dan benar."
        )
        content_system = (
            "Anda adalah asisten pembuat materi pembelajaran. "
            "Anda HARUS merespon HANYA dengan JSON object yang valid, tanpa teks lain, tanpa markdown. "
            "Bungkus array section dalam object dengan key \"sections\": { \"sections\": [...] }. "
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
            f"Buatkan {num_exercises} latihan interaktif berkualitas tinggi tentang topik: \"{prompt}\".\n\n"
            f"PENTING: Setiap soal harus spesifik dan relevan dengan topik. "
            f"JANGAN gunakan placeholder generik seperti 'Pernyataan A', 'Faktor X', 'Konsep A'. "
            f"Buat pertanyaan yang menguji pemahaman nyata siswa.\n\n"
            f"CONTOH BURUK (JANGAN DITIRU):\n"
            f"- question_text: 'Manakah pernyataan yang benar tentang {prompt}?'\n"
            f'- options: ["Pernyataan A tentang {prompt} (Benar)", "Pernyataan B tentang {prompt}", ...]\n\n'
            f"CONTOH BAIK:\n"
            f"- question_text: 'Apa output dari perintah print(type(3.14)) di Python?'\n"
            f"- options: [\"<class 'float'>\", \"<class 'int'>\", \"<class 'str'>\", \"<class 'decimal'>\"]\n\n"
            f"Variasi tipe latihan:\n"
            f"1. multiple_choice: 4 opsi dengan jawaban yang spesifik (nama, angka, istilah nyata)\n"
            f"2. fill_blank: isian singkat dengan jawaban kata/frasa spesifik\n"
            f"3. true_false: pernyataan faktual yang bisa diverifikasi\n"
            f"4. matching: pasangkan istilah nyata dengan definisi/penjelasan yang akurat\n"
            f"5. ordering: urutkan langkah/proses yang benar secara kronologis\n\n"
            f"Format JSON per latihan:\n"
            f"{{\n"
            f'  "exercise_type": "multiple_choice/fill_blank/true_false/matching/ordering",\n'
            f'  "question_text": "teks soal yang spesifik dan jelas",\n'
            f'  "options": [... atau null untuk fill_blank],\n'
            f'  "correct_answer": "jawaban benar yang spesifik",\n'
            f'  "explanation": "penjelasan singkat tapi informatif",\n'
            f'  "points": 10\n'
            f"}}\n\n"
            f"Gunakan bahasa Indonesia. Variasikan tipe latihan secara merata. "
            f"Pastikan jawaban correct_answer IDENTIK dengan salah satu opsi (untuk multiple_choice)."
        )
        exercise_system = (
            "Anda adalah asisten pembuat latihan interaktif berkualitas tinggi untuk siswa SMA/SMK. "
            "Anda HARUS merespon HANYA dengan JSON object yang valid, tanpa teks lain, tanpa markdown. "
            "Bungkus array latihan dalam object dengan key \"exercises\": { \"exercises\": [...] }. "
            "ATURAN PENTING:\n"
            "- Setiap soal harus spesifik dan relevan dengan topik yang diberikan\n"
            "- Jawaban harus konkret (nama tokoh, angka, istilah spesifik), bukan placeholder generik\n"
            "- Jangan gunakan pola 'Pernyataan A', 'Faktor X', 'Metode A' sebagai jawaban\n"
            "- Jangan mengulang judul topik di dalam teks soal\n"
            "- Buat latihan yang menguji pemahaman, bukan sekadar menghafal definisi\n"
            "- Variasikan tingkat kesulitan: ada yang mudah, sedang, dan sulit"
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
            "response_format": {"type": "json_object"},
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

            raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not raw_content:
                logger.error("vLLM returned empty content")
                return None

            content = VllmClient._clean_json_content(raw_content)
            if not content:
                logger.error(f"vLLM response contains no JSON. Raw: {raw_content[:500]}")
                return None

            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                logger.error(f"vLLM returned non-object: {type(parsed)}")
                return None

            result = None
            for key in ("sections", "exercises", "items", "data", "questions"):
                if key in parsed and isinstance(parsed[key], list):
                    result = parsed[key]
                    break
            if result is None:
                logger.error(f"vLLM response missing array key. Keys: {list(parsed.keys())}. Raw: {raw_content[:500]}")
                return None

            logger.info(f"vLLM generated {len(result)} items for topic: {user_prompt}")
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
            raw = raw_content[:500] if raw_content else "(no raw content)"
            logger.error(f"Failed to parse vLLM response as JSON: {e}. Raw: {raw}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling vLLM: {e}")
            return None
