@echo off
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "START_SCRIPT=%SCRIPT_DIR%start_app.py"
set "BACKEND_DIR=%PROJECT_DIR%\backend"

echo =============================================
echo          朝花夕拾 Flower Dance
echo =============================================
echo.

if not exist "%START_SCRIPT%" (
    echo 错误: 找不到启动脚本 %START_SCRIPT%
    pause
    exit /b 1
)

echo [1/3] 检查 Python 环境...
where python >nul 2>&1
if %errorlevel% neq 0 (
    where python3 >nul 2>&1
    if %errorlevel% neq 0 (
        echo 错误: 未找到 Python，请先安装 Python 3.9+
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python3"
) else (
    set "PYTHON_CMD=python"
)
echo   ✓ 已找到 Python

echo.
echo [2/3] 检查依赖...
cd /d "%BACKEND_DIR%"
%PYTHON_CMD% -c "import fastapi, uvicorn, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo   正在安装依赖...
    %PYTHON_CMD% -m pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo   ✗ 依赖安装失败
        pause
        exit /b 1
    )
    echo   ✓ 依赖安装完成
) else (
    echo   ✓ 依赖已就绪
)

echo.
echo [3/3] 启动应用...
cd /d "%PROJECT_DIR%"
%PYTHON_CMD% "%START_SCRIPT%"

pause