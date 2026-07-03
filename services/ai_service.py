import random
from typing import List, Dict, Any

class AIService:
    @staticmethod
    def generate_questions(topic: str, num_questions: int) -> List[Dict[str, Any]]:
        questions = []
        
        # Matematika / Aljabar Bank
        math_bank = [
            {
                "question_text": "Berapakah nilai x dari persamaan 2x + 5 = 15?",
                "options": ["x = 5", "x = 10", "x = 3", "x = 7"],
                "correct_answer": "x = 5",
                "explanation": "Pindahkan 5 ke ruas kanan: 2x = 15 - 5 => 2x = 10. Bagi kedua sisi dengan 2: x = 5."
            },
            {
                "question_text": "Faktorkan persamaan kuadrat berikut: x^2 - 5x + 6 = 0.",
                "options": ["(x - 2)(x - 3) = 0", "(x - 1)(x - 6) = 0", "(x + 2)(x + 3) = 0", "(x - 5)(x + 6) = 0"],
                "correct_answer": "(x - 2)(x - 3) = 0",
                "explanation": "Carilah dua bilangan yang jika dikalikan menghasilkan 6 dan jika dijumlahkan menghasilkan -5. Bilangan tersebut adalah -2 dan -3."
            },
            {
                "question_text": "Jika y = 3x - 4 dan x = 4, berapakah nilai y?",
                "options": ["y = 8", "y = 12", "y = 16", "y = 4"],
                "correct_answer": "y = 8",
                "explanation": "Substitusi x = 4 ke persamaan: y = 3(4) - 4 = 12 - 4 = 8."
            },
            {
                "question_text": "Jika 3x + 4 = 19, berapakah nilai dari 2x - 1?",
                "options": ["9", "10", "5", "7"],
                "correct_answer": "9",
                "explanation": "3x = 15 => x = 5. Maka 2x - 1 = 2(5) - 1 = 9."
            },
            {
                "question_text": "Tentukan gradien dari persamaan garis 3x - 2y = 6.",
                "options": ["1.5", "-1.5", "3", "2"],
                "correct_answer": "1.5",
                "explanation": "Ubah ke bentuk y = mx + c: -2y = -3x + 6 => y = 1.5x - 3. Gradien m = 1.5."
            }
        ]
        
        # Sejarah Bank
        history_bank = [
            {
                "question_text": "Siapakah presiden pertama Republik Indonesia?",
                "options": ["Ir. Soekarno", "Mohammad Hatta", "Soeharto", "B.J. Habibie"],
                "correct_answer": "Ir. Soekarno",
                "explanation": "Ir. Soekarno adalah presiden pertama RI yang menjabat dari tahun 1945 sampai 1967."
            },
            {
                "question_text": "Kapan teks proklamasi kemerdekaan Indonesia dibacakan?",
                "options": ["17 Agustus 1945", "18 Agustus 1945", "1 Juni 1945", "20 Mei 1908"],
                "correct_answer": "17 Agustus 1945",
                "explanation": "Teks proklamasi dibacakan pada hari Jumat, 17 Agustus 1945 jam 10.00 WIB."
            },
            {
                "question_text": "Di kota manakah teks proklamasi kemerdekaan Indonesia dibacakan?",
                "options": ["Jakarta", "Bandung", "Yogyakarta", "Surabaya"],
                "correct_answer": "Jakarta",
                "explanation": "Dibacakan di kediaman Soekarno, Jalan Pegangsaan Timur No. 56, Jakarta."
            },
            {
                "question_text": "Siapakah tokoh yang mengetik naskah proklamasi kemerdekaan Indonesia?",
                "options": ["Sayuti Melik", "Sukarni", "Ahmad Soebardjo", "Latief Hendraningrat"],
                "correct_answer": "Sayuti Melik",
                "explanation": "Naskah proklamasi diketik oleh Sayuti Melik setelah disetujui konsepnya oleh Soekarno-Hatta."
            }
        ]

        # Default Bank
        default_bank = [
            {
                "question_text": f"Pertanyaan contoh 1 mengenai topik '{topic}'.",
                "options": ["Jawaban A (Benar)", "Opsi B", "Opsi C", "Opsi D"],
                "correct_answer": "Jawaban A (Benar)",
                "explanation": f"Ini adalah penjelasan mock untuk pertanyaan 1 bertopik {topic}."
            },
            {
                "question_text": f"Pertanyaan contoh 2 mengenai topik '{topic}'.",
                "options": ["Opsi A", "Jawaban B (Benar)", "Opsi C", "Opsi D"],
                "correct_answer": "Jawaban B (Benar)",
                "explanation": f"Ini adalah penjelasan mock untuk pertanyaan 2 bertopik {topic}."
            },
            {
                "question_text": f"Pertanyaan contoh 3 mengenai topik '{topic}'.",
                "options": ["Opsi A", "Opsi B", "Jawaban C (Benar)", "Opsi D"],
                "correct_answer": "Jawaban C (Benar)",
                "explanation": f"Ini adalah penjelasan mock untuk pertanyaan 3 bertopik {topic}."
            }
        ]

        topic_lower = topic.lower()
        if "aljabar" in topic_lower or "matematika" in topic_lower or "math" in topic_lower:
            bank = math_bank
        elif "sejarah" in topic_lower or "history" in topic_lower:
            bank = history_bank
        else:
            bank = default_bank

        for i in range(num_questions):
            if i < len(bank):
                q = bank[i].copy()
            else:
                q = random.choice(bank).copy()
                q["question_text"] = f"{q['question_text']} (Varian Soal {i+1})"
            
            questions.append(q)

        return questions

    @staticmethod
    def regenerate_single_question(topic: str) -> Dict[str, Any]:
        questions = AIService.generate_questions(topic, 1)
        return questions[0]
