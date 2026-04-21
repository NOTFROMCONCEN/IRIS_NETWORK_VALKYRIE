#!/usr/bin/env python3
"""
通知模块
Notifier Module

提供桌面通知功能
"""

import sys
import logging
from typing import Optional
from datetime import datetime


class Notifier:
    """通知器"""
    
    def __init__(self, enabled: bool = True):
        """
        初始化通知器
        
        Args:
            enabled: 是否启用通知
        """
        self.enabled = enabled
        self.logger = logging.getLogger(__name__)
        self._check_availability()
    
    def _check_availability(self):
        """检查通知功能是否可用"""
        if not self.enabled:
            return
        
        self.windows_available = False
        self.linux_available = False
        self.macos_available = False
        
        if sys.platform == "win32":
            try:
                import win10toast
                self.windows_available = True
                self.logger.info("Windows通知功能可用")
            except ImportError:
                self.logger.warning("win10toast未安装，Windows通知不可用")
                self.logger.info("安装命令: pip install win10toast")
        elif sys.platform == "linux":
            try:
                import notify2
                self.linux_available = True
                self.logger.info("Linux通知功能可用")
            except ImportError:
                self.logger.warning("notify2未安装，Linux通知不可用")
                self.logger.info("安装命令: pip install notify2")
        elif sys.platform == "darwin":
            try:
                import pync
                self.macos_available = True
                self.logger.info("macOS通知功能可用")
            except ImportError:
                self.logger.warning("pync未安装，macOS通知不可用")
                self.logger.info("安装命令: pip install pync")
    
    def notify(self, title: str, message: str, duration: int = 5):
        """
        发送桌面通知
        
        Args:
            title: 通知标题
            message: 通知内容
            duration: 显示时长（秒）
        """
        if not self.enabled:
            return
        
        try:
            if sys.platform == "win32" and self.windows_available:
                self._notify_windows(title, message, duration)
            elif sys.platform == "linux" and self.linux_available:
                self._notify_linux(title, message)
            elif sys.platform == "darwin" and self.macos_available:
                self._notify_macos(title, message)
            else:
                self.logger.debug(f"通知功能不可用于平台: {sys.platform}")
        except Exception as e:
            self.logger.error(f"发送通知失败: {e}")
    
    def _notify_windows(self, title: str, message: str, duration: int):
        """发送Windows通知"""
        try:
            from win10toast import Toast
            toast = Toast()
            toast.title = title
            toast.body = message
            toast.duration = duration
            toast.show()
        except Exception as e:
            self.logger.error(f"Windows通知失败: {e}")
    
    def _notify_linux(self, title: str, message: str):
        """发送Linux通知"""
        try:
            import notify2
            notify2.notify(
                title,
                message,
                app_name="网络设备巡检工具",
                icon="",
                timeout=5000,
            )
        except Exception as e:
            self.logger.error(f"Linux通知失败: {e}")
    
    def _notify_macos(self, title: str, message: str):
        """发送macOS通知"""
        try:
            import pync
            pync.notify(
                message,
                title=title,
                app_name="网络设备巡检工具",
                sound="Ping",
            )
        except Exception as e:
            self.logger.error(f"macOS通知失败: {e}")
    
    def notify_completion(self, total: int, success: int, failed: int, duration: float):
        """
        发送完成通知
        
        Args:
            total: 总设备数
            success: 成功数
            failed: 失败数
            duration: 执行时长（秒）
        """
        if not self.enabled:
            return
        
        title = "巡检完成"
        success_rate = (success / total * 100) if total > 0 else 0
        
        if failed == 0:
            message = f"所有设备巡检成功！\n总计: {total}台，耗时: {self._format_duration(duration)}"
        elif success == 0:
            message = f"巡检失败！\n总计: {total}台，全部失败"
        else:
            message = f"巡检部分完成\n成功: {success}台，失败: {failed}台\n成功率: {success_rate:.1f}%"
        
        self.notify(title, message, duration=10)
    
    def notify_error(self, error_message: str):
        """
        发送错误通知
        
        Args:
            error_message: 错误消息
        """
        if not self.enabled:
            return
        
        title = "巡检错误"
        self.notify(title, error_message, duration=10)
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}小时{minutes}分"


# 全局通知器实例
_global_notifier: Optional[Notifier] = None


def get_notifier() -> Notifier:
    """
    获取全局通知器实例
    
    Returns:
        通知器实例
    """
    global _global_notifier
    if _global_notifier is None:
        _global_notifier = Notifier(enabled=True)
    return _global_notifier


def init_notifier(enabled: bool = True):
    """
    初始化全局通知器
    
    Args:
        enabled: 是否启用通知
    """
    global _global_notifier
    _global_notifier = Notifier(enabled=enabled)
