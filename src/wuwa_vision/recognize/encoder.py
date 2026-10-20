# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""DINOv2 icon encoder.

Ported from the sibling `wucv` project, whose history records moving
MobileNet -> DINOv2 "because it is more suitable". That is the right call and
supersedes this project's original shortlist (MaxViT / Swin / PvT v2 / CaiT /
Twins-SVT, PLAN.md D10): DINOv2 is self-supervised and strong at *instance*
retrieval, which is exactly the task -- "is this the same object?" rather than
"what category is this?".

The backbone stays frozen and is used as a feature extractor, matching D10 phase 1.
Nothing here trains.

Device selection is VRAM-aware, also ported from wucv: the game contends for VRAM
(~9.5 GB of 16 GB observed in use during profiling), so falling back to CPU when
the card is busy is better than an out-of-memory crash mid-scan.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
from PIL import Image

from .masking import apply_badge_mask

if TYPE_CHECKING:  # heavy imports stay out of the geometry/OCR test path
    import torch

#: dinov2-base over -small: measured on wucv's 27-class labelled set, base gives
#: 95.2% precision at margin 0.02 vs small's 86.7%, and 100% by margin 0.08.
#: ~86M params (~350MB) is affordable even with the game holding most of the VRAM.
DEFAULT_MODEL = "facebook/dinov2-base"
#: Vendored weights (tools/fetch_model.py). The encoder never loads from the Hub:
#: by hub name, transformers contacted huggingface.co on every start (D41).
MODELS_DIR = Path(
    os.environ.get("WUWA_MODEL_DIR", Path(__file__).resolve().parents[3] / "data" / "models")
)


class ModelMissingError(RuntimeError):
    """The vendored weights are not there; nothing is downloaded at runtime."""


def model_dir(model_name: str) -> Path:
    """Where `model_name` is vendored: data/models/<name without the org>."""
    return MODELS_DIR / model_name.split("/")[-1]


#: Bump when preprocessing changes in a way that invalidates stored embeddings.
PREPROCESSOR_VERSION = "2.0-badge-masked"

ImageLike = "str | Path | Image.Image | np.ndarray"


def to_pil(image: str | Path | Image.Image | np.ndarray) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if isinstance(image, np.ndarray):
        return Image.fromarray(image).convert("RGB")
    return Image.open(image).convert("RGB")


@dataclass(frozen=True, slots=True)
class EncoderInfo:
    """Identity of the embedding space. Stored embeddings are only valid for one."""

    model_name: str
    preprocessor_version: str
    embedding_size: int

    def key(self) -> str:
        return f"{self.model_name}|{self.preprocessor_version}|{self.embedding_size}"


class IconEncoder:
    """Frozen DINOv2 encoder producing L2-normalised CLS embeddings."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device_mode: Literal["cuda", "cpu", "auto"] = "auto",
        reserved_vram_gb: float = 2.0,
    ) -> None:
        self.model_name = model_name
        self.device_mode = device_mode
        self.reserved_vram_gb = reserved_vram_gb

    @cached_property
    def _loaded(self) -> tuple[object, object, torch.device]:
        path = model_dir(self.model_name)
        if not (path / "config.json").exists():
            raise ModelMissingError(
                f"{self.model_name} weights not found in {path}. "
                "Run once: uv run python tools/fetch_model.py"
            )
        # Belt and braces for zero egress (AGENTS.md constraint 3): no hub calls,
        # no telemetry, whatever transformers would otherwise do on load.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        import torch
        from transformers import AutoImageProcessor, AutoModel

        processor = AutoImageProcessor.from_pretrained(path, local_files_only=True)
        model = AutoModel.from_pretrained(path, local_files_only=True)
        model.eval()
        device = torch.device(self._pick_device())
        model.to(device)
        return processor, model, device

    def _pick_device(self) -> str:
        """The best device this machine actually has (D70).

        CUDA first, then Intel's XPU (Arc and the Core Ultra iGPUs, which is the
        only GPU path on a Windows machine without an NVIDIA card), then Apple's
        MPS. The VRAM guard is for CUDA alone: there the game is the other tenant
        on the card, and losing the scan to an out-of-memory beats saving seconds.
        """
        import torch

        if self.device_mode != "auto":
            return self.device_mode
        if torch.cuda.is_available():
            free_bytes, _ = torch.cuda.mem_get_info()
            return "cuda" if free_bytes > self.reserved_vram_gb * 1024**3 else "cpu"
        if getattr(torch, "xpu", None) is not None and torch.xpu.is_available():
            return "xpu"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
        return "cpu"

    @property
    def device(self) -> str:
        return str(self._loaded[2])

    @property
    def info(self) -> EncoderInfo:
        _, model, _ = self._loaded
        return EncoderInfo(
            model_name=self.model_name,
            preprocessor_version=PREPROCESSOR_VERSION,
            embedding_size=int(model.config.hidden_size),
        )

    def embed(
        self,
        images: list[str | Path | Image.Image | np.ndarray],
        *,
        mask_badges: bool = True,
        batch_size: int = 32,
    ) -> np.ndarray:
        """Return (N, D) float32 L2-normalised embeddings.

        `mask_badges` must be consistent between gallery and query; that is what
        `PREPROCESSOR_VERSION` guards.
        """
        import torch
        import torch.nn.functional as F

        processor, model, device = self._loaded
        if not images:
            return np.empty((0, self.info.embedding_size), dtype=np.float32)

        out: list[np.ndarray] = []
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            pils = []
            for item in batch:
                pil = to_pil(item)
                if mask_badges:
                    pil = Image.fromarray(apply_badge_mask(np.asarray(pil)))
                pils.append(pil)

            inputs = processor(images=pils, return_tensors="pt").to(device)
            with torch.inference_mode():
                tokens = model(**inputs).last_hidden_state
            cls = F.normalize(tokens[:, 0, :], p=2, dim=-1)
            out.append(cls.detach().cpu().numpy().astype(np.float32))

        return np.concatenate(out, axis=0)
