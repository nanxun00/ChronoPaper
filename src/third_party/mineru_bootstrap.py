"""将 vendored MinerU 加入 Python 导入路径。"""
from __future__ import annotations

import sys
from pathlib import Path

_THIRD_PARTY_DIR = Path(__file__).resolve().parent
_BOOTSTRAPPED = False


def ensure_mineru_importable() -> None:
    """确保 `import mineru` 解析到 src/third_party/mineru。"""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    third_party = str(_THIRD_PARTY_DIR)
    if third_party not in sys.path:
        sys.path.insert(0, third_party)

    import mineru  # noqa: F401

    _BOOTSTRAPPED = True
