from unittest.mock import patch, MagicMock
import pytest

from services.ai_service import AIService, MATH_BANK, HISTORY_BANK, DEFAULT_BANK


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
    def test_falls_back_when_vllm_returns_none(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.generate_questions("Biologi", 3)

        mock_generate.assert_called_once()
        assert result is not None
        assert len(result) == 3

    @patch("services.ai_service.VllmClient.generate")
    def test_falls_back_when_vllm_returns_empty_list(self, mock_generate):
        mock_generate.return_value = []

        result = AIService.generate_questions("Biologi", 3)

        mock_generate.assert_called_once()
        assert result is not None
        assert len(result) == 3

    @patch("services.ai_service.VllmClient.generate")
    def test_fallbacks_to_default_bank_for_unknown_topic(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.generate_questions("Biologi", 2)

        assert len(result) == 2
        assert "Biologi" in result[0]["question_text"]
        assert result[0]["correct_answer"] == DEFAULT_BANK[0]["correct_answer"]
        assert "Biologi" in result[1]["question_text"]
        assert result[1]["correct_answer"] == DEFAULT_BANK[1]["correct_answer"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_math_bank_for_math_topic(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.generate_questions("aljabar linear", 2)

        assert len(result) == 2
        assert result[0]["question_text"] == MATH_BANK[0]["question_text"]
        assert result[0]["correct_answer"] == MATH_BANK[0]["correct_answer"]
        assert result[1]["question_text"] == MATH_BANK[1]["question_text"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_math_bank_for_matematika_topic(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.generate_questions("Matematika Dasar", 1)

        assert result[0]["question_text"] == MATH_BANK[0]["question_text"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_history_bank_for_history_topic(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.generate_questions("sejarah indonesia", 3)

        assert len(result) == 3
        assert result[0]["question_text"] == HISTORY_BANK[0]["question_text"]
        assert result[1]["question_text"] == HISTORY_BANK[1]["question_text"]
        assert result[2]["question_text"] == HISTORY_BANK[2]["question_text"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_scales_beyond_bank_size(self, mock_generate):
        mock_generate.return_value = None

        num_beyond = len(DEFAULT_BANK) + 5
        result = AIService.generate_questions("Fisika", num_beyond)

        assert len(result) == num_beyond
        for i, q in enumerate(result):
            assert "Fisika" in q["question_text"]
            if i >= len(DEFAULT_BANK):
                assert "Varian" in q["question_text"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_preserves_topic_in_all_questions(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.generate_questions("Astronomi", 3)

        for q in result:
            assert "Astronomi" in q["question_text"]
            assert "Astronomi" in q["explanation"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_differentiates_variant_text(self, mock_generate):
        mock_generate.return_value = None

        num_beyond = len(DEFAULT_BANK) + 2
        result = AIService.generate_questions("Geologi", num_beyond)

        assert len(result) == num_beyond
        assert f"Varian {len(DEFAULT_BANK) + 1}" in result[len(DEFAULT_BANK)]["question_text"]
        assert f"Varian {len(DEFAULT_BANK) + 2}" in result[len(DEFAULT_BANK) + 1]["question_text"]


class TestRegenerateSingleQuestion:

    @patch("services.ai_service.VllmClient.generate")
    def test_uses_vllm_when_available(self, mock_generate):
        mock_generate.return_value = MOCK_OLLAMA_QUESTIONS

        result = AIService.regenerate_single_question("Sains")

        mock_generate.assert_called_once_with("Sains", 1)
        assert result["question_text"] == "Apa ibukota Indonesia?"

    @patch("services.ai_service.VllmClient.generate")
    def test_falls_back_when_vllm_returns_none(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.regenerate_single_question("Fisika")

        assert result is not None
        assert "question_text" in result
        assert "Fisika" in result["question_text"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_returns_math_question(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.regenerate_single_question("aljabar")

        assert result["question_text"] == MATH_BANK[0]["question_text"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_returns_history_question(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.regenerate_single_question("sejarah")

        assert result["question_text"] == HISTORY_BANK[0]["question_text"]

    @patch("services.ai_service.VllmClient.generate")
    def test_fallback_returned_question_has_all_keys(self, mock_generate):
        mock_generate.return_value = None

        result = AIService.regenerate_single_question("Kimia")

        assert "question_text" in result
        assert "options" in result
        assert "correct_answer" in result
        assert "explanation" in result
        assert len(result["options"]) == 4


class TestFallbackGenerate:

    def test_math_bank_contains_valid_questions(self):
        for q in MATH_BANK:
            assert "question_text" in q
            assert "options" in q
            assert "correct_answer" in q
            assert q["correct_answer"] in q["options"]

    def test_history_bank_contains_valid_questions(self):
        for q in HISTORY_BANK:
            assert "question_text" in q
            assert "options" in q
            assert "correct_answer" in q
            assert q["correct_answer"] in q["options"]

    def test_default_bank_contains_valid_questions(self):
        for q in DEFAULT_BANK:
            assert "question_text" in q
            assert "options" in q
            assert "correct_answer" in q
            assert q["correct_answer"] in q["options"]

    def test_returns_empty_list_for_zero_questions(self):
        result = AIService._fallback_generate("Sains", 0)
        assert result == []

    def test_math_bank_correct_answer_in_options(self):
        for q in MATH_BANK:
            assert q["correct_answer"] in q["options"], (
                f"correct_answer '{q['correct_answer']}' not in options for: {q['question_text']}"
            )

    def test_history_bank_correct_answer_in_options(self):
        for q in HISTORY_BANK:
            assert q["correct_answer"] in q["options"], (
                f"correct_answer '{q['correct_answer']}' not in options for: {q['question_text']}"
            )

    def test_default_bank_correct_answer_in_options(self):
        for q in DEFAULT_BANK:
            assert q["correct_answer"] in q["options"], (
                f"correct_answer '{q['correct_answer']}' not in options for: {q['question_text']}"
            )
