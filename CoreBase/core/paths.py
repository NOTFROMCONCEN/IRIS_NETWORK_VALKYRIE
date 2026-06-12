#!/usr/bin/env python3
"""
路径解析模块

统一将项目内的相对路径解析到 CoreBase 根目录，避免依赖当前工作目录。
"""

from pathlib import Path
from typing import Union


PathValue = Union[str, Path]

COREBASE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = COREBASE_ROOT.parent


def resolve_corebase_path(path_value: PathValue) -> Path:
    """将相对路径解析到 CoreBase 根目录。"""
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return COREBASE_ROOT / path
