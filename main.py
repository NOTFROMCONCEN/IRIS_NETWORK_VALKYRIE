#!/usr/bin/env python3
"""
仓库根目录程序入口。

用途：
1. 统一从仓库根目录启动程序（python main.py）
2. 自动切换到 CoreBase 目录，确保相对路径兼容
3. 复用 CoreBase/main.py 的完整 CLI 能力
"""

import os
import sys
from pathlib import Path


def bootstrap() -> int:
    """初始化运行环境并委托给 CoreBase 主程序。"""
    repo_root = Path(__file__).resolve().parent
    corebase_dir = repo_root / "CoreBase"

    if not corebase_dir.exists():
        print(f"[错误] 未找到 CoreBase 目录: {corebase_dir}")
        return 1

    # 切换工作目录，保持 CoreBase 中的相对路径行为不变。
    os.chdir(corebase_dir)

    # 将仓库根加入模块搜索路径，以便导入 CoreBase.main。
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from CoreBase.main import main as core_main
    except Exception as exc:
        print(f"[错误] 加载 CoreBase 入口失败: {exc}")
        return 1

    return core_main()


if __name__ == "__main__":
    try:
        sys.exit(bootstrap())
    except KeyboardInterrupt:
        print("\n[中断] 用户中断操作")
        sys.exit(130)
