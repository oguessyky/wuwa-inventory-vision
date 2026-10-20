# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Vendor the DINOv2 weights into data/models/, once.

The encoder loads ONLY from that folder (recognize/encoder.py). Loading by hub
name made transformers contact the Hugging Face Hub on every `wuwa live` start
("You are sending unauthenticated requests to the HF Hub") -- a runtime request,
which AGENTS.md hard constraint 3 forbids ("no runtime model downloads, vendor
weights ahead of time").

This is a ONE-TIME setup step, like tools/fetch_catalogue.py. Re-running it is
harmless: files already present are kept. `data/` is gitignored.

Run:  uv run python tools/fetch_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wuwa_vision.recognize.encoder import DEFAULT_MODEL, model_dir  # noqa: E402


def main() -> int:
    from huggingface_hub import snapshot_download

    dest = model_dir(DEFAULT_MODEL)
    path = snapshot_download(
        DEFAULT_MODEL,
        local_dir=dest,
        # Weights, config and preprocessor only: no duplicate pytorch_model.bin.
        allow_patterns=["*.json", "*.safetensors"],
    )
    files = [p for p in Path(path).iterdir() if p.is_file()]
    size = sum(p.stat().st_size for p in files) / 1e6
    print(f"{DEFAULT_MODEL} -> {path}  ({len(files)} files, {size:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
