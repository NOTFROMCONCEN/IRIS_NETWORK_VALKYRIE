#!/usr/bin/env python3
"""
设备引擎模块
Device Engine Module

负责设备测试、批量处理和结果协调
"""

import logging
import time
import socket
import subprocess
import platform
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from .adapters import AdapterFactory, BaseAdapter
from .performance import PerformanceMonitor


class DeviceEngine:
    """设备操作引擎"""

    @staticmethod
    def _classify_connection_error(message: str) -> str:
        """将连接失败消息归类为固定原因码，便于统计和排障。"""
        if not message:
            return "UNKNOWN"

        text = message.lower()
        if "认证失败" in message or "用户名/密码" in message or "auth" in text:
            return "AUTH_FAILED"
        if "连接超时" in message or "timeout" in text:
            return "TIMEOUT"
        if "设备未连接" in message:
            return "NOT_CONNECTED"
        if "不支持的厂商" in message:
            return "UNSUPPORTED_VENDOR"
        if "连接异常" in message or "refused" in text or "unreachable" in text:
            return "NETWORK_ERROR"
        return "UNKNOWN"

    def __init__(self, config: Dict[str, Any]):
        """
        初始化设备引擎

        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.performance_monitor = PerformanceMonitor()
        self.logger.info("设备引擎已初始化")

    @staticmethod
    def check_ping(ip: str, count: int = 1, timeout: int = 2) -> bool:
        """
        检查 Ping 连通性

        Args:
            ip: 目标IP
            count: Ping次数
            timeout: 超时时间(秒)

        Returns:
            是否连通
        """
        system = platform.system().lower()

        if system == "windows":
            # Windows: -n 次数, -w 超时(毫秒)
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), ip]
        else:
            # Linux/Mac: -c 次数, -W 超时(秒)
            cmd = ["ping", "-c", str(count), "-W", str(timeout), ip]

        try:
            # stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL to suppress output
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout
                + 2,  # Give a bit more time than the ping timeout itself
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def check_port(ip: str, port: int = 22, timeout: int = 2) -> bool:
        """
        检查端口是否开放

        Args:
            ip: 目标IP
            port: 目标端口
            timeout: 超时时间(秒)

        Returns:
            是否开放
        """
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error):
            return False

    def pre_check_connectivity(
        self, devices: List[Dict[str, Any]], max_workers: int = None
    ) -> List[Dict[str, Any]]:
        """
        预检查设备连通性

        Args:
            devices: 设备列表
            max_workers: 最大并发数（默认从配置读取）

        Returns:
            可连接的设备列表
        """
        print(f"\n{'='*60}")
        print(f"[预检] 开始检查 {len(devices)} 台设备的连通性...")
        print(f"{'='*60}")

        reachable_devices = []
        unreachable_devices = []
        # 从配置获取默认并发数，或使用传入值
        if max_workers is None:
            max_workers = self.config.get("system", {}).get("max_workers_precheck", 20)

        # 低功耗模式：降低并发数
        if self.config.get("system", {}).get("low_power_mode", False):
            max_workers = max(1, max_workers // 2)  # 最多减半，最少1
            print("[低功耗] 已启用低功耗模式，降低并发数")

        device_status = {}  # Store status for reporting

        def check_single_device(dev):
            ip = dev["ip"]
            port = dev.get("port", 22)
            ping_ok = self.check_ping(ip)
            port_ok = self.check_port(ip, port)
            return ping_ok, port_ok

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {
                executor.submit(check_single_device, d): d for d in devices
            }

            total = len(devices)
            completed = 0

            for future in as_completed(future_to_device):
                device = future_to_device[future]
                completed += 1

                # 简单的进度显示
                if completed % 10 == 0 or completed == total:
                    print(
                        f"\r进度: {completed}/{total} ({(completed/total)*100:.1f}%)",
                        end="",
                        flush=True,
                    )

                try:
                    is_ping, is_port = future.result()

                    device_status[device["ip"]] = {"ping": is_ping, "port": is_port}

                    # 只要Ping通或者端口通，都算可达
                    if is_ping or is_port:
                        reachable_devices.append(device)
                    else:
                        unreachable_devices.append(device)

                except Exception:
                    unreachable_devices.append(device)
                    device_status[device["ip"]] = {"ping": False, "port": False}

        print("\n")

        if unreachable_devices:
            print(f"[警告] 发现 {len(unreachable_devices)} 台设备无法连接:")
            for d in unreachable_devices:
                status = device_status.get(d["ip"], {"ping": False, "port": False})
                ping_str = "Ping:Fail" if not status["ping"] else "Ping:OK"
                port_str = "SSH:Fail" if not status["port"] else "SSH:OK"
                print(
                    f"  * {d.get('name', 'Unknown')} ({d['ip']}) - [{ping_str} | {port_str}]"
                )
            print(f"\n[提示] 以上设备可能宕机或网络不可达")

        # Optionally show partial failures (e.g. Ping OK but SSH Fail, or vice versa)
        partial_failures = [
            d
            for d in reachable_devices
            if not (device_status[d["ip"]]["ping"] and device_status[d["ip"]]["port"])
        ]
        if partial_failures:
            print(
                f"[注意] {len(partial_failures)} 台设备部分连通 (Ping或SSH其中一项失败):"
            )
            for d in partial_failures:
                status = device_status.get(d["ip"])
                ping_str = "Ping:Fail" if not status["ping"] else "Ping:OK"
                port_str = "SSH:Fail" if not status["port"] else "SSH:OK"
                print(
                    f"  ! {d.get('name', 'Unknown')} ({d['ip']}) - [{ping_str} | {port_str}]"
                )

        print(f"[结果] 可连接: {len(reachable_devices)} / 总数: {len(devices)}")
        return reachable_devices

    def test_device(
        self,
        device_info: Dict[str, Any],
        log_mode: bool = False,
        result_saver=None,
        connection_only: bool = False,
    ) -> bool:
        """
        测试单个设备

        Args:
            device_info: 设备信息字典
            log_mode: 是否为日志模式
            result_saver: 结果保存器实例
            connection_only: 是否只测试连接，不执行命令

        Returns:
            测试是否成功
        """
        vendor = device_info["vendor"]
        ip = device_info["ip"]
        device_name = device_info.get("name", ip)

        # 记录设备开始时间
        self.performance_monitor.record_device_start(device_name)

        # 创建适配器，传递配置
        adapter = AdapterFactory.create(
            vendor=vendor,
            host=ip,
            username=device_info["username"],
            password=device_info["password"],
            port=device_info.get("port", 22),
            config=self.config,
        )

        if not adapter:
            print(f"[错误] 不支持的厂商: {vendor}")
            return False

        # 连接设备
        print(f"\n{'='*60}")
        print(
            f"[设备] {device_name} ({ip}) [厂商: {vendor}] [端口: {device_info.get('port', 22)}]"
        )
        print(f"{'='*60}")

        # 获取重试配置
        max_retries = self.config.get("system", {}).get("retries", 3)
        retry_interval = 2

        # 获取密码错误立即断开配置（适用于dot1x等严苛的准入机制）
        password_error_disconnect = self.config.get("system", {}).get(
            "password_error_disconnect", False
        )

        success = False
        message = ""

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                print(f"[重试] 第 {attempt}/{max_retries} 次尝试连接...")
                time.sleep(retry_interval)

            success, message = adapter.connect()
            print(message)

            if success:
                if attempt > 1:
                    self.logger.info(
                        "设备重试连接成功: device=%s ip=%s attempt=%s",
                        device_name,
                        ip,
                        attempt,
                    )
                break

            # 如果是认证失败，根据配置决定是否停止重试
            error_code = self._classify_connection_error(message)
            self.logger.warning(
                "设备连接失败: device=%s ip=%s attempt=%s/%s reason=%s message=%s",
                device_name,
                ip,
                attempt,
                max_retries,
                error_code,
                message,
            )
            if "认证失败" in message:
                if password_error_disconnect:
                    print(
                        f"[提示] 检测到认证失败，根据配置立即断开（password_error_disconnect=True）"
                    )
                    break
                else:
                    print(
                        f"[提示] 检测到认证失败，将按配置继续重试（password_error_disconnect=False）"
                    )

        if not success:
            final_reason = self._classify_connection_error(message)
            self.logger.error(
                "设备连接最终失败: device=%s ip=%s retries=%s reason=%s",
                device_name,
                ip,
                max_retries,
                final_reason,
            )
            print(f"[失败] 经过 {max_retries} 次尝试后仍无法连接")
            return False

        try:
            if connection_only:
                # 只测试连接，不执行命令
                print(f"[模式] 连接测试模式")
                print(f"[结果] SSH连接成功，未执行任何命令")
                return True
            elif log_mode:
                # 日志收集模式
                return self._test_log_mode(adapter, device_info, result_saver)
            else:
                # 标准模式
                return self._test_standard_mode(adapter, device_info, result_saver)

        except Exception as e:
            self.logger.error(f"测试设备时发生错误: {e}")
            print(f"[错误] {str(e)}")
            self.performance_monitor.record_device_end(device_name)
            return False

        finally:
            # 确保断开连接
            adapter.disconnect()
            # 记录设备结束时间
            self.performance_monitor.record_device_end(device_name)

    def _test_standard_mode(
        self, adapter: BaseAdapter, device_info: Dict[str, Any], result_saver
    ) -> bool:
        """
        标准模式测试

        Args:
            adapter: 设备适配器
            device_info: 设备信息
            result_saver: 结果保存器

        Returns:
            是否成功
        """
        vendor = device_info["vendor"]
        ip = device_info["ip"]
        device_name = device_info.get("name", ip)

        print(f"[模式] 标准巡检模式")
        print(f"[任务] 执行 {len(adapter.commands)} 个检查命令")

        # 执行所有命令
        results = adapter.run_commands()

        if not results:
            print(f"[失败] 未获取到任何结果")
            return False

        # 统计结果
        success_count = sum(1 for r in results.values() if r.get("status"))
        total_count = len(results)

        print(f"\n[结果] 命令执行完成: {success_count}/{total_count}")

        # 保存结果
        if result_saver:
            for cmd_type, result in results.items():
                if result.get("status"):
                    output = result.get("output", "")
                    result_saver.save_result(device_name, ip, cmd_type, output, vendor)
                    print(f"  ✓ {cmd_type}: 已保存")
                else:
                    print(f"  ✗ {cmd_type}: 失败")

        return success_count > 0

    def _test_log_mode(
        self, adapter: BaseAdapter, device_info: Dict[str, Any], result_saver
    ) -> bool:
        """
        日志模式测试

        Args:
            adapter: 设备适配器
            device_info: 设备信息
            result_saver: 结果保存器

        Returns:
            是否成功
        """
        vendor = device_info["vendor"]
        ip = device_info["ip"]
        device_name = device_info.get("name", ip)

        print(f"[模式] 日志收集模式")

        # 获取日志
        success, logs, message = adapter.get_logs()

        if success:
            print(f"[成功] {message}")
            print(f"[数据] 日志长度: {len(logs)} 字符")

            # 保存日志
            if result_saver and logs:
                result_saver.save_result(device_name, ip, "device_logs", logs, vendor)
                print(f"  ✓ 日志已保存")

            return True
        else:
            print(f"[失败] {message}")
            return False

    def batch_test(
        self,
        devices: List[Dict[str, Any]],
        log_mode: bool = False,
        result_saver=None,
        max_workers: int = None,
    ) -> Dict[str, Any]:
        """
        批量测试设备

        Args:
            devices: 设备列表
            log_mode: 是否为日志模式
            result_saver: 结果保存器
            max_workers: 最大并发数（默认从配置读取）

        Returns:
            测试结果统计
        """
        # 开始性能监控
        self.performance_monitor.start()

        if not devices:
            print("[警告] 设备列表为空")
            return {"total": 0, "success": 0, "failed": 0, "details": []}

        results = {"total": len(devices), "success": 0, "failed": 0, "details": []}

        print(f"\n{'='*60}")
        print(f"[任务] 批量测试 {len(devices)} 台设备")
        print(f"[模式] {'日志收集' if log_mode else '标准巡检'}")
        print(f"{'='*60}")

        # 从配置获取默认并发数，或使用传入值
        if max_workers is None:
            max_workers = self.config.get("system", {}).get("max_workers_batch", 5)

        # 低功耗模式：降低并发数
        if self.config.get("system", {}).get("low_power_mode", False):
            max_workers = max(1, max_workers // 2)  # 最多减半，最少1
            print("[低功耗] 已启用低功耗模式，降低并发数")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {
                executor.submit(
                    self.test_device, device, log_mode, result_saver
                ): device
                for device in devices
            }

            for idx, future in enumerate(as_completed(future_to_device), 1):
                device = future_to_device[future]
                device_name = device.get("name", device.get("ip", "unknown"))
                ip = device.get("ip", "unknown")
                vendor = device.get("vendor", "unknown")

                try:
                    success = future.result()

                    if success:
                        results["success"] += 1
                        status_text = "[OK] 成功"
                    else:
                        results["failed"] += 1
                        status_text = "[FAIL] 失败"

                    results["details"].append(
                        {
                            "device": device_name,
                            "ip": ip,
                            "vendor": vendor,
                            "status": success,
                        }
                    )

                    print(f"[{idx}/{len(devices)}] {device_name}: {status_text}")

                except Exception as e:
                    results["failed"] += 1
                    self.logger.error(f"处理设备 {device_name} 时发生错误: {e}")
                    print(f"[{idx}/{len(devices)}] {device_name}: [ERROR] 异常: {str(e)}")

                    results["details"].append(
                        {
                            "device": device_name,
                            "ip": ip,
                            "vendor": vendor,
                            "status": False,
                            "error": str(e),
                        }
                    )

        # 打印总结
        self._print_summary(results)

        # 停止性能监控并打印摘要
        self.performance_monitor.stop()
        self.performance_monitor.print_summary()

        return results

    def _print_summary(self, results: Dict[str, Any]):
        """
        打印批量测试总结

        Args:
            results: 测试结果
        """
        print(f"\n{'='*60}")
        print(f"[总结] 批量测试完成")
        print(f"{'='*60}")
        print(f"总设备数: {results['total']}")
        print(f"成功: {results['success']} 台")
        print(f"失败: {results['failed']} 台")

        if results["total"] > 0:
            success_rate = (results["success"] / results["total"]) * 100
            print(f"成功率: {success_rate:.1f}%")

        # 显示失败设备
        if results["failed"] > 0:
            print(f"\n[失败设备列表]:")
            for detail in results["details"]:
                if not detail["status"]:
                    device = detail["device"]
                    ip = detail["ip"]
                    vendor = detail["vendor"]
                    error = detail.get("error", "未知错误")
                    print(f"  [FAIL] {device} ({ip}) [{vendor}] - {error}")

        print(f"{'='*60}")

    def filter_devices(
        self,
        devices: List[Dict[str, Any]],
        vendor: str = None,
        ip: str = None,
    ) -> List[Dict[str, Any]]:
        """
        过滤设备列表

        Args:
            devices: 原始设备列表
            vendor: 指定厂商
            ip: 指定IP

        Returns:
            过滤后的设备列表
        """
        filtered = devices.copy()

        if vendor:
            # 特殊处理锐捷设备，兼容 ruijie 和 ruijie_xialian
            if vendor.lower() == "ruijie":
                filtered = [d for d in filtered if "ruijie" in d["vendor"].lower()]
            else:
                filtered = [
                    d for d in filtered if d["vendor"].lower() == vendor.lower()
                ]
            print(f"[过滤] 只处理 {vendor} 设备: {len(filtered)} 台")

        if ip:
            filtered = [d for d in filtered if d["ip"] == ip]
            print(f"[过滤] 只处理 IP {ip}: {len(filtered)} 台")

        return filtered

    def get_supported_vendors(self) -> List[str]:
        """
        获取支持的厂商列表

        Returns:
            厂商列表
        """
        return AdapterFactory.get_supported_vendors()
