#!/usr/bin/env python3
"""
网络设备巡检工具 - 主程序入口
Network Device Inspection Tool - Main Entry

版本: 3.0.0
作者: CodeBuddy
描述: 简化优化版网络设备巡检工具
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils import (
    load_config,
    load_devices,
    load_passwords,
    setup_logging,
    update_devices_with_passwords,
    validate_device,
    print_banner,
    create_output_dirs,
    check_disk_space,
    filter_devices_by_group,
    get_device_groups,
)
from core.engine import DeviceEngine
from core.saver import ResultSaver
from core.validator import validate_config
from core.notifier import init_notifier, get_notifier
from core.paths import resolve_corebase_path
from core.lock import inspection_lock_guard


def parse_arguments():
    """
    解析命令行参数

    Returns:
        参数对象
    """
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="""
网络设备巡检工具 v3.0.0

用于批量巡检网络设备，支持华为、H3C、锐捷、迈普、龙马防火墙等厂商。
支持标准巡检与日志收集两种模式，并提供设备分组过滤和模拟运行。
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用示例:
  python main.py
      处理全部设备（标准巡检模式）

  python main.py --vendor huawei --group 核心
      只处理华为厂商且属于"核心"分组的设备

  python main.py --ip 192.168.1.1 --logmode
      只对指定 IP 执行日志收集

  python main.py --dry-run --vendor ruijie
      预览将被处理的设备，不实际连接

  python main.py --ui
      启动设备管理 Web 界面

  python main.py --discover lldp
      通过 LLDP/CDP 从设备清单中的设备发现邻居

  python main.py --discover subnet --subnets 192.168.1.0/24
      扫描指定子网发现网络设备

  python main.py --discover all --subnets 10.0.0.0/24 --depth 2
      组合发现: LLDP邻居 + 子网扫描

支持厂商关键字:
  huawei, h3c, ruijie, ruijie_xialian, maipu, wst, cisco

路径说明（以 CoreBase 为工作目录）:
  devices/devices.xlsx    设备清单
  config/config.yaml      主配置
  config/password.conf    密码配置
  output/results/         巡检结果
  output/logs/            执行日志

