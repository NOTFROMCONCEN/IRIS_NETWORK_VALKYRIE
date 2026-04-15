#!/usr/bin/env python3
"""
结果保存器模块
Result Saver Module

负责保存巡检结果和生成报告
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any


class ResultSaver:
    """结果保存器"""

    def __init__(self, output_dir: str = "output/results"):
        """
        初始化结果保存器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger.info(f"结果保存器已初始化: {self.output_dir}")

    def save_result(
        self, device_name: str, ip: str, command_type: str, output: str, vendor: str
    ):
        """
        保存命令结果

        Args:
            device_name: 设备名称
            ip: 设备IP
            command_type: 命令类型
            output: 输出内容
            vendor: 厂商
        """
        try:
            # 文件名格式: 设备名(IP)(日期)(厂商).log
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"{device_name}({ip})({date_str})({vendor}).log"
            filepath = os.path.join(self.output_dir, filename)

            # 追加模式写入
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"命令类型: {command_type}\n")
                f.write(f"{'='*60}\n")
                f.write(output)
                f.write(f"\n{'='*60}\n\n")

            self.logger.debug(f"结果已保存: {filepath}")

        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")
            print(f"[错误] 保存结果失败: {e}")

    def save_summary(self, results: Dict[str, Any], filename: str = None):
        """
        保存巡检汇总报告

        Args:
            results: 结果统计字典
            filename: 自定义文件名（可选）
        """
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"summary_{timestamp}.txt"

            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=" * 70 + "\n")
                f.write("网络设备巡检汇总报告\n")
                f.write("Network Device Inspection Summary Report\n")
                f.write("=" * 70 + "\n\n")

                f.write(
                    f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )

                f.write("=" * 70 + "\n")
                f.write("总体统计\n")
                f.write("=" * 70 + "\n")
                f.write(f"总设备数: {results.get('total', 0)} 台\n")
                f.write(f"成功: {results.get('success', 0)} 台\n")
                f.write(f"失败: {results.get('failed', 0)} 台\n")

                if results.get("total", 0) > 0:
                    success_rate = (results.get("success", 0) / results["total"]) * 100
                    f.write(f"成功率: {success_rate:.1f}%\n")

                f.write("\n")

                # 详细列表
                if results.get("details"):
                    f.write("=" * 70 + "\n")
                    f.write("设备详细列表\n")
                    f.write("=" * 70 + "\n\n")

                    # 成功设备
                    success_devices = [d for d in results["details"] if d.get("status")]
                    if success_devices:
                        f.write(f"成功设备 ({len(success_devices)} 台):\n")
                        f.write("-" * 70 + "\n")
                        for idx, device in enumerate(success_devices, 1):
                            f.write(f"{idx}. {device.get('device', 'unknown')} ")
                            f.write(f"({device.get('ip', 'unknown')}) ")
                            f.write(f"[{device.get('vendor', 'unknown')}]\n")
                        f.write("\n")

                    # 失败设备
                    failed_devices = [
                        d for d in results["details"] if not d.get("status")
                    ]
                    if failed_devices:
                        f.write(f"失败设备 ({len(failed_devices)} 台):\n")
                        f.write("-" * 70 + "\n")
                        for idx, device in enumerate(failed_devices, 1):
                            f.write(f"{idx}. {device.get('device', 'unknown')} ")
                            f.write(f"({device.get('ip', 'unknown')}) ")
                            f.write(f"[{device.get('vendor', 'unknown')}]\n")
                            error = device.get("error", "未知错误")
                            f.write(f"   错误: {error}\n")
                        f.write("\n")

                f.write("=" * 70 + "\n")
                f.write("报告结束\n")
                f.write("=" * 70 + "\n")

            print(f"[保存] 汇总报告已保存: {filepath}")
            self.logger.info(f"汇总报告已保存: {filepath}")

        except Exception as e:
            self.logger.error(f"保存汇总报告失败: {e}")
            print(f"[错误] 保存汇总报告失败: {e}")

    def save_failed_devices(self, results: Dict[str, Any], filename: str = None):
        """
        保存失败设备信息到单独的文件

        Args:
            results: 结果统计字典
            filename: 自定义文件名（可选）
        """
        try:
            # 获取失败设备列表
            failed_devices = [
                d for d in results.get("details", []) if not d.get("status")
            ]

            # 如果没有失败设备，不创建文件
            if not failed_devices:
                self.logger.info("没有失败设备，跳过创建失败设备信息文件")
                return

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"失败设备信息_{timestamp}.txt"

            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=" * 70 + "\n")
                f.write("失败设备信息\n")
                f.write("Failed Devices Information\n")
                f.write("=" * 70 + "\n\n")

                f.write(
                    f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(f"失败设备数量: {len(failed_devices)} 台\n\n")

                f.write("=" * 70 + "\n")
                f.write("设备详细信息\n")
                f.write("=" * 70 + "\n\n")

                for idx, device in enumerate(failed_devices, 1):
                    device_name = device.get("device", "未知设备")
                    ip = device.get("ip", "未知IP")
                    vendor = device.get("vendor", "未知厂商")
                    error = device.get("error", "连接失败或执行失败")

                    f.write(f"{idx}. 设备信息:\n")
                    f.write(f"   设备名称: {device_name}\n")
                    f.write(f"   IP地址: {ip}\n")
                    f.write(f"   厂商: {vendor}\n")
                    f.write(f"   失败原因: {error}\n")
                    f.write("-" * 70 + "\n")

                f.write("\n")
                f.write("=" * 70 + "\n")
                f.write("文件结束\n")
                f.write("=" * 70 + "\n")

            print(f"[保存] 失败设备信息已保存: {filepath}")
            self.logger.info(f"失败设备信息已保存: {filepath}")

        except Exception as e:
            self.logger.error(f"保存失败设备信息失败: {e}")
            print(f"[错误] 保存失败设备信息失败: {e}")

    def get_output_dir(self) -> str:
        """
        获取输出目录路径

        Returns:
            输出目录路径
        """
        return self.output_dir

    def list_results(self, limit: int = 10) -> list:
        """
        列出最近的结果文件

        Args:
            limit: 返回文件数量限制

        Returns:
            文件列表
        """
        try:
            files = []
            for filename in os.listdir(self.output_dir):
                if filename.endswith(".log"):
                    filepath = os.path.join(self.output_dir, filename)
                    mtime = os.path.getmtime(filepath)
                    files.append((filename, mtime))

            # 按修改时间排序
            files.sort(key=lambda x: x[1], reverse=True)

            return [f[0] for f in files[:limit]]

        except Exception as e:
            self.logger.error(f"列出结果文件失败: {e}")
            return []
