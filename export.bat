@echo off
REM export.bat — BD 快捷导出 + 推送 GitHub
REM 双击此文件即可运行

echo.
echo ================================================
echo   Seller Journey — 导出到 GitHub
echo ================================================
echo.

REM 进入 repo 目录
cd /d "%~dp0"

REM 尝试将 Git 加入 PATH
if exist "C:\Program Files\Git\cmd\git.exe" (
    set PATH=%PATH%;C:\Program Files\Git\cmd
)
if exist "C:\Program Files (x86)\Git\cmd\git.exe" (
    set PATH=%PATH%;C:\Program Files (x86)\Git\cmd
)

REM 检查 git 是否可用
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git 未安装或不在 PATH 中。
    echo         请安装 Git for Windows: https://gitforwindows.org/
    echo         安装后重启命令提示符。
    pause
    exit /b 1
)

python scripts\export_to_repo.py %*

echo.
pause
