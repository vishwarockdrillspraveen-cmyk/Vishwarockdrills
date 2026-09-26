@echo off
setlocal

set GIT_EXE="C:\Program Files\Git\cmd\git.exe"
set REPO_DIR=C:\vishwa_rockdrills_code

cd /d "%REPO_DIR%"

:menu
cls
echo =====================================================
echo Vishwa Rock Drills - Launcher
echo =====================================================
echo 1) Start Streamlit app
echo 2) Stop Streamlit app
echo 3) Pull from GitHub
echo 4) Push to GitHub
echo 5) Git status
echo 6) Exit
set /p choice="Enter choice (1-6): "

if "%choice%"=="1" (
    echo Starting Streamlit app on port 8501...
    taskkill /F /IM streamlit.exe >nul 2>&1
    start "Streamlit App" cmd /k "cd /d %REPO_DIR% && python -m streamlit run app.py --server.port 8501"
    start "http://localhost:8501"
    goto menu
)

if "%choice%"=="2" (
    echo Stopping Streamlit app...
    taskkill /F /IM streamlit.exe >nul 2>&1
    goto menu
)

if "%choice%"=="3" (
    echo Pulling latest changes...
    "%GIT_EXE%" pull origin main
    pause
    goto menu
)

if "%choice%"=="4" (
    echo.
    echo Enter commit message:
    set /p commit_msg="Commit message: "
    if "%commit_msg%"=="" (
        set commit_msg=Update project
    )
    "%GIT_EXE%" add .
    "%GIT_EXE%" commit -m "%commit_msg%"
    "%GIT_EXE%" push origin main
    pause
    goto menu
)

if "%choice%"=="5" (
    "%GIT_EXE%" status --short --branch
    pause
    goto menu
)

if "%choice%"=="6" (
    echo Exiting.
    exit /b 0
)

echo Invalid choice.
pause
goto menu
