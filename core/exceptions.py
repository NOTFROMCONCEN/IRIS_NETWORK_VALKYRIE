#!/usr/bin/env python3
"""
异常处理模块
Exception Handling Module

提供自定义异常和错误处理功能
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(Enum):
    """错误代码枚举"""
    # 配置错误
    CONFIG_INVALID = 1001
    CONFIG_MISSING = 1002
    CONFIG_TYPE_ERROR = 1003
    
    # 设备错误
    DEVICE_NOT_FOUND = 2001
    DEVICE_INVALID = 2002
    DEVICE_DUPLICATE = 2003
    DEVICE_UNSUPPORTED = 2004
    
    # 连接错误
    CONNECTION_TIMEOUT = 3001
    CONNECTION_REFUSED = 3002
    CONNECTION_AUTH_FAILED = 3003
    CONNECTION_FAILED = 3004
    
    # 网络错误
    NETWORK_UNREACHABLE = 4001
    NETWORK_PING_FAILED = 4002
    NETWORK_PORT_CLOSED = 4003
    
    # 文件错误
    FILE_NOT_FOUND = 5001
    FILE_PERMISSION = 5002
    FILE_READ_ERROR = 5003
    FILE_WRITE_ERROR = 5004
    FILE_DISK_FULL = 5005
    
    # 系统错误
    SYSTEM_DISK_FULL = 6001
    SYSTEM_MEMORY_LOW = 6002
    SYSTEM_CPU_HIGH = 6003


class InspectionError(Exception):
    """巡检工具基础异常"""
    
    def __init__(self, code: ErrorCode, message: str, details: Optional[str] = None):
        """
        初始化异常
        
        Args:
            code: 错误代码
            message: 错误消息
            details: 错误详情
        """
        self.code = code
        self.message = message
        self.details = details
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """格式化错误消息"""
        msg = f"[{self.code.name}] {self.message}"
        if self.details:
            msg += f": {self.details}"
        return msg
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": self.code.value,
            "code_name": self.code.name,
            "message": self.message,
            "details": self.details
        }


class ConfigError(InspectionError):
    """配置错误"""
    pass


class DeviceError(InspectionError):
    """设备错误"""
    pass


class ConnectionError(InspectionError):
    """连接错误"""
    pass


class NetworkError(InspectionError):
    """网络错误"""
    pass


class FileError(InspectionError):
    """文件错误"""
    pass


class SystemError(InspectionError):
    """系统错误"""
    pass


def format_error(error: Exception) -> str:
    """
    格式化异常为用户友好的消息
    
    Args:
        error: 异常对象
        
    Returns:
        格式化的错误消息
    """
    if isinstance(error, InspectionError):
        return error._format_message()
    
    # 处理常见异常
    error_messages = {
        FileNotFoundError: "文件不存在",
        PermissionError: "权限不足",
        TimeoutError: "操作超时",
        ConnectionRefusedError: "连接被拒绝",
        ConnectionResetError: "连接被重置",
        ConnectionAbortedError: "连接被中止",
    }
    
    error_type = type(error)
    if error_type in error_messages:
        return f"{error_messages[error_type]}: {str(error)}"
    
    # 默认处理
    return f"错误: {str(error)}"


def get_error_suggestion(error: Exception) -> Optional[str]:
    """
    获取错误解决建议
    
    Args:
        error: 异常对象
        
    Returns:
        解决建议
    """
    if isinstance(error, InspectionError):
        suggestions = {
            ErrorCode.CONFIG_INVALID: "请检查配置文件格式和内容",
            ErrorCode.CONFIG_MISSING: "请确保配置文件存在",
            ErrorCode.DEVICE_NOT_FOUND: "请检查设备配置",
            ErrorCode.DEVICE_INVALID: "请检查设备信息是否完整",
            ErrorCode.CONNECTION_TIMEOUT: "请检查网络连接和设备状态",
            ErrorCode.CONNECTION_AUTH_FAILED: "请检查用户名和密码",
            ErrorCode.FILE_DISK_FULL: "请清理磁盘空间",
            ErrorCode.SYSTEM_DISK_FULL: "请清理磁盘空间",
            ErrorCode.SYSTEM_MEMORY_LOW: "请关闭其他程序或增加内存",
        }
        return suggestions.get(error.code)
    
    # 处理常见异常
    if isinstance(error, FileNotFoundError):
        return "请检查文件路径是否正确"
    if isinstance(error, PermissionError):
        return "请检查文件权限或以管理员身份运行"
    if isinstance(error, TimeoutError):
        return "请检查网络连接或增加超时时间"
    
    return None


def handle_error(error: Exception, context: str = "") -> tuple:
    """
    处理错误并返回格式化信息
    
    Args:
        error: 异常对象
        context: 错误上下文
        
    Returns:
        (错误消息, 解决建议)
    """
    message = format_error(error)
    suggestion = get_error_suggestion(error)
    
    if context:
        message = f"[{context}] {message}"
    
    return message, suggestion
