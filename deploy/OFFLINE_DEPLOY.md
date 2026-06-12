# 离线部署说明

本文档对应仓库根目录下的 `deploy/offline_build.ps1`、`deploy/run_ui.bat` 和 `deploy/run_cli.bat`。

## 适用场景

- 目标机器无法访问外网
- 需要通过 `python main.py --ui` 使用本地 Web UI
- 希望将项目连同依赖整理成一个可拷贝交付包

## 交付包内容

执行构建脚本后，默认会在 `deploy/build/Iris_Network_Valkyrie_OfflineBundle/` 下生成：

1. `Iris_Network_Valkyrie/`：项目运行副本
2. `wheelhouse/`：离线依赖目录
3. `python-installer/`：Python 安装包放置目录
4. `run_ui.bat`：启动 UI
5. `run_cli.bat`：启动 CLI
6. `OFFLINE_DEPLOY.md`：本说明

## 一、在联网机器上生成交付包

建议联网机器与目标机器保持相同的 Windows 版本、CPU 架构和 Python 大小版本。

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\offline_build.ps1
```

如需指定 Python 解释器：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\offline_build.ps1 -PythonExe "C:\\Python314\\python.exe"
```

如果你是在当前 PowerShell 会话里直接调用脚本，也可以传 `py` 启动器参数，例如：

```powershell
.\deploy\offline_build.ps1 -PythonExe py -PythonArgs "-3.14"
```

构建完成后，请手动把对应版本的 Windows Python 安装包放入：

```text
deploy\build\Iris_Network_Valkyrie_OfflineBundle\python-installer\
```

推荐放入 64 位安装包，并与构建 wheelhouse 时使用的 Python 版本保持一致。

## 二、将交付包复制到内网笔记本

将整个目录复制到目标机器，例如：

```text
D:\Tools\Iris_Network_Valkyrie_OfflineBundle\
```

下文默认你已经进入交付包根目录。

## 三、在内网笔记本完成安装

1. 先运行 `python-installer` 目录中的 Python 安装包。
2. 安装完成后，在交付包根目录创建虚拟环境：

```powershell
py -m venv .venv
```

如果目标机器上安装了多个 Python 版本，请以交付包根目录中的 `bundle-info.txt` 为准，选择与其中 `PythonVersion=` 一致的大版本和小版本。

如果目标机器没有 `py` 启动器，也可以改用 Python 安装目录中的 `python.exe`。

3. 使用离线依赖目录安装运行依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r .\Iris_Network_Valkyrie\CoreBase\requirements.txt
```

## 四、验证安装结果

先做基础环境检查：

```powershell
Set-Location .\Iris_Network_Valkyrie\CoreBase
..\..\.venv\Scripts\python.exe scripts\check_env.py
Set-Location ..\..
```

然后验证入口：

```powershell
.\run_cli.bat --help
.\run_ui.bat
```

说明：当前 `scripts/check_env.py` 只检查核心依赖，不检查 `streamlit`。因此即使环境检查通过，也建议额外执行一次 `run_ui.bat`。

## 五、运行与日常使用

UI 模式：

```powershell
.\run_ui.bat
```

CLI 模式：

```powershell
.\run_cli.bat
.\run_cli.bat --vendor huawei
.\run_cli.bat --dry-run
```

## 六、需要一并带走的业务文件

请确认交付包中的以下文件已经替换为你的实际配置：

- `Iris_Network_Valkyrie\CoreBase\config\config.yaml`
- `Iris_Network_Valkyrie\CoreBase\config\password.conf`
- `Iris_Network_Valkyrie\CoreBase\devices\devices.xlsx`

如果这些文件包含生产密码或真实设备信息，请按内网交付要求单独管控。

## 七、常见问题

### 1. `run_ui.bat` 启动失败

优先检查以下几点：

- `.venv\Scripts\python.exe` 是否存在
- `wheelhouse` 是否是用同版本 Python 下载出来的
- 目标机器是否能访问设备 IP 和 SSH 端口

### 2. 环境检查通过，但 UI 仍然启动失败

常见原因是 `streamlit` 没有正确安装。可执行：

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse streamlit
```

### 3. 能打开 UI，但巡检连不上设备

这通常不是外网问题，而是目标机器到设备网段的连通性问题。请检查：

- 目标笔记本是否已接入设备所在内网
- 设备 IP 是否可达
- 22 端口或配置中的 SSH 端口是否开放

## 八、为什么当前不建议直接打包成单文件 exe

当前 UI 启动链路会再次调用 Python 和 Streamlit，巡检执行时也会拉起新的 Python 子进程。现阶段更适合目录式离线交付，不适合直接做单文件 exe。