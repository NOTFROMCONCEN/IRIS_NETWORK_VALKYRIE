[CmdletBinding()]
param(
    [string]$PythonExe = "py",
    [string[]]$PythonArgs = @(),
    [string]$BundleName = "Iris_Network_Valkyrie_OfflineBundle",
    [string]$OutputRoot = "",
    [switch]$SkipWheelDownload
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-PythonCommand {
    param([string[]]$Arguments)

    & $PythonExe @PythonArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python 命令执行失败: $PythonExe $($PythonArgs -join ' ') $($Arguments -join ' ')"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $PSScriptRoot "build"
}

$bundleRoot = Join-Path $OutputRoot $BundleName
$projectCopyRoot = Join-Path $bundleRoot "Iris_Network_Valkyrie"
$corebaseRoot = Join-Path $repoRoot "CoreBase"
$corebaseCopyRoot = Join-Path $projectCopyRoot "CoreBase"
$wheelhouseDir = Join-Path $bundleRoot "wheelhouse"
$pythonInstallerDir = Join-Path $bundleRoot "python-installer"
$requirementsFile = Join-Path $corebaseRoot "requirements.txt"

$requiredPaths = @(
    (Join-Path $repoRoot "main.py"),
    (Join-Path $repoRoot "README.md"),
    $requirementsFile,
    (Join-Path $corebaseRoot "core"),
    (Join-Path $corebaseRoot "config"),
    (Join-Path $PSScriptRoot "run_ui.bat"),
    (Join-Path $PSScriptRoot "run_cli.bat"),
    (Join-Path $PSScriptRoot "OFFLINE_DEPLOY.md")
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path $path)) {
        throw "缺少构建所需文件: $path"
    }
}

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    throw "未找到 Python 启动命令: $PythonExe"
}

Write-Step "检查 Python 版本"
Invoke-PythonCommand -Arguments @("--version")

Write-Step "准备输出目录: $bundleRoot"
if (Test-Path $bundleRoot) {
    Remove-Item $bundleRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $bundleRoot, $projectCopyRoot, $corebaseCopyRoot, $wheelhouseDir, $pythonInstallerDir | Out-Null

Write-Step "复制仓库运行所需文件"
Copy-Item (Join-Path $repoRoot "main.py") -Destination (Join-Path $projectCopyRoot "main.py") -Force
Copy-Item (Join-Path $repoRoot "README.md") -Destination (Join-Path $projectCopyRoot "README.md") -Force

$corebaseItems = @(
    "main.py",
    "requirements.txt",
    "SETUP.md",
    "config",
    "core",
    "devices",
    "doc",
    "scripts",
    "ui"
)

foreach ($item in $corebaseItems) {
    $sourcePath = Join-Path $corebaseRoot $item
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath -Destination $corebaseCopyRoot -Recurse -Force
    }
}

$cleanupPaths = @(
    (Join-Path $projectCopyRoot "output"),
    (Join-Path $corebaseCopyRoot "output"),
    (Join-Path $corebaseCopyRoot "devices\backups")
)

foreach ($cleanupPath in $cleanupPaths) {
    if (Test-Path $cleanupPath) {
        Remove-Item $cleanupPath -Recurse -Force
    }
}

Get-ChildItem -Path $projectCopyRoot -Directory -Recurse -Force |
Where-Object { $_.Name -in @("__pycache__", ".pytest_cache") } |
Remove-Item -Recurse -Force

Get-ChildItem -Path $projectCopyRoot -File -Recurse -Force |
Where-Object { $_.Extension -in @(".pyc", ".pyo", ".log") } |
Remove-Item -Force

New-Item -ItemType Directory -Path (Join-Path $corebaseCopyRoot "output\logs"), (Join-Path $corebaseCopyRoot "output\results") | Out-Null

Write-Step "复制交付包根目录脚本和说明"
Copy-Item (Join-Path $PSScriptRoot "run_ui.bat") -Destination (Join-Path $bundleRoot "run_ui.bat") -Force
Copy-Item (Join-Path $PSScriptRoot "run_cli.bat") -Destination (Join-Path $bundleRoot "run_cli.bat") -Force
Copy-Item (Join-Path $PSScriptRoot "OFFLINE_DEPLOY.md") -Destination (Join-Path $bundleRoot "OFFLINE_DEPLOY.md") -Force

$pythonVersion = (& $PythonExe @PythonArgs -c "import platform,sys; print(f'{sys.version.split()[0]}|{platform.architecture()[0]}')").Trim()
if ($LASTEXITCODE -ne 0) {
    throw "获取 Python 版本信息失败"
}

$pythonVersionNumber = ($pythonVersion -split "\|")[0]
$pythonMajorMinor = [regex]::Match($pythonVersionNumber, "^\d+\.\d+").Value
if ([string]::IsNullOrWhiteSpace($pythonMajorMinor)) {
    $pythonMajorMinor = $pythonVersionNumber
}

$pythonInstallerReadme = @(
    "将 Windows 版 Python 离线安装包放到此目录中。",
    "建议使用与 wheelhouse 构建时相同版本和位数的 Python 安装包。",
    "",
    "推荐命名示例:",
    "- python-$pythonMajorMinor.x-amd64.exe"
) -join [Environment]::NewLine

Set-Content -Path (Join-Path $pythonInstallerDir "README.txt") -Value $pythonInstallerReadme -Encoding UTF8

@(
    "BuildTime=$(Get-Date -Format s)",
    "PythonExe=$PythonExe",
    "PythonArgs=$($PythonArgs -join ' ')",
    "PythonVersion=$pythonVersion",
    "BundleName=$BundleName"
) | Set-Content -Path (Join-Path $bundleRoot "bundle-info.txt") -Encoding UTF8

if (-not $SkipWheelDownload) {
    Write-Step "下载离线依赖到 wheelhouse"
    Invoke-PythonCommand -Arguments @(
        "-m",
        "pip",
        "download",
        "--dest",
        $wheelhouseDir,
        "-r",
        $requirementsFile
    )
}
else {
    Write-Step "跳过 wheelhouse 下载"
}

Write-Step "离线交付包已生成: $bundleRoot"
Write-Host "后续操作:" -ForegroundColor Green
Write-Host "  1. 将 Python 离线安装包放入 $pythonInstallerDir"
Write-Host "  2. 将整个 $bundleRoot 目录拷贝到目标内网笔记本"
Write-Host "  3. 按 OFFLINE_DEPLOY.md 在目标机器完成安装"