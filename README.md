# Teachee API 

Backend API untuk Teacher Module yang memungkinkan pembuatan kuis (AI-generated), pengelolaan pertanyaan (regenerasi/edit/hapus), publikasi kuis, manajemen kelas (classroom), serta pelaporan statistik nilai siswa. Project ini dibangun menggunakan **FastAPI** dan menggunakan **Raw SQL (PostgreSQL)** untuk interaksi database.

---

## 🚀 Fitur Utama

1. **Authentication (JWT)**: Registrasi dan login untuk guru dan siswa dengan enkripsi password (`bcrypt`) dan autentikasi token JWT.
2. **AI Quiz Generation**: Pembuatan kuis secara otomatis berdasarkan topik, subjek, dan kelas menggunakan sistem AI generator (di-mock menggunakan database bank soal interaktif).
3. **Question Management**:
   - Regenerasi soal tertentu secara instan jika dirasa tidak cocok.
   - Edit manual teks soal, pilihan jawaban (options), kunci jawaban, dan penjelasan.
   - Penghapusan soal dari draf kuis.
4. **Classroom Management**: CRUD Data kelas (Classroom), pendaftaran siswa ke kelas, serta daftar detail kelas beserta siswa di dalamnya.
5. **Quiz Reports & Analytics**: Laporan nilai rata-rata, nilai tertinggi/terendah, tingkat partisipasi kelas, serta riwayat pengerjaan siswa secara detail. Jika kuis belum dikerjakan, sistem secara otomatis mensimulasikan data pengerjaan (auto-seed) untuk kemudahan pengujian.

---

## 📁 Struktur Folder Proyek

- `main.py`: Entry point dari FastAPI application.
- `core/`: Modul konfigurasi sistem.
  - `database.py`: Inisialisasi pool koneksi database PostgreSQL (`psycopg2-binary`) dan migrasi DDL otomatis.
  - `security.py`: Fungsi pembantu untuk hash password (`bcrypt`) dan pembuatan token JWT (`pyjwt`).
  - `seeding.py`: Seed data awal (default guru, kelas, dan murid) ke database saat aplikasi pertama kali dijalankan.
- `app/api/v1/`: Berisi routing dan controller API.
  - `router.py`: Pintu masuk utama pendaftaran router `/auth`, `/quizzes`, `/questions`, `/classrooms`.
  - `endpoints/`: Penanganan logika API untuk masing-masing modul.
- `services/`: Berisi service logika bisnis eksternal/AI.
  - `ai_service.py`: Logika pembuatan/penyusunan soal kuis berbasis topik.
- `schemas/`: Pydantic model untuk validasi request dan response serialization.
- `Dockerfile` & `docker-compose.yml`: Konfigurasi kontainerisasi aplikasi dan PostgreSQL database.

---

## 🛠️ Persyaratan Sistem

Pastikan Anda telah memasang tool berikut di komputer Anda:

- Docker & Docker Compose
- Python 3.10+ (jika ingin dijalankan secara lokal tanpa Docker)
- PostgreSQL (jika ingin dijalankan secara lokal tanpa Docker)

---

## ⚙️ Cara Memulai & Menjalankan Aplikasi

### Opsi A: Menggunakan Docker Compose (Sangat Direkomendasikan)

Metode ini paling mudah karena Docker akan menginisialisasi database PostgreSQL, server FastAPI, dan pgAdmin secara otomatis.

1. Salin `.env.example` menjadi `.env`:
   ```bash
   cp .env.example .env
   ```
   > [!IMPORTANT]
   > **JWT_SECRET_KEY wajib diisi** — gunakan key acak berikut:
   > ```bash
   > python3 -c "import secrets; print(secrets.token_hex(32))"
   > ```
   > Tempelkan hasilnya ke `JWT_SECRET_KEY` di file `.env`.

2. Jalankan perintah berikut di direktori root proyek:
   ```bash
   docker compose up --build
   ```
3. Aplikasi akan berjalan di port `8000`:
   - **Base API URL**: `http://localhost:8000`
   - **Swagger UI Docs**: `http://localhost:8000/docs`
   - **ReDoc Docs**: `http://localhost:8000/redoc`
   - **pgAdmin**: `http://localhost:8080` (Email: `admin@school.com`, Password: `adminpassword`)

4. Siapkan model AI Ollama (cukup sekali):
   ```bash
   bash scripts/setup-ollama.sh
   ```
   > Script ini menunggu Ollama siap, mengunduh base model, lalu membuat custom model `quizzy:latest` dari `modelfiles/QuizModelfile`.

### Opsi B: Menjalankan Secara Lokal (Tanpa Docker)

1. Buat virtual environment Python dan aktifkan:
   ```bash
   python -m venv venv
   # Di Windows (PowerShell/CMD):
   .\venv\Scripts\activate
   # Di macOS/Linux:
   source venv/bin/activate
   ```
2. Pasang semua dependensi proyek:
   ```bash
   pip install -r requirements.txt
   ```
3. Salin `.env.example` menjadi `.env` dan sesuaikan konfigurasinya:
   ```bash
   cp .env.example .env
   ```
   Contoh isi `.env`:
   ```env
   DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<nama_db>
   JWT_SECRET_KEY=change-this-to-a-random-secret-key
   JWT_ALGORITHM=HS256
   ```
   > [!IMPORTANT]
   > **JWT_SECRET_KEY wajib diisi** — server tidak akan start tanpa key ini. Gunakan key acak yang aman:
   > ```bash
   > python3 -c "import secrets; print(secrets.token_hex(32))"
   > ```
