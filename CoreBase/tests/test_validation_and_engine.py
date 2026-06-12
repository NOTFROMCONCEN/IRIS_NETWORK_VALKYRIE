import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from textwrap import dedent
from unittest.mock import patch, MagicMock

from core.adapters import (
    AdapterFactory,
    CommandSpec,
    HuaweiAdapter,
    RuijieAdapter,
)
from core.device_inventory import validate_cli_device, validate_ui_device
from core.engine import DeviceEngine
from core.validator import validate_config


class _FakeAdapter:
    def __init__(self, message: str):
        self.message = message
        self.attempts = 0

    def connect(self):
        self.attempts += 1
        return False, self.message

    def disconnect(self):
        return None


class InventoryValidationTests(unittest.TestCase):
    def test_validate_ui_device_normalizes_port(self):
        device = {
            "设备名": "Core_SW_01",
            "IP地址": "192.168.1.10",
            "生产厂商": "HUAWEI",
            "端口": "22",
            "备注": " demo ",
        }

        is_valid, error_msg = validate_ui_device(device)

        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "")
        self.assertEqual(device["生产厂商"], "HUAWEI")
        self.assertEqual(device["端口"], "22")
        self.assertEqual(device["备注"], "demo")

    def test_validate_cli_device_rejects_invalid_ip(self):
        device = {
            "name": "Core_SW_01",
            "ip": "999.1.1.1",
            "vendor": "huawei",
            "port": 22,
            "username": "admin",
            "password": "secret",
        }

        is_valid, error_msg = validate_cli_device(device, ["huawei"])

        self.assertFalse(is_valid)
        self.assertIn("IP地址", error_msg)

    def test_validate_cli_device_with_jump_host(self):
        """测试带跳板机的设备验证"""
        device = {
            "name": "Core_SW_01",
            "ip": "192.168.1.10",
            "vendor": "huawei",
            "port": 22,
            "username": "admin",
            "password": "secret",
            "jump_host": "10.0.0.1",
            "jump_port": 22,
            "jump_username": "jumpuser",
            "jump_password": "jumppass",
        }

        is_valid, error_msg = validate_cli_device(device, ["huawei"])

        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "")
        self.assertEqual(device["jump_host"], "10.0.0.1")
        self.assertEqual(device["jump_port"], 22)
        self.assertEqual(device["jump_username"], "jumpuser")
        self.assertEqual(device["jump_password"], "jumppass")

    def test_validate_cli_device_rejects_invalid_jump_host_ip(self):
        """测试无效跳板机IP地址的设备验证"""
        device = {
            "name": "Core_SW_01",
            "ip": "192.168.1.10",
            "vendor": "huawei",
            "port": 22,
            "username": "admin",
            "password": "secret",
            "jump_host": "999.0.0.1",
            "jump_port": 22,
            "jump_username": "jumpuser",
            "jump_password": "jumppass",
        }

        is_valid, error_msg = validate_cli_device(device, ["huawei"])

        self.assertFalse(is_valid)
        self.assertIn("跳板机IP地址", error_msg)

    def test_validate_cli_device_requires_jump_username_when_jump_host_configured(self):
        """测试配置跳板机时必须提供用户名"""
        device = {
            "name": "Core_SW_01",
            "ip": "192.168.1.10",
            "vendor": "huawei",
            "port": 22,
            "username": "admin",
            "password": "secret",
            "jump_host": "10.0.0.1",
            "jump_port": 22,
            "jump_username": "",
            "jump_password": "jumppass",
        }

        is_valid, error_msg = validate_cli_device(device, ["huawei"])

        self.assertFalse(is_valid)
        self.assertIn("跳板机用户名", error_msg)

    def test_validate_cli_device_requires_jump_password_or_key_when_jump_host_configured(self):
        """测试配置跳板机时必须提供密码或SSH密钥"""
        device = {
            "name": "Core_SW_01",
            "ip": "192.168.1.10",
            "vendor": "huawei",
            "port": 22,
            "username": "admin",
            "password": "secret",
            "jump_host": "10.0.0.1",
            "jump_port": 22,
            "jump_username": "jumpuser",
            "jump_password": "",
            "jump_key_path": "",
        }

        is_valid, error_msg = validate_cli_device(device, ["huawei"])

        self.assertFalse(is_valid)
        self.assertIn("密码或SSH密钥路径", error_msg)

    def test_validate_ui_device_with_jump_host(self):
        """测试带跳板机的UI设备验证"""
        device = {
            "设备名": "Core_SW_01",
            "IP地址": "192.168.1.10",
            "生产厂商": "HUAWEI",
            "端口": "22",
            "备注": " demo ",
            "跳板机地址": "10.0.0.1",
            "跳板机端口": "22",
            "跳板机用户名": "jumpuser",
            "跳板机密码": "jumppass",
        }

        is_valid, error_msg = validate_ui_device(device)

        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "")
        self.assertEqual(device["跳板机地址"], "10.0.0.1")
        self.assertEqual(device["跳板机端口"], "22")
        self.assertEqual(device["跳板机用户名"], "jumpuser")
        self.assertEqual(device["跳板机密码"], "jumppass")


