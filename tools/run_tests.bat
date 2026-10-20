@echo off
echo ========================================
echo  Python Project - Run Tests
echo ========================================
echo.

:: Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv is not installed or not in PATH
    echo Please install uv first: https://docs.astral.sh/uv/getting-started/installation/
    if not "%TICKETS_WATCHER_COMMAND_RUN%"=="1" pause
    exit /b 1
)

echo Running tests...
echo.
uv run pytest tests/ -v
set "RESULT=%ERRORLEVEL%"
if %RESULT% neq 0 (
    echo.
    echo ========================================
    echo  Some tests failed!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo  All tests passed!
    echo ========================================
)
echo.
if not "%TICKETS_WATCHER_COMMAND_RUN%"=="1" pause
exit /b %RESULT%