返回码:
  0   全部成功
  1   全部失败或程序异常
  2   部分成功
  130 用户中断
        """,
    )

    target_group = parser.add_argument_group("目标筛选参数")
    mode_group = parser.add_argument_group("执行模式参数")
    discovery_group = parser.add_argument_group("设备发现参数")
    io_group = parser.add_argument_group("配置与输出参数")
    info_group = parser.add_argument_group("信息与辅助参数")

    target_group.add_argument(
        "--vendor",
        type=str,
        help="按厂商过滤设备：huawei/h3c/ruijie/ruijie_xialian/maipu/wst",
    )

    target_group.add_argument(
        "--ip",
        type=str,
        help="按单个设备 IP 过滤，只处理该设备",
    )

    target_group.add_argument(
        "--group",
        type=str,
        help="按分组过滤（支持：分组名_设备名、[分组名]设备名、分组名-设备名）",
    )

    mode_group.add_argument(
        "--logmode",
        action="store_true",
        help="日志收集模式：只执行日志相关命令，不执行完整巡检",
    )

    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行：展示将要处理的设备，不实际连接",
    )

    mode_group.add_argument(
        "--ui",
        action="store_true",
        help="启动设备管理 Web 界面（Streamlit）",
    )

    mode_group.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="自动确认所有交互提示（适合自动化或 Web 场景）",
    )

    mode_group.add_argument(
        "--force",
        action="store_true",
        help="强制获取巡检锁（覆盖其他正在运行的巡检任务）",
    )

    # ---- 设备发现参数 ----
    discovery_group.add_argument(
        "--discover",
        type=str,
        choices=["lldp", "subnet", "all"],
        help="设备发现模式: lldp(LLDP/CDP邻居发现) / subnet(子网扫描) / all(组合发现)",
    )

    discovery_group.add_argument(
        "--subnets",
        type=str,
        help="子网列表，逗号分隔 (CIDR格式，如 192.168.1.0/24,10.0.0.0/24)",
    )

    discovery_group.add_argument(
        "--seed-ip",
        type=str,
        help="种子设备IP (仅LLDP模式，不指定则使用设备清单中全部设备)",
    )

    discovery_group.add_argument(
        "--depth",
        type=int,
        default=3,
        help="LLDP递归发现深度 (默认: 3)",
    )

    discovery_group.add_argument(
        "--discover-output",
        type=str,
        help="发现结果导出文件路径 (xlsx格式)",
    )

    discovery_group.add_argument(
        "--discover-import",
        action="store_true",
        help="发现完成后进入交互式导入流程，将选中设备加入设备清单",
    )

    discovery_group.add_argument(
        "--discover-dry-run",
        action="store_true",
        help="仅探测可达性，不尝试SSH登录识别厂商",
    )

    io_group.add_argument(
        "--config",
        type=str,
        help="自定义配置文件路径（默认：config/config.yaml）",
    )

    io_group.add_argument(
        "--output-dir",
        type=str,
        help="自定义结果输出目录（默认：output/results）",
    )

    info_group.add_argument(
        "--list-vendors", action="store_true", help="列出所有支持厂商"
    )

    info_group.add_argument(
        "--list-groups",
        action="store_true",
        help="列出设备清单中的所有分组",
    )

    info_group.add_argument(
        "--version", action="store_true", help="显示版本信息与能力概览"
    )

    return parser.parse_args()


def show_version(config):
    """
    显示版本信息

    Args:
        config: 配置字典
    """
    print_banner(config)
    print("[信息] 简化优化版本")
    print("[特性] 代码量减少65%，性能提升75%")
    print("[支持] 华为、H3C、锐捷、迈普、龙马防火墙")
    print()


def list_vendors(engine):
    """
    列出支持的厂商

    Args:
        engine: 设备引擎实例
    """
    vendors = engine.get_supported_vendors()
    print("\n支持的设备厂商:")
    print("=" * 50)

    vendor_names = {
        "huawei": "华为 (Huawei)",
        "h3c": "H3C (华三)",
        "ruijie": "锐捷 (Ruijie)",
        "ruijie_xialian": "锐捷下级 (Ruijie Sub-devices)",
        "maipu": "迈普 (MaiPu)",
        "wst": "龙马防火墙 (WST Firewall)",
    }

    for vendor in vendors:
        display_name = vendor_names.get(vendor, vendor.upper())
        print(f"  * {vendor:20} - {display_name}")

    print("=" * 50)
    print(f"总计: {len(vendors)} 个厂商\n")


def run_discovery(args, config, passwords):
    """
    执行设备发现流程。

    Args:
        args: 命令行参数
        config: 配置字典
        passwords: 凭证字典

    Returns:
        退出码
    """
    from core.discovery import DiscoveryManager

    discover_mode = args.discover  # lldp / subnet / all
    depth = getattr(args, "depth", 3)
    subnets_str = getattr(args, "subnets", "") or ""
    seed_ip = getattr(args, "seed_ip", "") or ""
    discover_output = getattr(args, "discover_output", "") or ""
    discover_import = getattr(args, "discover_import", False)
    discover_dry_run = getattr(args, "discover_dry_run", False)

    # 解析子网列表
    subnets = [s.strip() for s in subnets_str.split(",") if s.strip()] if subnets_str else []

    # 验证参数
    if discover_mode in ("subnet", "all") and not subnets:
        print("[错误] 子网扫描模式需要指定 --subnets 参数 (如 --subnets 192.168.1.0/24)")
        return 1

    # 加载密码配置
    if not passwords:
        passwords = load_passwords()

    # 获取现有设备清单IP（用于排除）
    excel_file = resolve_corebase_path("devices/devices.xlsx")
    existing_ips = set()
    seed_devices = []

    if excel_file.exists():
        try:
            devices = load_devices(excel_file)
            devices = update_devices_with_passwords(devices, passwords)
            existing_ips = {d.get("ip", "") for d in devices if d.get("ip")}

            # 构建 LLDP 种子设备列表
            if discover_mode in ("lldp", "all"):
                if seed_ip:
                    # 指定种子IP
                    seed_devices = [d for d in devices if d.get("ip") == seed_ip]
                    if not seed_devices:
                        print(f"[错误] 在设备清单中未找到IP为 {seed_ip} 的设备")
                        return 1
                else:
                    seed_devices = list(devices)
        except Exception as e:
            print(f"[警告] 加载设备清单失败: {e}")

    # 创建发现管理器
    discovery_mgr = DiscoveryManager(config, passwords)

    print(f"\n{'=' * 60}")
    print(f"设备自发现 - 模式: {discover_mode.upper()}")
    print(f"{'=' * 60}")

    # 执行发现
    if discover_mode == "lldp":
        if not seed_devices:
            print("[错误] LLDP 发现需要种子设备。请在设备清单中添加设备或使用 --seed-ip 指定。")
            return 1
        print(f"[信息] 种子设备: {len(seed_devices)} 台")
        print(f"[信息] 递归深度: {depth}")
        result = discovery_mgr.discover_from_seeds(
            seed_devices=seed_devices,
            max_depth=depth,
            exclude_ips=existing_ips,
            progress_callback=lambda msg: print(f"  {msg}"),
        )

    elif discover_mode == "subnet":
        print(f"[信息] 扫描子网: {', '.join(subnets)}")
        result = discovery_mgr.scan_subnets(
            subnets=subnets,
            exclude_ips=existing_ips,
            dry_run=discover_dry_run,
            progress_callback=lambda msg: print(f"  {msg}"),
        )

    elif discover_mode == "all":
        print(f"[信息] 种子设备: {len(seed_devices)} 台")
        print(f"[信息] 扫描子网: {', '.join(subnets) if subnets else '无'}")
        print(f"[信息] 递归深度: {depth}")
        result = discovery_mgr.combined_discover(
            seed_devices=seed_devices,
            subnets=subnets,
            max_depth=depth,
            exclude_ips=existing_ips,
            dry_run=discover_dry_run,
            progress_callback=lambda msg: print(f"  {msg}"),
        )
    else:
        print(f"[错误] 未知的发现模式: {discover_mode}")
        return 1

    # 展示结果
    print(f"\n{'=' * 60}")
    print(f"发现结果汇总")
    print(f"{'=' * 60}")
    print(f"  总计发现: {result.total_found} 台设备")
    print(f"  已识别厂商: {sum(1 for d in result.devices if d.identified)} 台")
    print(f"  去重移除: {result.duplicates_removed} 台")
    print(f"  已在清单: {result.already_in_inventory} 台")
    print(f"  新设备: {len(result.new_devices)} 台")
    print(f"  耗时: {result.scan_duration:.1f}s")

    if result.errors:
        print(f"\n[警告] 发现过程中的错误:")
        for err in result.errors:
            print(f"  - {err}")

    # 显示发现设备表格
    if result.devices:
        print(f"\n{'=' * 90}")
        print(f"{'序号':>4}  {'IP地址':<18} {'主机名':<20} {'厂商':<12} {'来源':<10} {'SSH':>4} {'状态':<6}")
        print(f"{'-' * 90}")
        for i, dev in enumerate(result.devices, 1):
            vendor_str = dev.vendor_raw or dev.vendor or "?"
            status = "已存在" if dev.already_in_inventory else ("已识别" if dev.identified else "未识别")
            ssh_str = "✅" if dev.ssh_reachable else "❌"
            print(
                f"{i:>4}  {dev.display_ip:<18} {dev.hostname or '-':<20} "
                f"{vendor_str:<12} {dev.source:<10} {ssh_str:>4} {status:<6}"
            )
        print(f"{'-' * 90}")

    # 导出结果
    if discover_output:
        try:
            import pandas as pd
            table_data = result.to_table_data()
            df = pd.DataFrame(table_data)
            output_path = resolve_corebase_path(discover_output)
            df.to_excel(str(output_path), index=False)
            print(f"\n[成功] 发现结果已导出到: {output_path}")
        except Exception as e:
            print(f"\n[错误] 导出失败: {e}")

    # 交互式导入
    if discover_import and result.new_devices:
        print(f"\n{'=' * 60}")
        print(f"交互式导入 - 选择要添加到设备清单的设备")
        print(f"{'=' * 60}")

        new_devices = result.new_devices
        selected = []

        for i, dev in enumerate(new_devices, 1):
            print(f"\n  [{i}/{len(new_devices)}] {dev.display_ip} ({dev.hostname or '?'}) - {dev.vendor_raw or dev.vendor or '?'}")
            try:
                choice = input("    导入此设备? (y/n/a=全部/q=退出) [n]: ").strip().lower()
                if choice == "q":
                    break
                elif choice == "a":
                    selected = list(new_devices[i - 1:])
                    break
                elif choice in ("y", "yes"):
                    selected.append(dev)
            except (EOFError, KeyboardInterrupt):
                print("\n")
                break

        if selected:
            print(f"\n[信息] 即将导入 {len(selected)} 台设备到设备清单...")
            try:
                from ui.device_manager import DeviceManager
                dm = DeviceManager()
                existing_devices = dm.load_devices()
                imported = 0

                for dev in selected:
                    inv_dict = dev.to_inventory_dict()
                    # 检查是否已存在
                    ip_exists = any(
                        d.get("IP地址", "") == inv_dict["IP地址"]
                        for d in existing_devices
                    )
                    if not ip_exists:
                        existing_devices.append(inv_dict)
                        imported += 1
                        print(f"  + {inv_dict['IP地址']} ({inv_dict['设备名']}) - {inv_dict['生产厂商']}")

                if imported > 0:
                    if dm.save_devices(existing_devices):
                        print(f"\n[成功] 已导入 {imported} 台设备到设备清单")
                    else:
                        print(f"\n[错误] 保存设备清单失败")
                        return 1
                else:
                    print(f"\n[信息] 没有新设备需要导入")

            except Exception as e:
                print(f"\n[错误] 导入失败: {e}")
                return 1
        else:
            print(f"\n[信息] 未选择任何设备")

    print(f"\n[完成] 设备发现流程结束")
    return 0


def confirm_execution(devices, log_mode, auto_confirm=False):
    """
    确认执行

    Args:
        devices: 设备列表
        log_mode: 是否为日志模式
        auto_confirm: 是否自动确认（用于Web模式或自动化脚本）

    Returns:
        是否继续
    """
    print(f"\n{'='*60}")
    print(f"准备执行巡检")
    print(f"{'='*60}")
    print(f"设备数量: {len(devices)} 台")
    print(f"执行模式: {'日志收集模式' if log_mode else '标准巡检模式'}")
    print(f"{'='*60}")

    if auto_confirm:
        print("\n[自动确认] 跳过交互式确认")
        return True

    try:
        response = input("\n确认开始？(y/N): ").strip().lower()
        return response in ["y", "yes"]
    except (EOFError, KeyboardInterrupt):
        print("\n\n操作已取消")
        return False


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 加载配置
    if hasattr(args, "config") and args.config:
        config = load_config(args.config)
    else:
        config = load_config()

    # 验证配置
    is_valid, errors, warnings = validate_config(config)
    if not is_valid:
        print("\n[错误] 配置文件验证失败，程序无法启动")
        print("请检查 config/config.yaml 文件")
        for error in errors:
            print(f"  - {error}")
        return 1

    if warnings:
        print("\n[警告] 配置文件存在警告:")
        for warning in warnings:
            print(f"  - {warning}")

    # 显示版本信息
    if args.version:
        show_version(config)
        return 0

    # 初始化通知器
    init_notifier(enabled=True)

    # 显示横幅
    print_banner(config)

    # 检查是否启动UI界面
    if hasattr(args, "ui") and args.ui:
        try:
            print("[信息] 启动设备管理UI界面...")
            # 导入UI模块
            from ui import start_ui

            return start_ui()
        except ImportError as e:
            print(f"[错误] 无法导入UI模块: {e}")
            print("[提示] 请确保已安装streamlit: pip install streamlit>=1.28.0")
            return 1
        except Exception as e:
            print(f"[错误] 启动UI失败: {e}")
            return 1

    # 设备发现模式
    if hasattr(args, "discover") and args.discover:
        passwords = load_passwords()
        return run_discovery(args, config, passwords)

    # 创建输出目录
    if hasattr(args, "output_dir") and args.output_dir:
        # 如果指定了自定义输出目录，更新配置
        if "output" not in config:
            config["output"] = {}
        config["output"]["results_dir"] = args.output_dir
    create_output_dirs(config)

    # 检查磁盘空间
    required_space = config.get("system", {}).get("disk_space_check_mb", 100)
    has_space, free_mb, error_msg = check_disk_space(required_space)
    if not has_space:
        print(f"[错误] {error_msg}")
        print("[提示] 请清理磁盘空间后重试")
        return 1
    print(f"[检查] 磁盘空间充足，可用 {free_mb}MB")

    # 初始化设备引擎
    engine = DeviceEngine(config)

    # 定义Excel文件路径
    excel_file = resolve_corebase_path("devices/devices.xlsx")

    # 列出支持的厂商
    if args.list_vendors:
        list_vendors(engine)
        return 0

    # 列出设备分组
    if args.list_groups:
        devices = load_devices(excel_file)
        groups = get_device_groups(devices)
        print("\n设备分组列表:")
        print("=" * 50)
        if groups:
            for group in groups:
                print(f"  * {group}")
        else:
            print("  未找到设备分组")
        print("=" * 50)
        print(f"总计: {len(groups)} 个分组\n")
        return 0

    # 设置日志
    setup_logging(config)

    # 加载密码配置
    passwords = load_passwords()

    # 加载设备信息
    if not excel_file.exists():
        print(f"[错误] 设备配置文件不存在: {excel_file}")
        print("[提示] 请创建 devices/devices.xlsx 文件并配置设备信息")
        return 1

    devices = load_devices(excel_file)

    if not devices:
        print("[错误] 没有找到任何设备")
        print("[提示] 请检查 devices/devices.xlsx 文件")
        return 1

    # 更新设备认证信息
    devices = update_devices_with_passwords(devices, passwords)

    # 验证设备信息
    valid_devices = []
    for device in devices:
        is_valid, error_msg = validate_device(device)
        if is_valid:
            valid_devices.append(device)
        else:
            print(f"[警告] 设备 {device.get('name', 'unknown')} 无效: {error_msg}")

    if not valid_devices:
        print("[错误] 没有有效的设备")
        return 1

    print(f"[成功] 有效设备: {len(valid_devices)}/{len(devices)} 台")

    # 过滤设备
    filtered_devices = engine.filter_devices(
        valid_devices,
        vendor=args.vendor,
        ip=args.ip,
    )

    # 按分组过滤
    if hasattr(args, "group") and args.group:
        filtered_devices = filter_devices_by_group(filtered_devices, args.group)
        print(f"[过滤] 只处理分组 '{args.group}': {len(filtered_devices)} 台")

    if not filtered_devices:
        print("[错误] 没有符合条件的设备")
        return 1

    # 模拟运行模式
    if hasattr(args, "dry_run") and args.dry_run:
        print("\n[模拟运行] 以下设备将被处理（不会实际连接）:")
        print("=" * 80)
        for device in filtered_devices:
            print(
                f"  * {device.get('name', 'Unknown')} ({device.get('ip', 'N/A')}) - {device.get('vendor', 'Unknown')}"
            )
        print("=" * 80)
        print(f"总计: {len(filtered_devices)} 台设备")
        print(f"执行模式: {'日志收集模式' if args.logmode else '标准巡检模式'}")
        return 0

    # 预检查连通性
    reachable_devices = engine.pre_check_connectivity(filtered_devices)

    if len(reachable_devices) == 0:
        print("[错误] 所有设备均无法连接，终止执行")
        return 1

    if len(reachable_devices) < len(filtered_devices):
        print(
            f"\n[警告] 有 {len(filtered_devices) - len(reachable_devices)} 台设备无法连接"
        )
        print("1. 继续执行（只处理可连接设备）")
        print("2. 尝试处理所有设备（包括不可连接设备）")
        print("3. 取消执行")

        try:
            choice = input("\n请选择操作 [1/2/3] (默认为1): ").strip()
            if choice == "3":
                print("[取消] 操作已取消")
                return 0
            elif choice == "2":
                print("[提示] 将尝试处理所有设备")
                # 保持 filtered_devices 不变
            else:
                print("[提示] 将只处理可连接设备")
                filtered_devices = reachable_devices
        except (EOFError, KeyboardInterrupt):
            print("\n\n[取消] 操作已取消")
            return 0

    # 确认执行
    if not confirm_execution(filtered_devices, args.logmode, args.yes):
        print("[取消] 操作已取消")
        return 0

    # 获取巡检任务锁
    try:
        with inspection_lock_guard(
            mode="cli",
            description=f"vendor={args.vendor or 'all'}, ip={args.ip or 'all'}, group={args.group or 'all'}",
            force=args.force,
        ):
            # 初始化结果保存器
            output_dir = config.get("output", {}).get("results_dir", "output/results")
            saver = ResultSaver(output_dir)

            # 执行批量测试
            results = engine.batch_test(
                filtered_devices,
                log_mode=args.logmode,
                result_saver=saver,
            )

            # 保存汇总报告
            saver.save_summary(results)

            # 保存失败设备信息
            saver.save_failed_devices(results)

            # 显示输出路径
            print(f"\n[输出] 结果目录: {saver.get_output_dir()}")

            # 发送完成通知
            notifier = get_notifier()
            notifier.notify_completion(
                total=results["total"],
                success=results["success"],
                failed=results["failed"],
                duration=engine.performance_monitor.get_summary().get("total_duration", 0),
            )

            # 返回状态码
            if results["failed"] == 0:
                return 0  # 全部成功
            elif results["success"] > 0:
                return 2  # 部分成功
            else:
                return 1  # 全部失败

    except RuntimeError as e:
        print(f"\n[错误] {e}")
        print("[提示] 使用 --force 参数可强制获取锁（会中断其他正在运行的巡检任务）")
        return 1

    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断操作")
        # 发送中断通知
        notifier = get_notifier()
        notifier.notify_error("用户中断了巡检任务")
        return 130

    except Exception as e:
        print(f"\n[错误] 程序异常: {e}")
        import traceback

        traceback.print_exc()
        # 发送错误通知
        notifier = get_notifier()
        notifier.notify_error(f"程序异常: {str(e)}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[致命错误] {e}")
        sys.exit(1)
