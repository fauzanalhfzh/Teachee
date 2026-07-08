#!/bin/bash
# Script untuk setup Ollama model di VPS
# Jalankan sekali setelah docker-compose up -d

set -e

echo "Menunggu Ollama siap..."
until docker exec teachee_ollama ollama list >/dev/null 2>&1; do
  echo "Menunggu Ollama service..."
  sleep 3
done

echo "Mengunduh base model qwen3.5:0.8b..."
docker exec teachee_ollama ollama pull qwen3.5:0.8b

echo "Membuat custom model quizzy:latest dari Modelfile..."
docker cp modelfiles/QuizModelfile teachee_ollama:/tmp/QuizModelfile
docker exec teachee_ollama ollama create quizzy:latest -f /tmp/QuizModelfile

echo ""
echo "✅ Selesai! Custom model 'quizzy:latest' siap digunakan."
echo "   Cek dengan: docker exec quiz_ollama ollama list"
