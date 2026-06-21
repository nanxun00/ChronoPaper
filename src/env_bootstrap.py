"""在 import transformers / MinerU 之前设置 ML 相关环境变量。

Windows 上若启用用户 site-packages（Roaming\\Python\\Python312\\site-packages），
pip --user 安装的 tensorflow/transformers 会污染 conda 环境，导致 Keras backend 报错。
"""
from __future__ import annotations

import os


def apply_ml_import_env() -> None:
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_TORCH", "1")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    # 解决 Windows 上多个 libiomp5md.dll 冲突导致的 WinError 1114 错误
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


apply_ml_import_env()
