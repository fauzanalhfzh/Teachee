import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

AI_PROVIDER = os.getenv("AI_PROVIDER", "vllm").lower()


def _get_ai_client():
    from services.vllm_client import VllmClient
    return VllmClient


class AIService:

    @staticmethod
    def generate_questions(topic: str, num_questions: int) -> Optional[List[Dict[str, Any]]]:
        client = _get_ai_client()
        questions = client.generate(topic, num_questions)
        if questions:
            logger.info(f"Generated {len(questions)} questions via vLLM for topic: {topic}")
        return questions

    @staticmethod
    def regenerate_single_question(topic: str) -> Optional[Dict[str, Any]]:
        client = _get_ai_client()
        questions = client.generate(topic, 1)
        if questions:
            return questions[0]
        return None

    @staticmethod
    def generate_module_sections(topic: str, num_sections: int) -> Optional[List[Dict[str, Any]]]:
        client = _get_ai_client()
        sections = client.generate_content(topic, num_sections)
        if sections:
            logger.info(f"Generated {len(sections)} sections via vLLM for topic: {topic}")
        return sections

    @staticmethod
    def generate_module_exercises(topic: str, num_exercises: int) -> Optional[List[Dict[str, Any]]]:
        client = _get_ai_client()
        exercises = client.generate_exercises(topic, num_exercises)
        if exercises:
            logger.info(f"Generated {len(exercises)} exercises via vLLM for topic: {topic}")
        return exercises
