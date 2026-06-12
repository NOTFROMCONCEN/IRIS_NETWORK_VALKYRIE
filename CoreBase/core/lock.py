#!/usr/bin/env python3
"""
巡检任务锁模块

提供文件锁和进程锁机制，防止 CLI 与 WEB 同时执行巡检任务。

锁文件存放于 CoreBase/output/.inspection_lock，包含：
    - pid: 持有锁的进程ID
    - started_at: 巡检开始时间（ISO 8601）
    - mode: 启动模式（cli / web）
    - description: 可选描述
"""

import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from .paths import resolve_corebase_path


DEFAULT_LOCK_FILE = "output/.inspection_lock"
LOCK_TIMEOUT_SECONDS = 7200  # 锁最长持有时间（2小时），超时自动失效


@dataclass
class LockInfo:
    """锁信息数据类"""
    pid: int
    started_at: str
    mode: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "started_at": self.started_at,
            "mode": self.mode,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LockInfo":
        return cls(
            pid=data.get("pid", 0),
            started_at=data.get("started_at", ""),
            mode=data.get("mode", "unknown"),
            description=data.get("description", ""),
        )


class InspectionLock:
    """巡检任务锁

    基于文件锁实现，支持跨进程互斥。
    同时通过进程存在性检测（PID 存活检查）处理崩溃残留锁。
    """

    def __init__(self, lock_file: str = DEFAULT_LOCK_FILE):
        self.lock_path = resolve_corebase_path(lock_file)
        # 确保目录存在
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_lock(self) -> Optional[LockInfo]:
        """读取锁文件内容，若不存在或损坏返回 None。"""
        if not self.lock_path.exists():
            return None
        try:
            with open(self.lock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return LockInfo.from_dict(data)
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    def _write_lock(self, info: LockInfo) -> bool:
        """写入锁文件。"""
        try:
            # 原子写入：先写临时文件再重命名
            tmp_path = self.lock_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(info.to_dict(), f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.lock_path)
            return True
        except OSError:
            return False

    def _is_process_alive(self, pid: int) -> bool:
        """检测指定 PID 的进程是否存活（跨平台）。"""
        if pid <= 0:
            return False
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            # 降级：使用 os.kill(0) 检测
            if sys.platform == "win32":
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.OpenProcess(1, False, pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        return True
                    return False
                except Exception:
                    return True  # 无法检测时保守返回存活
            else:
                try:
                    os.kill(pid, 0)
                    return True
                except (OSError, ProcessLookupError):
                    return False

    def _is_lock_expired(self, info: LockInfo) -> bool:
        """检查锁是否已超时。"""
        try:
            started = datetime.fromisoformat(info.started_at)
            # 处理带时区的日期
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            elapsed = (now - started).total_seconds()
            return elapsed > LOCK_TIMEOUT_SECONDS
        except (ValueError, TypeError):
            return True  # 时间格式错误视为已过期

    def is_locked(self) -> bool:
        """当前是否已有有效锁（考虑进程存活与超时）。"""
        info = self._read_lock()
        if info is None:
            return False

        # 锁已超时
        if self._is_lock_expired(info):
            self.release()
            return False

        # 持有锁的进程已不存在
        if not self._is_process_alive(info.pid):
            self.release()
            return False

        return True

    def get_lock_info(self) -> Optional[LockInfo]:
        """获取当前锁信息（仅在锁有效时返回）。"""
        if self.is_locked():
            return self._read_lock()
        return None

    def acquire(self, mode: str = "cli", description: str = "", force: bool = False) -> bool:
        """尝试获取锁。

        Args:
            mode: 启动模式（cli / web）
            description: 描述信息
            force: 是否强制获取（会覆盖现有锁）

        Returns:
            是否成功获取
        """
        if not force and self.is_locked():
            return False

        info = LockInfo(
            pid=os.getpid(),
            started_at=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            description=description,
        )
        return self._write_lock(info)

    def release(self) -> bool:
        """释放锁。"""
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
            return True
        except OSError:
            return False

    def __enter__(self):
        """上下文管理器入口（不自动获取锁，仅提供便捷访问）。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        return False


@contextmanager
def inspection_lock_guard(
    mode: str = "cli",
    description: str = "",
    force: bool = False,
    lock_file: str = DEFAULT_LOCK_FILE,
):
    """巡检锁上下文管理器。

    用法：
        with inspection_lock_guard(mode="cli"):
            # 执行巡检...

    若获取锁失败会抛出 RuntimeError。
    退出上下文时自动释放锁。
    """
    lock = InspectionLock(lock_file)
    if not lock.acquire(mode=mode, description=description, force=force):
        info = lock.get_lock_info()
        if info:
            raise RuntimeError(
                f"巡检任务锁被占用。"
                f"PID={info.pid}, 模式={info.mode}, 开始于={info.started_at}"
            )
        raise RuntimeError("巡检任务锁被占用，无法获取锁信息")

    try:
        yield lock
    finally:
        lock.release()


def check_inspection_status(lock_file: str = DEFAULT_LOCK_FILE) -> Dict[str, Any]:
    """检查当前巡检状态，返回状态字典（供 UI 与 CLI 查询）。

    Returns:
        {
            "running": bool,
            "pid": int | None,
            "mode": str,
            "started_at": str,
            "description": str,
        }
    """
    lock = InspectionLock(lock_file)
    info = lock.get_lock_info()
    if info:
        return {
            "running": True,
            "pid": info.pid,
            "mode": info.mode,
            "started_at": info.started_at,
            "description": info.description,
        }
    return {
        "running": False,
        "pid": None,
        "mode": "",
        "started_at": "",
        "description": "",
    }


def wait_for_lock_release(
    lock_file: str = DEFAULT_LOCK_FILE,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
) -> bool:
    """等待锁释放（轮询方式）。

    Returns:
        True: 锁已释放
        False: 等待超时
    """
    lock = InspectionLock(lock_file)
    start = time.time()
    while lock.is_locked():
        if time.time() - start > timeout:
            return False
        time.sleep(poll_interval)
    return True
