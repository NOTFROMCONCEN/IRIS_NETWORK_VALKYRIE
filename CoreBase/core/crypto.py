#!/usr/bin/env python3
"""
加密模块
Crypto Module

提供密码加密和解密功能，使用 Fernet 对称加密
"""

import os
import base64
import logging
from pathlib import Path
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


# 密钥文件路径
KEY_FILE_PATH = "config/.secret.key"


class PasswordCrypto:
    """密码加密器"""

    def __init__(self, key_file: str = KEY_FILE_PATH):
        """
        初始化加密器

        Args:
            key_file: 密钥文件路径
        """
        self.logger = logging.getLogger(__name__)
        self.key_file = Path(key_file)
        self._fernet = None
        self._load_or_generate_key()

    def _load_or_generate_key(self):
        """加载或生成加密密钥"""
        if not CRYPTO_AVAILABLE:
            self.logger.warning(
                "cryptography 库未安装，密码加密功能不可用。"
                "安装命令: pip install cryptography"
            )
            return

        try:
            if self.key_file.exists():
                # 从文件加载密钥
                with open(self.key_file, "r", encoding="utf-8") as f:
                    key = f.read().strip()
                self._fernet = Fernet(key.encode())
                self.logger.info(f"已从 {self.key_file} 加载加密密钥")
            else:
                # 生成新密钥并保存
                key = Fernet.generate_key()
                self.key_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.key_file, "w", encoding="utf-8") as f:
                    f.write(key.decode())
                # 设置文件权限（仅所有者可读写）
                try:
                    os.chmod(self.key_file, 0o600)
                except (OSError, AttributeError):
                    # Windows 可能不支持 chmod
                    pass
                self._fernet = Fernet(key)
                self.logger.info(f"已生成新加密密钥并保存到 {self.key_file}")
        except Exception as e:
            self.logger.error(f"加载/生成密钥失败: {e}")
            self._fernet = None

    @property
    def available(self) -> bool:
        """检查加密功能是否可用"""
        return CRYPTO_AVAILABLE and self._fernet is not None

    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        加密明文密码

        Args:
            plaintext: 明文密码

        Returns:
            加密后的字符串（带 ENC: 前缀），失败返回 None
        """
        if not self.available:
            return None

        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            # 添加前缀标识这是加密密码
            return f"ENC:{encrypted.decode()}"
        except Exception as e:
            self.logger.error(f"加密失败: {e}")
            return None

    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        解密加密密码

        Args:
            ciphertext: 加密密码字符串（带 ENC: 前缀）

        Returns:
            明文密码，失败返回 None
        """
        if not self.available:
            return None

        try:
            # 检查是否为加密密码
            if not ciphertext.startswith("ENC:"):
                return None

            # 移除前缀
            encrypted = ciphertext[4:].encode()
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode()
        except InvalidToken:
            self.logger.error("解密失败：密钥无效或数据已损坏")
            return None
        except Exception as e:
            self.logger.error(f"解密失败: {e}")
            return None

    def is_encrypted(self, text: str) -> bool:
        """检查字符串是否为加密格式"""
        return text.startswith("ENC:")


# 全局加密器实例
_crypto_instance: Optional[PasswordCrypto] = None


def get_crypto() -> PasswordCrypto:
    """获取全局加密器实例"""
    global _crypto_instance
    if _crypto_instance is None:
        _crypto_instance = PasswordCrypto()
    return _crypto_instance


def encrypt_password(plaintext: str) -> Optional[str]:
    """便捷函数：加密密码"""
    return get_crypto().encrypt(plaintext)


def decrypt_password(ciphertext: str) -> Optional[str]:
    """便捷函数：解密密码"""
    return get_crypto().decrypt(ciphertext)


def is_encrypted(text: str) -> bool:
    """便捷函数：检查是否为加密格式"""
    return get_crypto().is_encrypted(text)
