import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FLUX_URL = os.getenv("FLUX_URL", "http://flux:8000")
REQUEST_TIMEOUT = int(os.getenv("FLUX_TIMEOUT", "120"))


class FluxClient:

    @staticmethod
    def generate_image(prompt: str) -> Optional[bytes]:
        try:
            with httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT)) as client:
                resp = client.post(
                    f"{FLUX_URL.rstrip('/')}/generate",
                    json={
                        "prompt": prompt,
                        "width": 1024,
                        "height": 1024,
                        "guidance_scale": 3.5,
                        "num_inference_steps": 28,
                    },
                )
                resp.raise_for_status()
                logger.info(f"FLUX generated image for prompt: {prompt[:80]}...")
                return resp.content

        except httpx.TimeoutException:
            logger.error(f"FLUX request timed out after {REQUEST_TIMEOUT}s")
            return None
        except httpx.ConnectError:
            logger.error(f"Cannot connect to FLUX at {FLUX_URL}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"FLUX returned HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling FLUX: {e}")
            return None
