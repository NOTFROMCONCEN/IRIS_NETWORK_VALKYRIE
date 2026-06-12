#!/usr/bin/env python3
"""
UI模块 - 网络设备管理界面
"""

__version__ = "1.0.0"
__author__ = "Network Inspection Tool UI Module"


from .device_manager import DeviceManager
from .app import main as run_ui


def start_ui():
    """启动UI界面"""
    import sys
    from pathlib import Path

    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # 导入并运行Streamlit应用
    import subprocess
    import os

    # 获取当前文件路径
    ui_app_path = os.path.join(os.path.dirname(__file__), "app.py")

    # 启动Streamlit
    print(f"[信息] 启动设备管理UI界面...")
    print(f"[信息] 请访问 http://localhost:8501")
    print(f"[信息] 按 Ctrl+C 停止服务")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", ui_app_path],
            check=True,
            cwd=str(project_root),
        )
    except KeyboardInterrupt:
        print("\n[信息] UI服务已停止")
    except Exception as e:
        print(f"[错误] 启动UI失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    start_ui()
