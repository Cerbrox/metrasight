"""Docker-build-time PaddleOCR model bake (Render Free reliability fix).

Downloads the exact PP-OCRv5 mobile models this deployment uses and leaves
them in ``$PADDLE_PDX_CACHE_HOME/official_models/`` so the runtime NEVER
fetches them. Run inside the Docker image build (see Dockerfile):

    PADDLE_PDX_CACHE_HOME=/opt/paddlex-cache python scripts/bake_ocr_models.py

Why: Render Free has an ephemeral filesystem — the previous deployment
pointed the model cache at /tmp, so every cold start re-downloaded ~22 MB.
With PADDLE_PDX_MODEL_SOURCE defaulting to "huggingface" (1s reachability
probe, then a BOS/Chinese-CDN fallback that crawled at ~3 KB/s from Render's
US instances), that download alone kept the seed run in OCR_PROCESSING for
90+ minutes. PaddleX 3.1.0 resolves official models via
``official_models[key] -> download_and_extract(..., overwrite=False)``, which
SKIPS the download entirely when the model directory already exists — so a
baked cache plus ``PADDLE_PDX_MODEL_SOURCE=BOS`` makes runtime loading a pure
local existence check with zero network calls.

The engine is constructed through the app's own :class:`PaddleOCRService`
with the deployment flags (mobile tier, cpu_threads=1, mkldnn disabled) so
the baked models and predictor options are exactly what the runtime loads.
This is a real engine build, NOT a mock: if model download or load fails,
the Docker build fails loudly.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ocr.paddle import PaddleOCRService  # noqa: E402


def main() -> int:
    cache = os.environ.get("PADDLE_PDX_CACHE_HOME")
    if not cache:
        raise SystemExit(
            "PADDLE_PDX_CACHE_HOME must be set so the baked cache location is "
            "explicit and stable between build and runtime."
        )
    started = time.monotonic()
    service = PaddleOCRService(
        langs=["en"],
        model_tier="mobile",
        cpu_threads=1,
        enable_mkldnn=False,
    )
    service.prewarm()  # downloads (if missing) + loads det/rec engines
    elapsed = round(time.monotonic() - started, 1)
    print(f"baked_paddle_models cache={cache} elapsed_seconds={elapsed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
