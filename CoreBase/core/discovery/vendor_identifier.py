#!/usr/bin/env python3
"""
设备厂商识别模块
Vendor Identification Module

通过 SSH Banner、命令输出特征和提示符识别设备厂商。
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class VendorIdentifier:
    """通过 SSH 连接识别设备厂商"""

    # 各厂商识别特征
    VENDOR_PATTERNS: Dict[str, Dict[str, Any]] = {
        "huawei": {
            "banner_keywords": ["huawei", "vrp"],
            "prompt_patterns": [r"<[^>]+>"],           # <HUAWEI> 或 <Switch>
            "version_commands": ["display version"],
            "output_keywords": ["huawei", "vrp", "huawei versatile routing platform"],
        },
        "h3c": {
            "banner_keywords": ["h3c", "comware"],
            "prompt_patterns": [r"<[^>]+>"],           # <H3C>
            "version_commands": ["display version"],
            "output_keywords": ["h3c", "comware", "hpe", "flexnetwork"],
        },
        "cisco": {
            "banner_keywords": ["cisco"],
            "prompt_patterns": [r"[A-Za-z][\w\-]*#"],  # Router# 或 Switch#
            "version_commands": ["show version"],
            "output_keywords": ["cisco", "ios", "nx-os", "catos"],
        },
        "ruijie": {
            "banner_keywords": ["ruijie", "rgos"],
            "prompt_patterns": [r"[A-Za-z][\w\-]*#"],
            "version_commands": ["show version"],
            "output_keywords": ["ruijie", "rgos"],
        },
        "maipu": {
            "banner_keywords": ["maipu"],
            "prompt_patterns": [r"[A-Za-z][\w\-]*#"],
            "version_commands": ["show version"],
            "output_keywords": ["maipu", "mp"],
        },
        "wst": {
            "banner_keywords": ["wst"],
            "prompt_patterns": [r"[A-Za-z][\w\-]*>", r"[A-Za-z][\w\-]*#"],
            "version_commands": ["show version"],
            "output_keywords": ["wst"],
        },
    }

    # 厂商别名映射：常见的别名 → 标准厂商名
    VENDOR_ALIASES: Dict[str, str] = {
        "huawei": "huawei",
        "h3c": "h3c",
        "hewlett packard": "h3c",
        "hpe": "h3c",
        "hp": "h3c",
        "cisco": "cisco",
        "cisco systems": "cisco",
        "ruijie": "ruijie",
        "rg-s": "ruijie",
        "maipu": "maipu",
        "wst": "wst",
    }

    @classmethod
    def identify_from_banner(cls, banner: str) -> Optional[str]:
        """
        从 SSH Banner 识别厂商。

        Args:
            banner: SSH 连接时获取的 Banner 字符串

        Returns:
            厂商名或 None
        """
        if not banner:
            return None

        banner_lower = banner.lower()

        for vendor, patterns in cls.VENDOR_PATTERNS.items():
            for keyword in patterns["banner_keywords"]:
                if keyword in banner_lower:
                    logger.debug("通过 Banner 识别厂商: %s (关键词: %s)", vendor, keyword)
                    return vendor

        return None

    @classmethod
    def identify_from_prompt(cls, prompt: str) -> Optional[str]:
        """
        从设备提示符识别厂商。

        Args:
            prompt: 设备命令行提示符

        Returns:
            厂商名或 None
        """
        if not prompt:
            return None

        # 华为/H3C 风格提示符: <Hostname>
        if re.match(r"^<[^>]+>$", prompt.strip()):
            # 需要进一步区分华为和H3C，通过提示符无法区分
            # 返回 "huawei_h3c" 让调用者通过其他方式区分
            logger.debug("通过提示符识别为华为/H3C风格: %s", prompt)
            return "huawei_h3c"

        # Cisco/Ruijie/Maipu 风格提示符: Hostname#
        if re.match(r"^[A-Za-z][\w\-]*#$", prompt.strip()):
            logger.debug("通过提示符识别为Cisco风格: %s", prompt)
            return "cisco_family"

        return None

    @classmethod
    def identify_from_output(cls, output: str) -> Optional[str]:
        """
        从命令输出（如 display version / show version）识别厂商。

        Args:
            output: 版本命令的输出文本

        Returns:
            厂商名或 None
        """
        if not output:
            return None

        output_lower = output.lower()

        # 按优先级匹配各厂商特征
        for vendor, patterns in cls.VENDOR_PATTERNS.items():
            for keyword in patterns["output_keywords"]:
                if keyword in output_lower:
                    logger.debug("通过命令输出识别厂商: %s (关键词: %s)", vendor, keyword)
                    return vendor

        return None

    @classmethod
    def identify_from_lldp_info(cls, system_name: str = "", system_desc: str = "") -> Optional[str]:
        """
        从 LLDP 邻居信息中的系统名和系统描述识别厂商。

        Args:
            system_name: LLDP System Name
            system_desc: LLDP System Description

        Returns:
            厂商名或 None
        """
        combined = f"{system_name} {system_desc}".lower()

        for alias, vendor in cls.VENDOR_ALIASES.items():
            if alias in combined:
                logger.debug("通过LLDP信息识别厂商: %s (别名: %s)", vendor, alias)
                return vendor

        return None

    @classmethod
    def extract_model_from_version(cls, vendor: str, output: str) -> str:
        """
        从版本命令输出中提取设备型号。

        Args:
            vendor: 已识别的厂商
            output: 版本命令输出

        Returns:
            设备型号字符串
        """
        if not output:
            return ""

        # 各厂商型号提取正则
        model_patterns = {
            "huawei": [
                r"(?:Huawei|HUAWEI)\s+([\w\-]+(?:\s*[\w\-]+)?)",
                r"hardware\s*[:]\s*([\w\-]+)",
                r"(S\d{4}[\w\-]*)",            # S5735-L48T4X
                r"(CE\d{4}[\w\-]*)",            # CE6850
                r"(AR\d{3,4}[\w\-]*)",           # AR6280
                r"(NE\d{4}[\w\-]*)",             # NE40E
            ],
            "h3c": [
                r"(?:H3C|HPE)\s+([\w\-]+(?:\s*[\w\-]+)?)",
                r"(S\d{4}[\w\-]*)",              # S6520
                r"(MSR\d{3,4}[\w\-]*)",           # MSR3620
                r"(SR\d{4}[\w\-]*)",              # SR8800
                r"(SecPath\s*[\w\-]+)",           # SecPath防火墙
            ],
            "cisco": [
                r"(?:cisco|Cisco)\s+([\w\-]+(?:\s*[\w\-]+)?)",
                r"(Catalyst\s*\d{4}[\w\-]*)",     # Catalyst 3750
                r"(WS-C\d{4}[\w\-]*)",            # WS-C3750
                r"(ISR\d{3,4}[\w\-]*)",            # ISR4321
                r"(ASR\d{3,4}[\w\-]*)",            # ASR9000
                r"(N\dK[\w\-]*)",                  # N9K-C9300
            ],
            "ruijie": [
                r"(?:Ruijie|RGOS)\s+([\w\-]+(?:\s*[\w\-]+)?)",
                r"(RG-[\w\-]+)",                  # RG-S5750
                r"(S\d{4}[\w\-]*)",
            ],
            "maipu": [
                r"(?:Maipu|MP)\s+([\w\-]+(?:\s*[\w\-]+)?)",
                r"(MP\d{3,4}[\w\-]*)",
            ],
            "wst": [
                r"(?:WST)\s+([\w\-]+(?:\s*[\w\-]+)?)",
            ],
        }

        patterns = model_patterns.get(vendor, [])
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                model = match.group(1).strip()
                if model:
                    return model

        return ""

    @classmethod
    def extract_hostname_from_prompt(cls, prompt: str) -> str:
        """
        从设备提示符中提取主机名。

        Args:
            prompt: 设备命令行提示符

        Returns:
            主机名
        """
        if not prompt:
            return ""

        prompt = prompt.strip()

        # 华为/H3C: <Hostname>
        match = re.match(r"^<([^>]+)>$", prompt)
        if match:
            return match.group(1)

        # Cisco/Ruijie/Maipu: Hostname# 或 Hostname>
        match = re.match(r"^([A-Za-z][\w\-]*)[#>]$", prompt)
        if match:
            return match.group(1)

        # 通用：取第一个非空白段
        return prompt.split()[0] if prompt else ""
