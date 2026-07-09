import os
import random
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

AI_PROVIDER = os.getenv("AI_PROVIDER", "vllm").lower()


def _get_ai_client():
    from services.vllm_client import VllmClient
    return VllmClient

MATH_BANK = [
    {
        "question_text": "Berapakah nilai x dari persamaan 2x + 5 = 15?",
        "options": ["x = 5", "x = 10", "x = 3", "x = 7"],
        "correct_answer": "x = 5",
        "explanation": "Pindahkan 5 ke ruas kanan: 2x = 15 - 5 => 2x = 10. Bagi kedua sisi dengan 2: x = 5.",
    },
    {
        "question_text": "Faktorkan persamaan kuadrat berikut: x^2 - 5x + 6 = 0.",
        "options": ["(x - 2)(x - 3) = 0", "(x - 1)(x - 6) = 0", "(x + 2)(x + 3) = 0", "(x - 5)(x + 6) = 0"],
        "correct_answer": "(x - 2)(x - 3) = 0",
        "explanation": "Carilah dua bilangan yang jika dikalikan menghasilkan 6 dan jika dijumlahkan menghasilkan -5. Bilangan tersebut adalah -2 dan -3.",
    },
    {
        "question_text": "Jika y = 3x - 4 dan x = 4, berapakah nilai y?",
        "options": ["y = 8", "y = 12", "y = 16", "y = 4"],
        "correct_answer": "y = 8",
        "explanation": "Substitusi x = 4 ke persamaan: y = 3(4) - 4 = 12 - 4 = 8.",
    },
    {
        "question_text": "Jika 3x + 4 = 19, berapakah nilai dari 2x - 1?",
        "options": ["9", "10", "5", "7"],
        "correct_answer": "9",
        "explanation": "3x = 15 => x = 5. Maka 2x - 1 = 2(5) - 1 = 9.",
    },
    {
        "question_text": "Tentukan gradien dari persamaan garis 3x - 2y = 6.",
        "options": ["1.5", "-1.5", "3", "2"],
        "correct_answer": "1.5",
        "explanation": "Ubah ke bentuk y = mx + c: -2y = -3x + 6 => y = 1.5x - 3. Gradien m = 1.5.",
    },
    {
        "question_text": "Berapakah luas segitiga dengan alas 10 cm dan tinggi 8 cm?",
        "options": ["40 cm²", "80 cm²", "20 cm²", "60 cm²"],
        "correct_answer": "40 cm²",
        "explanation": "Luas segitiga = ½ × alas × tinggi = ½ × 10 × 8 = 40 cm².",
    },
    {
        "question_text": "Jika a = 5 dan b = 3, berapakah nilai dari a² - b²?",
        "options": ["16", "4", "25", "9"],
        "correct_answer": "16",
        "explanation": "a² - b² = 25 - 9 = 16.",
    },
    {
        "question_text": "Berapakah hasil dari 15 ÷ (3 × 5)?",
        "options": ["1", "9", "25", "0"],
        "correct_answer": "1",
        "explanation": "Kerjakan operasi dalam kurung terlebih dahulu: 3 × 5 = 15. Lalu 15 ÷ 15 = 1.",
    },
    {
        "question_text": "Tentukan median dari data: 7, 3, 9, 5, 6.",
        "options": ["6", "5", "7", "3"],
        "correct_answer": "6",
        "explanation": "Urutkan: 3, 5, 6, 7, 9. Nilai tengah adalah 6.",
    },
    {
        "question_text": "Sebuah lingkaran memiliki jari-jari 7 cm. Berapakah kelilingnya?",
        "options": ["44 cm", "22 cm", "154 cm", "88 cm"],
        "correct_answer": "44 cm",
        "explanation": "K = 2πr = 2 × 22/7 × 7 = 44 cm.",
    },
    {
        "question_text": "Berapakah nilai dari 2⁵?",
        "options": ["32", "25", "10", "64"],
        "correct_answer": "32",
        "explanation": "2⁵ = 2 × 2 × 2 × 2 × 2 = 32.",
    },
    {
        "question_text": "Jika x + y = 10 dan x - y = 2, berapakah nilai x?",
        "options": ["6", "4", "8", "5"],
        "correct_answer": "6",
        "explanation": "Jumlahkan kedua persamaan: (x+y)+(x-y) = 10+2 => 2x = 12 => x = 6.",
    },
    {
        "question_text": "Berapakah 25% dari 200?",
        "options": ["50", "25", "75", "100"],
        "correct_answer": "50",
        "explanation": "25/100 × 200 = 50.",
    },
    {
        "question_text": "Sebuah kubus memiliki panjang rusuk 5 cm. Berapakah volumenya?",
        "options": ["125 cm³", "25 cm³", "100 cm³", "150 cm³"],
        "correct_answer": "125 cm³",
        "explanation": "V = s³ = 5³ = 125 cm³.",
    },
    {
        "question_text": "Berapakah hasil dari 7! (7 faktorial)?",
        "options": ["5040", "720", "2520", "40320"],
        "correct_answer": "5040",
        "explanation": "7! = 7 × 6 × 5 × 4 × 3 × 2 × 1 = 5040.",
    },
]