class AdapterFactoryTests(unittest.TestCase):
    """适配器工厂测试"""

    def test_create_adapter_with_jump_host(self):
        """测试通过跳板机创建适配器"""
        adapter = AdapterFactory.create(
            vendor="huawei",
            host="192.168.1.10",
            username="admin",
            password="secret",
            port=22,
            jump_host="10.0.0.1",
            jump_port=22,
            jump_username="jumpuser",
            jump_password="jumppass",
        )

        self.assertIsNotNone(adapter)
        self.assertIsInstance(adapter, HuaweiAdapter)
        self.assertEqual(adapter.host, "192.168.1.10")
        self.assertEqual(adapter.jump_host, "10.0.0.1")
        self.assertEqual(adapter.jump_port, 22)
        self.assertEqual(adapter.jump_username, "jumpuser")
        self.assertEqual(adapter.jump_password, "jumppass")

    def test_create_adapter_without_jump_host(self):
        """测试不通过跳板机创建适配器"""
        adapter = AdapterFactory.create(
            vendor="huawei",
            host="192.168.1.10",
            username="admin",
            password="secret",
            port=22,
        )

        self.assertIsNotNone(adapter)
        self.assertIsInstance(adapter, HuaweiAdapter)
        self.assertEqual(adapter.host, "192.168.1.10")
        self.assertIsNone(adapter.jump_host)
        self.assertEqual(adapter.jump_port, 22)
        self.assertEqual(adapter.jump_username, "")
        self.assertEqual(adapter.jump_password, "")


class ConfigValidationTests(unittest.TestCase):
    def test_validate_config_accepts_password_error_disconnect(self):
        config = {
            "version": "3.1.0",
            "description": "新增跳板机支持",
            "release_date": "2026-05-06",
            "system": {
                "log_level": "INFO",
                "retries": 3,
                "timeout": 120,
                "max_workers_precheck": 20,
                "max_workers_batch": 5,
                "disk_space_check_mb": 100,
                "low_power_mode": False,
                "password_error_disconnect": True,
            },
            "network": {
                "ssh_port": 22,
                "connect_timeout": 60,
                "command_timeout": 120,
            },
            "commands": {
                "catalog_file": "config/commands.yaml",
            },
            "output": {
                "results_dir": "output/results",
                "logs_dir": "output/logs",
            },
            "features": {
                "auto_retry": True,
                "log_mode": True,
                "progress_bar": True,
            },
        }

        is_valid, errors, warnings = validate_config(config)
        
        if not is_valid:
            print(f"Validation failed with errors: {errors}")
            print(f"Warnings: {warnings}")
        
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class DeviceEngineRetryTests(unittest.TestCase):
    @patch("core.engine.AdapterFactory.create")
    def test_auth_failure_disconnect_stops_retry_on_first_attempt(self, mock_create):
        adapter = _FakeAdapter("Authentication failed")
        mock_create.return_value = adapter
        engine = DeviceEngine(
            {"system": {"retries": 3, "password_error_disconnect": True}}
        )

        result = engine.test_device(
            {
                "vendor": "huawei",
                "ip": "192.168.1.10",
                "name": "Core_SW_01",
                "username": "admin",
                "password": "secret",
                "port": 22,
            },
            connection_only=True,
        )

        self.assertFalse(result)
        self.assertEqual(adapter.attempts, 1)

    @patch("core.engine.AdapterFactory.create")
    def test_auth_failure_retries_when_disconnect_disabled(self, mock_create):
        adapter = _FakeAdapter("Authentication failed")
        mock_create.return_value = adapter
        engine = DeviceEngine(
            {"system": {"retries": 3, "password_error_disconnect": False}}
        )

        result = engine.test_device(
            {
                "vendor": "huawei",
                "ip": "192.168.1.10",
                "name": "Core_SW_01",
                "username": "admin",
                "password": "secret",
                "port": 22,
            },
            connection_only=True,
        )

        self.assertFalse(result)
        self.assertEqual(adapter.attempts, 3)


