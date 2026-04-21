#!/usr/bin/env python3
"""
性能监控模块
Performance Monitor Module

提供资源使用监控和性能统计功能
"""

import time
import psutil
from typing import Dict, Any, Optional
from datetime import datetime


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        """初始化性能监控器"""
        self.start_time = None
        self.end_time = None
        self.device_times = {}  # 设备执行时间记录
        self.resource_usage = []  # 资源使用记录
        
    def start(self):
        """开始监控"""
        self.start_time = time.time()
        self._record_resource_usage("启动")
        
    def stop(self):
        """停止监控"""
        self.end_time = time.time()
        self._record_resource_usage("结束")
        
    def record_device_start(self, device_name: str):
        """记录设备开始时间"""
        self.device_times[device_name] = {
            "start": time.time(),
            "end": None,
            "duration": None
        }
        
    def record_device_end(self, device_name: str):
        """记录设备结束时间"""
        if device_name in self.device_times:
            self.device_times[device_name]["end"] = time.time()
            self.device_times[device_name]["duration"] = (
                self.device_times[device_name]["end"] - 
                self.device_times[device_name]["start"]
            )
    
    def _record_resource_usage(self, label: str):
        """记录资源使用情况"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            self.resource_usage.append({
                "time": datetime.now().isoformat(),
                "label": label,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "disk_free_mb": disk.free / (1024 * 1024),
            })
        except Exception as e:
            # 忽略监控错误，不影响主程序
            pass
    
    def get_summary(self) -> Dict[str, Any]:
        """获取性能统计摘要"""
        if self.start_time is None or self.end_time is None:
            return {}
        
        total_duration = self.end_time - self.start_time
        
        # 计算平均资源使用
        avg_cpu = sum(r["cpu_percent"] for r in self.resource_usage) / len(self.resource_usage) if self.resource_usage else 0
        avg_memory = sum(r["memory_percent"] for r in self.resource_usage) / len(self.resource_usage) if self.resource_usage else 0
        
        # 计算设备统计
        device_count = len(self.device_times)
        device_times = [d["duration"] for d in self.device_times.values() if d["duration"]]
        avg_device_time = sum(device_times) / len(device_times) if device_times else 0
        max_device_time = max(device_times) if device_times else 0
        min_device_time = min(device_times) if device_times else 0
        
        return {
            "total_duration": total_duration,
            "total_duration_formatted": self._format_duration(total_duration),
            "device_count": device_count,
            "avg_device_time": avg_device_time,
            "avg_device_time_formatted": self._format_duration(avg_device_time),
            "max_device_time": max_device_time,
            "max_device_time_formatted": self._format_duration(max_device_time),
            "min_device_time": min_device_time,
            "min_device_time_formatted": self._format_duration(min_device_time),
            "avg_cpu_percent": avg_cpu,
            "avg_memory_percent": avg_memory,
            "resource_samples": len(self.resource_usage),
        }
    
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
    
    def check_resource_warning(self, cpu_threshold: float = 80.0, memory_threshold: float = 80.0) -> Optional[str]:
        """
        检查资源使用是否超过阈值
        
        Args:
            cpu_threshold: CPU使用率阈值（百分比）
            memory_threshold: 内存使用率阈值（百分比）
            
        Returns:
            警告信息，如果没有超过阈值则返回None
        """
        if not self.resource_usage:
            return None
        
        latest = self.resource_usage[-1]
        warnings = []
        
        if latest["cpu_percent"] > cpu_threshold:
            warnings.append(f"CPU使用率过高: {latest['cpu_percent']:.1f}%")
        
        if latest["memory_percent"] > memory_threshold:
            warnings.append(f"内存使用率过高: {latest['memory_percent']:.1f}%")
        
        if latest["disk_free_mb"] < 100:
            warnings.append(f"磁盘空间不足: {latest['disk_free_mb']:.1f}MB")
        
        return "; ".join(warnings) if warnings else None
    
    def print_summary(self):
        """打印性能摘要"""
        summary = self.get_summary()
        if not summary:
            return
        
        print("\n" + "=" * 60)
        print("[性能] 性能统计摘要")
        print("=" * 60)
        print(f"总执行时间: {summary['total_duration_formatted']}")
        print(f"设备数量: {summary['device_count']} 台")
        print(f"平均设备时间: {summary['avg_device_time_formatted']}")
        print(f"最慢设备: {summary['max_device_time_formatted']}")
        print(f"最快设备: {summary['min_device_time_formatted']}")
        print(f"平均CPU使用: {summary['avg_cpu_percent']:.1f}%")
        print(f"平均内存使用: {summary['avg_memory_percent']:.1f}%")
        
        # 检查资源警告
        warning = self.check_resource_warning()
        if warning:
            print(f"\n[警告] {warning}")
        
        print("=" * 60)