HISTORY_BANK = [
    {
        "question_text": "Siapakah presiden pertama Republik Indonesia?",
        "options": ["Ir. Soekarno", "Mohammad Hatta", "Soeharto", "B.J. Habibie"],
        "correct_answer": "Ir. Soekarno",
        "explanation": "Ir. Soekarno adalah presiden pertama RI yang menjabat dari tahun 1945 sampai 1967.",
    },
    {
        "question_text": "Kapan teks proklamasi kemerdekaan Indonesia dibacakan?",
        "options": ["17 Agustus 1945", "18 Agustus 1945", "1 Juni 1945", "20 Mei 1908"],
        "correct_answer": "17 Agustus 1945",
        "explanation": "Teks proklamasi dibacakan pada hari Jumat, 17 Agustus 1945 jam 10.00 WIB.",
    },
    {
        "question_text": "Di kota manakah teks proklamasi kemerdekaan Indonesia dibacakan?",
        "options": ["Jakarta", "Bandung", "Yogyakarta", "Surabaya"],
        "correct_answer": "Jakarta",
        "explanation": "Dibacakan di kediaman Soekarno, Jalan Pegangsaan Timur No. 56, Jakarta.",
    },
    {
        "question_text": "Siapakah tokoh yang mengetik naskah proklamasi kemerdekaan Indonesia?",
        "options": ["Sayuti Melik", "Sukarni", "Ahmad Soebardjo", "Latief Hendraningrat"],
        "correct_answer": "Sayuti Melik",
        "explanation": "Naskah proklamasi diketik oleh Sayuti Melik setelah disetujui konsepnya oleh Soekarno-Hatta.",
    },
    {
        "question_text": "Pada tahun berapakah peristiwa Sumpah Pemuda?",
        "options": ["1928", "1945", "1908", "1930"],
        "correct_answer": "1928",
        "explanation": "Sumpah Pemuda dicetuskan pada 28 Oktober 1928.",
    },
    {
        "question_text": "Siapakah pahlawan nasional yang dijuluki 'Bapak Pendidikan'?",
        "options": ["Ki Hajar Dewantara", "Mohammad Hatta", "Soekarno", "R.A. Kartini"],
        "correct_answer": "Ki Hajar Dewantara",
        "explanation": "Ki Hajar Dewantara adalah Bapak Pendidikan Nasional Indonesia.",
    },
    {
        "question_text": "Peristiwa apa yang terjadi pada tanggal 10 November 1945?",
        "options": ["Pertempuran Surabaya", "Proklamasi Kemerdekaan", "Sumpah Pemuda", "Serangan Umum 1 Maret"],
        "correct_answer": "Pertempuran Surabaya",
        "explanation": "Pertempuran Surabaya pada 10 November 1945 diperingati sebagai Hari Pahlawan.",
    },
    {
        "question_text": "Siapakah presiden RI yang menjabat paling lama?",
        "options": ["Soeharto", "Soekarno", "Susilo Bambang Yudhoyono", "Joko Widodo"],
        "correct_answer": "Soeharto",
        "explanation": "Soeharto menjabat sebagai presiden RI selama 32 tahun (1967-1998).",
    },
    {
        "question_text": "Apa nama organisasi pemuda yang pertama kali didirikan di Indonesia?",
        "options": ["Budi Utomo", "Sarekat Islam", "Indische Partij", "Muhammadiyah"],
        "correct_answer": "Budi Utomo",
        "explanation": "Budi Utomo didirikan pada 20 Mei 1908 oleh Dr. Soetomo.",
    },
    {
        "question_text": "Kapan Indonesia merdeka?",
        "options": ["17 Agustus 1945", "18 Agustus 1945", "1 Juni 1945", "10 November 1945"],
        "correct_answer": "17 Agustus 1945",
        "explanation": "Indonesia memproklamasikan kemerdekaan pada 17 Agustus 1945.",
    },
    {
        "question_text": "Siapakah tokoh yang membacakan teks proklamasi?",
        "options": ["Soekarno dan Hatta", "Soekarno saja", "Hatta saja", "Ahmad Soebardjo"],
        "correct_answer": "Soekarno dan Hatta",
        "explanation": "Proklamasi dibacakan oleh Soekarno dan didampingi oleh Mohammad Hatta.",
    },
    {
        "question_text": "Apa nama kerajaan Hindu tertua di Indonesia?",
        "options": ["Kutai", "Majapahit", "Sriwijaya", "Tarumanegara"],
        "correct_answer": "Kutai",
        "explanation": "Kerajaan Kutai di Kalimantan Timur adalah kerajaan Hindu tertua di Indonesia (abad ke-4 M).",
    },
]

