:: MT5 客户端连接器 - 一键启动
:: 将此文件夹复制到你的电脑，双击运行即可
:: 首次运行会自动进入配置向导

@echo off
cd /d %~dp0

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 请先安装 Python 3.7+ https://www.python.org/downloads/
    pause
    exit /b
)

:: 检查依赖
python -c "import MetaTrader5, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装依赖...
    pip install MetaTrader5 requests -q
)

echo ====================================
echo   MT5/MT4 客户端连接器
echo ====================================
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
python mt5_push.py
goto end

:mt4
python mt4_push.py
goto end

:setup
python mt5_push.py --setup
goto end

:quit
exit /b

:end
pause
