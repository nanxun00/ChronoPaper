"""GPU / 加速器可用性检测。"""
from __future__ import annotations


def has_gpu_accelerator() -> bool:
    """检测当前环境是否具备可用于 MinerU VLM/Hybrid 的加速器。"""
    try:
        import torch
    except ImportError:
        return False

    if torch.cuda.is_available():
        return True

    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return True

    for attr in ("npu", "gcu", "musa", "mlu", "sdaa"):
        device_mod = getattr(torch, attr, None)
        if device_mod is None:
            continue
        is_available = getattr(device_mod, "is_available", None)
        if callable(is_available) and is_available():
            return True

    return False