DEFAULT_BANK = [
    {
        "question_text": "Manakah pernyataan yang benar tentang topik '{topic}'?",
        "options": ["Pernyataan A (Benar)", "Pernyataan B", "Pernyataan C", "Pernyataan D"],
        "correct_answer": "Pernyataan A (Benar)",
        "explanation": "Pernyataan A adalah yang paling tepat untuk topik {topic}.",
    },
    {
        "question_text": "Apa penyebab utama terjadinya fenomena terkait '{topic}'?",
        "options": ["Faktor X (Benar)", "Faktor Y", "Faktor Z", "Faktor W"],
        "correct_answer": "Faktor X (Benar)",
        "explanation": "Faktor X merupakan penyebab utama dalam konteks {topic}.",
    },
    {
        "question_text": "Tokoh terkenal yang berkaitan dengan '{topic}' adalah?",
        "options": ["Tokoh A (Benar)", "Tokoh B", "Tokoh C", "Tokoh D"],
        "correct_answer": "Tokoh A (Benar)",
        "explanation": "Tokoh A adalah tokoh yang paling dikenal dalam bidang {topic}.",
    },
    {
        "question_text": "Teori tentang '{topic}' pertama kali dikemukakan oleh?",
        "options": ["Ilmuwan A (Benar)", "Ilmuwan B", "Ilmuwan C", "Ilmuwan D"],
        "correct_answer": "Ilmuwan A (Benar)",
        "explanation": "Ilmuwan A adalah pencetus teori {topic} yang diakui secara luas.",
    },
    {
        "question_text": "Aplikasi praktis dari konsep '{topic}' adalah?",
        "options": ["Aplikasi A (Benar)", "Aplikasi B", "Aplikasi C", "Aplikasi D"],
        "correct_answer": "Aplikasi A (Benar)",
        "explanation": "Aplikasi A merupakan contoh nyata penerapan {topic}.",
    },
    {
        "question_text": "Tahun penting dalam sejarah perkembangan '{topic}' adalah?",
        "options": ["Tahun 2000 (Benar)", "Tahun 1990", "Tahun 2010", "Tahun 1980"],
        "correct_answer": "Tahun 2000 (Benar)",
        "explanation": "Tahun 2000 menandai tonggak penting dalam perkembangan {topic}.",
    },
    {
        "question_text": "Manakah yang BUKAN merupakan cabang dari '{topic}'?",
        "options": ["Cabang Y (Benar, bukan cabang)", "Cabang A", "Cabang B", "Cabang C"],
        "correct_answer": "Cabang Y (Benar, bukan cabang)",
        "explanation": "Cabang Y tidak termasuk dalam disiplin ilmu {topic}.",
    },
    {
        "question_text": "Metode yang paling umum digunakan dalam studi '{topic}' adalah?",
        "options": ["Metode A (Benar)", "Metode B", "Metode C", "Metode D"],
        "correct_answer": "Metode A (Benar)",
        "explanation": "Metode A adalah pendekatan standar dalam mempelajari {topic}.",
    },
    {
        "question_text": "Dampak positif dari '{topic}' bagi masyarakat adalah?",
        "options": ["Dampak A (Benar)", "Dampak B", "Dampak C", "Dampak D"],
        "correct_answer": "Dampak A (Benar)",
        "explanation": "Dampak A merupakan kontribusi utama {topic} bagi masyarakat.",
    },
    {
        "question_text": "Prinsip dasar yang mendasari '{topic}' adalah?",
        "options": ["Prinsip A (Benar)", "Prinsip B", "Prinsip C", "Prinsip D"],
        "correct_answer": "Prinsip A (Benar)",
        "explanation": "Prinsip A merupakan landasan fundamental dari {topic}.",
    },
    {
        "question_text": "Perbedaan utama antara '{topic}' dan konsep serupa adalah?",
        "options": ["Perbedaan A (Benar)", "Perbedaan B", "Perbedaan C", "Perbedaan D"],
        "correct_answer": "Perbedaan A (Benar)",
        "explanation": "Perbedaan A membedakan {topic} dari konsep-konsep lainnya.",
    },
    {
        "question_text": "Sumber daya yang paling dibutuhkan untuk mempelajari '{topic}' adalah?",
        "options": ["Sumber A (Benar)", "Sumber B", "Sumber C", "Sumber D"],
        "correct_answer": "Sumber A (Benar)",
        "explanation": "Sumber A adalah referensi utama untuk memahami {topic}.",
    },
]


