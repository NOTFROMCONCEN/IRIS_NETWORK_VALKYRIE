@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "BUNDLE_ROOT=%~dp0"
set "PYTHON_EXE=%BUNDLE_ROOT%.venv\Scripts\python.exe"
set "PROJECT_ROOT=%BUNDLE_ROOT%Iris_Network_Valkyrie"

if not exist "%PYTHON_EXE%" (
    echo [错误] 未找到离线虚拟环境: "%PYTHON_EXE%"
    echo [提示] 请先按 OFFLINE_DEPLOY.md 完成 Python 安装和离线依赖安装。
    exit /b 1
)

if not exist "%PROJECT_ROOT%\main.py" (
    echo [错误] 未找到项目入口: "%PROJECT_ROOT%\main.py"
    exit /b 1
)

cd /d "%PROJECT_ROOT%"
"%PYTHON_EXE%" main.py %*
endlocal