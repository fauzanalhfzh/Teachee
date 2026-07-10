FROM rocm/pytorch:latest

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    diffusers>=0.30.0 \
    transformers \
    accelerate \
    sentencepiece \
    Pillow

COPY flux_server.py .

EXPOSE 8000

CMD ["uvicorn", "flux_server:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "asyncio"]
