from unittest.mock import patch, MagicMock
import pytest

from services.ai_service import AIService


MOCK_OLLAMA_QUESTIONS = [
    {
        "question_text": "Apa ibukota Indonesia?",
        "options": ["Jakarta", "Bandung", "Surabaya", "Medan"],
        "correct_answer": "Jakarta",
        "explanation": "Jakarta adalah ibukota Indonesia.",
    },
    {
        "question_text": "Siapa penemu bola lampu?",
        "options": ["Einstein", "Edison", "Newton", "Tesla"],
        "correct_answer": "Edison",
        "explanation": "Thomas Edison menemukan bola lampu.",
    },
]


class TestGenerateQuestions:

    @patch("services.ai_service.VllmClient.generate")
    def test_uses_vllm_when_available(self, mock_generate):
        mock_generate.return_value = MOCK_OLLAMA_QUESTIONS

        result = AIService.generate_questions("Sains", 2)

        mock_generate.assert_called_once_with("Sains", 2)
        assert len(result) == 2
        assert result[0]["question_text"] == "Apa ibukota Indonesia?"
        assert result[1]["correct_answer"] == "Edison"

    @patch("services.ai_service.VllmClient.generate")
    def test_returns_none_when_vllm_returns_none(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.generate_questions("Biologi", 3)

        mock_generate.assert_called_once()
        assert result is None

    @patch("services.ai_service.VllmClient.generate")
    def test_returns_empty_when_vllm_returns_empty_list(self, mock_generate):
        mock_generate.return_value = []

        result = AIService.generate_questions("Biologi", 3)

        mock_generate.assert_called_once()
        assert result == []


class TestRegenerateSingleQuestion:

    @patch("services.ai_service.VllmClient.generate")
    def test_uses_vllm_when_available(self, mock_generate):
        mock_generate.return_value = MOCK_OLLAMA_QUESTIONS

        result = AIService.regenerate_single_question("Sains")

        mock_generate.assert_called_once_with("Sains", 1)
        assert result["question_text"] == "Apa ibukota Indonesia?"

    @patch("services.ai_service.VllmClient.generate")
    def test_returns_none_when_vllm_returns_none(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.regenerate_single_question("Fisika")

        assert result is None
