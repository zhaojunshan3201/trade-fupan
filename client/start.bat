@echo off
chcp 65001 >nul
title 交易复盘 MT4/MT5 客户端连接器
cd /d %~dp0
set "LOG=%~dp0connector.log"
echo [%date% %time%] start.bat launched > "%LOG%"

if not exist "%~dp0mt5_push.py" (
    echo.
    echo 未找到 mt5_push.py。
    echo 请先解压 trade-journal-client.zip，再双击解压后文件夹里的 start.bat。
    echo.
    echo [%date% %time%] missing mt5_push.py >> "%LOG%"
    pause
    exit /b 1
)

if not exist "%~dp0mt4_push.py" (
    echo.
    echo 未找到 mt4_push.py。
    echo 请先解压 trade-journal-client.zip，再双击解压后文件夹里的 start.bat。
    echo.
    echo [%date% %time%] missing mt4_push.py >> "%LOG%"
    pause
    exit /b 1
)

set "PYTHON_CMD=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py -3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=py -3"
    )
)

:: 检查 Python
%PYTHON_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 未检测到 Python。
    echo 请先安装 Python 3.7+ https://www.python.org/downloads/
    echo 安装时请勾选 Add Python to PATH。
    echo.
    echo [%date% %time%] python not found >> "%LOG%"
    pause
    exit /b 1
)

echo ====================================
echo   MT5/MT4 客户端连接器
echo ====================================
echo.
echo 请确认：
echo  1. 已解压 zip，不是在压缩包里直接运行
echo  2. 本机 MT4/MT5 已打开并登录账户
echo  3. config.ini 已在本目录中
echo.
echo  [1] MT5 自动连接 (MetaTrader 5)
echo  [2] MT4 CSV 监控 (MetaTrader 4)
echo  [S] 重新配置
echo  [Q] 退出
echo.
choice /c 12SQ /n /m "请选择: "
if errorlevel 4 goto quit
if errorlevel 3 goto setup
if errorlevel 2 goto mt4
if errorlevel 1 goto mt5

:mt5
%PYTHON_CMD% -c "import MetaTrader5, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 正在安装 MT5 依赖...
    echo [%date% %time%] installing mt5 dependencies >> "%LOG%"
    %PYTHON_CMD% -m pip install --user MetaTrader5 requests
    if %errorlevel% neq 0 (
        echo.
        echo MT5 依赖安装失败。请检查网络，或手动运行：
        echo %PYTHON_CMD% -m pip install --user MetaTrader5 requests
        echo.
        echo [%date% %time%] mt5 dependency install failed >> "%LOG%"
        pause
        exit /b 1
    )
)
echo [%date% %time%] run mt5_push.py >> "%LOG%"
%PYTHON_CMD% mt5_push.py
goto end

:mt4
%PYTHON_CMD% -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 正在安装 MT4 依赖...
    echo [%date% %time%] installing mt4 dependencies >> "%LOG%"
    %PYTHON_CMD% -m pip install --user requests
    if %errorlevel% neq 0 (
        echo.
        echo MT4 依赖安装失败。请检查网络，或手动运行：
        echo %PYTHON_CMD% -m pip install --user requests
        echo.
        echo [%date% %time%] mt4 dependency install failed >> "%LOG%"
        pause
        exit /b 1
    )
)
echo [%date% %time%] run mt4_push.py >> "%LOG%"
%PYTHON_CMD% mt4_push.py
goto end

:setup
%PYTHON_CMD% -c "import MetaTrader5, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 正在安装 MT5 配置依赖...
    %PYTHON_CMD% -m pip install --user MetaTrader5 requests
    if %errorlevel% neq 0 (
        pause
        exit /b 1
    )
)
echo [%date% %time%] run setup >> "%LOG%"
%PYTHON_CMD% mt5_push.py --setup
goto end

:quit
exit /b

:end
echo.
echo 如果上方有错误，请把本目录 connector.log 发给管理员排查。
pause
