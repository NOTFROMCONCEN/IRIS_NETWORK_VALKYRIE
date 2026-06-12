#!/usr/bin/env python3
"""
密码加密工具
Password Encryption Tool

用于将明文密码文件转换为加密格式
用法: python scripts/encrypt_password.py [--input password.conf] [--output password_encrypted.conf]
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.crypto import get_crypto, encrypt_password, is_encrypted


def encrypt_password_file(input_file: str, output_file: str) -> bool:
    """
    加密密码文件

    Args:
        input_file: 输入文件路径（明文）
        output_file: 输出文件路径（加密）

    Returns:
        是否成功
    """
    crypto = get_crypto()

    if not crypto.available:
        print("[错误] 加密功能不可用，请确保已安装 cryptography 库:")
        print("       pip install cryptography")
        return False

    input_path = Path(input_file)
    if not input_path.exists():
        print(f"[错误] 输入文件不存在: {input_path}")
        return False

    print(f"[信息] 读取密码文件: {input_path}")

    encrypted_lines = []
    encrypted_count = 0
    skipped_count = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()

            # 保留注释和空行
            if not stripped or stripped.startswith("#"):
                encrypted_lines.append(line)
                continue

            # 解析格式: 厂商=用户名,密码
            if "=" in stripped:
                parts = stripped.split("=", 1)
                if len(parts) != 2:
                    print(f"[警告] 第 {line_num} 行格式错误，保持原样: {stripped}")
                    encrypted_lines.append(line)
                    skipped_count += 1
                    continue

                vendor, credentials = parts
                vendor = vendor.strip()

                if "," in credentials:
                    cred_parts = credentials.split(",", 1)
                    if len(cred_parts) != 2:
                        print(f"[警告] 第 {line_num} 行凭证格式错误，保持原样: {stripped}")
                        encrypted_lines.append(line)
                        skipped_count += 1
                        continue

                    username, password = cred_parts
                    username = username.strip()
                    password = password.strip()

                    # 检查是否已经加密
                    if is_encrypted(password):
                        print(f"[提示] 第 {line_num} 行 {vendor} 密码已加密，跳过")
                        encrypted_lines.append(line)
                        continue

                    # 加密密码
                    encrypted = encrypt_password(password)
                    if encrypted is None:
                        print(f"[错误] 第 {line_num} 行 {vendor} 密码加密失败，保持原样")
                        encrypted_lines.append(line)
                        skipped_count += 1
                        continue

                    new_line = f"{vendor}={username},{encrypted}\n"
                    encrypted_lines.append(new_line)
                    encrypted_count += 1
                    print(f"[成功] 已加密 {vendor} 的密码")
                else:
                    print(f"[警告] 第 {line_num} 行凭证格式错误(缺少逗号)，保持原样")
                    encrypted_lines.append(line)
                    skipped_count += 1
            else:
                print(f"[警告] 第 {line_num} 行格式错误，保持原样: {stripped}")
                encrypted_lines.append(line)
                skipped_count += 1

    # 写入输出文件
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(encrypted_lines)

    print(f"\n{'='*60}")
    print(f"[完成] 加密结果统计:")
    print(f"  - 成功加密: {encrypted_count} 个密码")
    print(f"  - 跳过/失败: {skipped_count} 行")
    print(f"  - 输出文件: {output_path}")
    print(f"{'='*60}")

    if encrypted_count > 0:
        print(f"\n[提示] 请验证加密文件内容后，替换原文件:")
        print(f"       copy /Y \"{output_path}\" \"{input_path}\"")

    return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="密码加密工具 - 将明文密码转换为加密格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 加密默认密码文件
  python scripts/encrypt_password.py

  # 指定输入和输出文件
  python scripts/encrypt_password.py --input password.conf --output password_encrypted.conf

  # 原地加密（覆盖原文件）
  python scripts/encrypt_password.py --input password.conf --output password.conf

安全建议:
  1. 加密前请备份原文件
  2. 加密后验证输出文件内容正确
  3. 确认无误后再替换原文件
  4. 密钥文件 config/.secret.key 请妥善保管
        """
    )

    parser.add_argument(
        "--input",
        type=str,
        default="config/password.conf",
        help="输入密码文件路径（默认: config/password.conf）"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="config/password_encrypted.conf",
        help="输出加密文件路径（默认: config/password_encrypted.conf）"
    )

    args = parser.parse_args()

    print("="*60)
    print("密码加密工具 v1.0")
    print("="*60)

    success = encrypt_password_file(args.input, args.output)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