4. Jalankan aplikasi menggunakan Uvicorn:
   ```bash
   uvicorn main:app --reload
   ```

---

## 📊 Data Awal (Seeding)

Saat database dijalankan untuk pertama kali, aplikasi akan otomatis memigrasi tabel dan menyuntikkan data seed berikut:

- **Guru Default**:
  - Email: `teacher@school.com`
  - Password: `password123`
- **Kelas Default**:
  - Nama: `Kelas 10A`
- **Siswa Default**:
  - `adit@school.com` (Password: `password123`)
  - `bambang@school.com` (Password: `password123`)

_Catatan: UUID hasil seeding guru dan kelas akan tercetak di console/log startup aplikasi saat kontainer `quiz_fastapi_app` dimulai. UUID ini dibutuhkan untuk pengujian API._

---

## 🧪 Pengujian API

Proyek ini dilengkapi dengan file REST Client (`.http`) untuk mempermudah Anda melakukan uji coba endpoint langsung dari VS Code (menggunakan ekstensi _REST Client_) atau IDE JetBrains (seperti PyCharm/WebStorm).

1. **`test_auth.http`**: Pengujian alur registrasi guru baru, login akun baru, dan pengambilan profil menggunakan token JWT.
2. **`test_api.http`**: Pengujian alur pembuatan kuis draft lewat AI, regenerasi soal spesifik, pengeditan manual soal oleh guru, penghapusan soal, publikasi kuis, serta melihat statistik & performa murid.
3. **`test_main.http`**: Pengujian endpoint root selamat datang.

### Cara Cepat Menguji Alur Utama:

1. Lakukan **POST** ke `/api/v1/auth/login` menggunakan kredensial seed:
   ```json
   {
     "email": "teacher@school.com",
     "password": "password123"
   }
   ```
2. Ambil token yang didapatkan dan masukkan sebagai `Authorization: Bearer <token>` pada request-request di `test_api.http`.
3. Jalankan pembuat kuis (`/quizzes/generate`) dengan parameter:
   ```json
   {
     "classroom_id": "<uuid-kelas-10A>",
     "teacher_id": "<uuid-guru-budi>",
     "title": "Kuis Aljabar Linear Dasar",
     "subject": "Matematika",
     "topic": "Aljabar",
     "num_questions": 5
   }
   ```
4. Cobalah mengambil API Laporan `/api/v1/quizzes/{quiz_id}/reports`. Jika siswa belum mengisi kuis tersebut, sistem akan secara otomatis mensimulasikan nilai dan pengerjaan murid-murid di kelas 10A untuk mempermudah visualisasi data statistik!

---

## 🐳 Panduan Docker untuk Tim Frontend (FE)

Bagi tim Frontend yang ingin menjalankan server Backend secara lokal tanpa perlu menginstal Python atau PostgreSQL di mesin lokal, ikuti panduan berikut ini:

### 1. Prasyarat
Pastikan Anda sudah menginstal **Docker Desktop** dan aplikasinya sedang berjalan di komputer Anda.

### 2. Cara Menjalankan Backend (Background Mode)
Agar terminal Anda tidak terblokir oleh log server, jalankan kontainer dalam mode *detached* (`-d`):

```bash
docker-compose up -d --build
```

Setelah perintah selesai dijalankan, kontainer backend (`quiz_fastapi_app`), database PostgreSQL (`quiz_postgres_db`), dan pgAdmin (`quiz_pgadmin`) akan berjalan di latar belakang.

### 3. Memantau Status & Log Kontainer
- **Cek Status Kontainer**:
  ```bash
  docker ps
  ```
  Pastikan ada tiga kontainer berjalan.
  
- **Melihat Log Realtime** (untuk melihat error, debug, atau mengambil UUID hasil seeding):
  ```bash
  docker logs -f quiz_fastapi_app
  ```

### 4. Integrasi dengan Frontend (API Base URL)
- **Base URL API**: `http://localhost:8000/api/v1`
- **CORS**: CORS telah diaktifkan untuk semua origin (`*`) pada port lokal backend, sehingga Anda dapat langsung melakukan `fetch` atau `axios` dari repositori frontend Anda (seperti `http://localhost:3000` atau `http://localhost:5173`) tanpa kendala CORS.

### 5. Dokumentasi API Interaktif (Swagger UI)
Anda bisa melihat spesifikasi endpoint, parameter request, dan skema respons di:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)** (Swagger UI)

Anda juga bisa melakukan ujicoba request (Try it out) langsung melalui halaman tersebut.

### 6. Akun Uji Coba Default & Seeding
Database akan otomatis terisi data awal ketika pertama kali dijalankan. Gunakan akun berikut untuk login lewat API `/api/v1/auth/login` guna mendapatkan Token JWT:

- **Akun Guru (Teacher)**:
  - **Email**: `teacher@school.com`
  - **Password**: `password123`
- **Akun Siswa (Student)**:
  - **Email**: `adit@school.com` (atau `bambang@school.com`)
  - **Password**: `password123`

> [!TIP]
> **UUID Guru** dan **UUID Kelas** default yang diperlukan saat membuat kuis baru (`POST /quizzes/generate`) akan tercetak pada log startup kontainer. Gunakan `docker logs quiz_fastapi_app` untuk melihat UUID tersebut.

### 7. Perintah Docker Penting Lainnya
- **Menghentikan Server**:
  ```bash
  docker-compose down
  ```
- **Menghentikan dan Menghapus Database (Reset Data)**:
  Jika ingin menghapus semua database kuis dan melakukan seed ulang dari awal, hapus volume PostgreSQL dengan perintah:
  ```bash
  docker-compose down -v
  ```