class AdapterCommandTests(unittest.TestCase):
    def _write_temp_catalog(self, content: str) -> str:
        temp_file = NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".yaml", delete=False
        )
        temp_file.write(dedent(content).strip() + "\n")
        temp_file.close()
        self.addCleanup(lambda: Path(temp_file.name).unlink(missing_ok=True))
        return temp_file.name

    def test_huawei_adapter_keeps_public_command_map_compatible(self):
        adapter = HuaweiAdapter("192.168.1.10", "admin", "secret")

        self.assertEqual(adapter.commands["version"], "display version")
        self.assertIsInstance(adapter.command_specs["version"], CommandSpec)
        self.assertEqual(
            adapter.command_specs["version"].command,
            adapter.commands["version"],
        )

    def test_ruijie_log_collection_uses_generic_fallback_commands(self):
        adapter = RuijieAdapter("192.168.1.10", "admin", "secret")
        adapter.is_connected = True

        with patch.object(
            adapter,
            "send_command",
            side_effect=[
                (False, "unknown command"),
                (False, "unknown command"),
                (True, "x" * 60),
            ],
        ) as mock_send:
            success, logs, message = adapter.get_logs()

        self.assertTrue(success)
        self.assertIn("成功获取 1 个日志", message)
        self.assertIn("show logging", logs)
        self.assertEqual(
            [call.args[0] for call in mock_send.call_args_list],
            ["show loggin", "sh loggin", "show logging"],
        )

    def test_ruijie_xialian_reuses_ruijie_command_catalog(self):
        adapter = RuijieAdapter(
            "192.168.1.10", "admin", "secret", vendor="ruijie_xialian"
        )

        self.assertEqual(adapter.commands["version"], "show version")
        self.assertIn("logging", adapter._get_log_commands_from_catalog())

    def test_hostname_specific_commands_override_vendor_defaults(self):
        catalog_file = self._write_temp_catalog(
            """
            version: 1
            groups:
              huawei_base:
                interface_brief: display interface brief
            vendors:
              huawei:
                standard_groups:
                  - huawei_base
                standard:
                  version: display version
                  device: display device
                logs:
                  logbuffer: display logbuffer
            hostnames:
              core_sw_01:
                vendor: huawei
                standard:
                  version: display startup
                  transceiver: display transceiver diagnosis interface 10ge1/0/1
                logs:
                  alarm: display alarm active
            """
        )

        adapter = AdapterFactory.create(
            vendor="huawei",
            host="192.168.1.10",
            username="admin",
            password="secret",
            config={"commands": {"catalog_file": catalog_file}},
            device_name="CORE_SW_01",
        )

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.commands["version"], "display startup")
        self.assertEqual(adapter.commands["device"], "display device")
        self.assertEqual(
            adapter.commands["transceiver"],
            "display transceiver diagnosis interface 10ge1/0/1",
        )
        self.assertEqual(adapter.commands["interface_brief"], "display interface brief")

        log_commands = adapter._get_log_commands_from_catalog()
        self.assertIn("logbuffer", log_commands)
        self.assertIn("alarm", log_commands)

    def test_hostname_override_respects_vendor_constraint(self):
        catalog_file = self._write_temp_catalog(
            """
            version: 1
            groups: {}
            vendors:
              huawei:
                standard:
                  version: display version
              h3c:
                standard:
                  version: display version
            hostnames:
              core_sw_01:
                vendor: h3c
                standard:
                  version: display current-configuration
            """
        )

        adapter = AdapterFactory.create(
            vendor="huawei",
            host="192.168.1.10",
            username="admin",
            password="secret",
            config={"commands": {"catalog_file": catalog_file}},
            device_name="core_sw_01",
        )

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.commands["version"], "display version")


if __name__ == "__main__":
    unittest.main()
