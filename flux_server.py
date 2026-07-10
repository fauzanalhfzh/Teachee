import io
import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import Response
import torch
from diffusers import FluxPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flux")

app = FastAPI(title="FLUX Image Generator")

MODEL_ID = os.getenv("FLUX_MODEL", "black-forest-labs/FLUX.1-dev")
HF_TOKEN = os.getenv("HF_TOKEN", "")
DTYPE = torch.bfloat16

pipe = None

class GenerateRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    guidance_scale: float = 3.5
    num_inference_steps: int = 28

@app.on_event("startup")
def load_model():
    global pipe
    logger.info(f"Loading FLUX model: {MODEL_ID}")
    try:
        token = HF_TOKEN if HF_TOKEN else None
        pipe = FluxPipeline.from_pretrained(MODEL_ID, torch_dtype=DTYPE, token=token)

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info(f"GPU detected: {name}")
            pipe.enable_sequential_cpu_offload()
            logger.info("FLUX model loaded (sequential CPU offload)")
        else:
            logger.warning("No GPU detected, running on CPU (slow)")
    except Exception as e:
        logger.error(f"Failed to load FLUX model: {e}")
        raise

@app.post("/generate")
def generate_image(payload: GenerateRequest):
    global pipe
    logger.info(f"Generating image for prompt: {payload.prompt[:100]}...")
    image = pipe(
        prompt=payload.prompt,
        width=payload.width,
        height=payload.height,
        guidance_scale=payload.guidance_scale,
        num_inference_steps=payload.num_inference_steps,
    ).images[0]

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "device": str(pipe.device) if pipe else "not loaded"}