class AIService:

    @staticmethod
    def generate_questions(topic: str, num_questions: int) -> List[Dict[str, Any]]:
        client = _get_ai_client()
        provider_name = AI_PROVIDER

        questions = client.generate(topic, num_questions)
        if questions and len(questions) > 0:
            logger.info(f"Generated {len(questions)} questions via {provider_name} for topic: {topic}")
            return questions

        logger.warning(f"{provider_name} unavailable, trying fallback bank for topic: {topic}")
        return AIService._fallback_generate(topic, num_questions)

    @staticmethod
    def regenerate_single_question(topic: str) -> Dict[str, Any]:
        client = _get_ai_client()
        provider_name = AI_PROVIDER

        questions = client.generate(topic, 1)
        if questions and len(questions) > 0:
            return questions[0]

        logger.warning(f"{provider_name} unavailable, using fallback for single question: {topic}")
        questions = AIService._fallback_generate(topic, 1)
        return questions[0]

    @staticmethod
    def _fallback_generate(topic: str, num_questions: int) -> List[Dict[str, Any]]:
        questions = []
        topic_lower = topic.lower()
        if "aljabar" in topic_lower or "matematika" in topic_lower or "math" in topic_lower:
            bank = MATH_BANK
        elif "sejarah" in topic_lower or "history" in topic_lower:
            bank = HISTORY_BANK
        else:
            bank = DEFAULT_BANK

        for i in range(num_questions):
            if i < len(bank):
                q = bank[i].copy()
            else:
                q = random.choice(bank).copy()
            q["question_text"] = q["question_text"].format(topic=topic)
            q["explanation"] = q["explanation"].format(topic=topic)
            if i >= len(bank):
                q["question_text"] = f"{q['question_text']} (Varian {i + 1})"
            questions.append(q)

        return questions
