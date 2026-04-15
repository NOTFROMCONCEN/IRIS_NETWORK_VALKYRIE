#!/usr/bin/env python3
"""
环境检查脚本
Environment Check Script

检查运行环境是否满足要求
"""

import sys
import os
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    print("[1] 检查Python版本...")
    version = sys.version_info

    if version.major >= 3 and version.minor >= 7:
        print(f"    ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"    ✗ Python版本过低: {version.major}.{version.minor}.{version.micro}")
        print(f"    需要Python 3.7或更高版本")
        return False


def check_dependencies():
    """检查依赖包"""
    print("\n[2] 检查依赖包...")

    required_packages = {
        "netmiko": "netmiko",
        "openpyxl": "openpyxl",
        "pandas": "pandas",
        "yaml": "PyYAML",
    }

    missing = []
    installed = []

    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            installed.append(package_name)
            print(f"    ✓ {package_name}")
        except ImportError:
            missing.append(package_name)
            print(f"    ✗ {package_name} - 未安装")

    if missing:
        print(f"\n    [提示] 安装缺失的包:")
        print(f"    pip install {' '.join(missing)}")
        return False

    return True


def check_files():
    """检查必要文件"""
    print("\n[3] 检查必要文件...")

    required_files = [
        "main.py",
        "requirements.txt",
        "config/config.yaml",
        "config/password.conf",
        "core/__init__.py",
        "core/utils.py",
        "core/adapters.py",
        "core/engine.py",
        "core/saver.py",
    ]

    missing = []

    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"    ✓ {file_path}")
        else:
            print(f"    ✗ {file_path} - 不存在")
            missing.append(file_path)

    if missing:
        return False

    return True


def check_directories():
    """检查目录结构"""
    print("\n[4] 检查目录结构...")

    required_dirs = [
        "config",
        "core",
        "devices",
        "output",
        "output/results",
        "output/logs",
        "scripts",
    ]

    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"    ✓ {dir_path}/")
        else:
            print(f"    ! {dir_path}/ - 不存在，正在创建...")
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"      ✓ 已创建")
            except Exception as e:
                print(f"      ✗ 创建失败: {e}")
                return False

    return True


def check_device_file():
    """检查设备配置文件"""
    print("\n[5] 检查设备配置...")

    device_file = "devices/devices.xlsx"

    if os.path.exists(device_file):
        print(f"    ✓ {device_file}")

        try:
            import pandas as pd

            df = pd.read_excel(device_file)

            required_cols = ["生产厂商", "设备型号", "device", "IP"]
            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                print(f"    ✗ 缺少必需列: {missing_cols}")
                print(f"    当前列: {list(df.columns)}")
                return False

            device_count = len(df)
            print(f"    ✓ 包含 {device_count} 台设备")

            if device_count > 0:
                # 显示厂商统计
                vendor_counts = df["生产厂商"].value_counts()
                print(f"    厂商分布:")
                for vendor, count in vendor_counts.items():
                    print(f"      • {vendor}: {count}台")

            return True

        except Exception as e:
            print(f"    ✗ 读取失败: {e}")
            return False
    else:
        print(f"    ! {device_file} - 不存在")
        print(f"    [提示] 请创建设备配置文件")
        return False


def check_config():
    """检查配置文件"""
    print("\n[6] 检查配置文件...")

    # 检查主配置
    config_file = "config/config.yaml"
    if os.path.exists(config_file):
        print(f"    ✓ {config_file}")
        try:
            import yaml

            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            print(f"    ✓ 配置格式正确")
        except Exception as e:
            print(f"    ✗ 配置格式错误: {e}")
            return False
    else:
        print(f"    ✗ {config_file} - 不存在")
        return False

    # 检查密码配置
    password_file = "config/password.conf"
    if os.path.exists(password_file):
        print(f"    ✓ {password_file}")
    else:
        print(f"    ✗ {password_file} - 不存在")
        return False

    return True


def main():
    """主函数"""
    print("=" * 60)
    print("网络设备巡检工具 - 环境检查")
    print("Network Device Inspection Tool - Environment Check")
    print("=" * 60)
    print()

    checks = [
        ("Python版本", check_python_version),
        ("依赖包", check_dependencies),
        ("必要文件", check_files),
        ("目录结构", check_directories),
        ("设备配置", check_device_file),
        ("配置文件", check_config),
    ]

    results = []

    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"\n[错误] {check_name} 检查时发生异常: {e}")
            results.append((check_name, False))

    # 总结
    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)

    all_passed = True
    for check_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{check_name:15} : {status}")
        if not result:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ 所有检查通过！环境配置正确。")
        print("\n可以运行程序:")
        print("  python main.py")
        print("\n查看帮助:")
        print("  python main.py --help")
        return 0
    else:
        print("\n✗ 存在配置问题，请根据上述提示进行修复。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
