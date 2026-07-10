import os
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

AI_PROVIDER = os.getenv("AI_PROVIDER", "vllm").lower()

TEMPLATE_PATTERNS = [
    r'Pernyataan\s+[A-Z]',
    r'Faktor\s+[XYZ]',
    r'Konsep\s+[A-Z]',
    r'Metode\s+[A-D]',
    r'Ilmuwan\s+[A-D]',
    r'Tokoh\s+[A-D]',
    r'Cabang\s+[A-Z]',
    r'Dampak\s+[A-D]',
    r'Sumber\s+[A-D]',
    r'Prinsip\s+[A-D]',
    r'Aplikasi\s+[A-D]',
    r'Perbedaan\s+[A-D]',
    r'Tahun\s+\d{4}\s+\(Benar\)',
    r'\(Varian\s+\d+\)',
]


def _is_template_response(items: List[Dict[str, Any]]) -> bool:
    for item in items:
        text_fields = [
            str(item.get("question_text", "")),
            str(item.get("correct_answer", "")),
            str(item.get("explanation", "")),
        ]
        options = item.get("options", [])
        if isinstance(options, list):
            text_fields.extend(str(o) for o in options if isinstance(o, str))
        elif isinstance(options, dict):
            for val in options.values():
                if isinstance(val, list):
                    text_fields.extend(str(v) for v in val if isinstance(v, str))

        for field in text_fields:
            for pattern in TEMPLATE_PATTERNS:
                if re.search(pattern, field):
                    logger.warning(f"Template detected: pattern='{pattern}' in field='{field[:100]}'")
                    return True
    return False


def _get_ai_client():
    from services.vllm_client import VllmClient
    return VllmClient


class AIService:

    @staticmethod
    def generate_questions(topic: str, num_questions: int) -> Optional[List[Dict[str, Any]]]:
        client = _get_ai_client()
        questions = client.generate(topic, num_questions)
        if questions and not _is_template_response(questions):
            logger.info(f"Generated {len(questions)} questions via vLLM for topic: {topic}")
            return questions
        if questions:
            logger.warning(f"Template detected in generate_questions, retrying with high temp for: {topic}")
            questions = client.generate(topic, num_questions, temperature=1.0)
            if questions and not _is_template_response(questions):
                return questions
        return None

    @staticmethod
    def regenerate_single_question(topic: str) -> Optional[Dict[str, Any]]:
        client = _get_ai_client()
        questions = client.generate(topic, 1)
        if questions and not _is_template_response(questions):
            return questions[0]
        if questions:
            logger.warning(f"Template detected in regenerate, retrying with high temp for: {topic}")
            questions = client.generate(topic, 1, temperature=1.0)
            if questions and not _is_template_response(questions):
                return questions[0]
        return None

    @staticmethod
    def generate_module_sections(topic: str, num_sections: int) -> Optional[List[Dict[str, Any]]]:
        client = _get_ai_client()
        sections = client.generate_content(topic, num_sections)
        if sections and not _is_template_response(sections):
            logger.info(f"Generated {len(sections)} sections via vLLM for topic: {topic}")
            return sections
        if sections:
            logger.warning(f"Template detected in sections, retrying with high temp for: {topic}")
            sections = client.generate_content(topic, num_sections, temperature=1.0)
            if sections and not _is_template_response(sections):
                return sections
        return None

    @staticmethod
    def generate_module_exercises(topic: str, num_exercises: int) -> Optional[List[Dict[str, Any]]]:
        client = _get_ai_client()
        exercises = client.generate_exercises(topic, num_exercises)
        if exercises and not _is_template_response(exercises):
            logger.info(f"Generated {len(exercises)} exercises via vLLM for topic: {topic}")
            return exercises
        if exercises:
            logger.warning(f"Template detected in exercises, retrying with high temp for: {topic}")
            exercises = client.generate_exercises(topic, num_exercises, temperature=1.0)
            if exercises and not _is_template_response(exercises):
                return exercises
        return None
