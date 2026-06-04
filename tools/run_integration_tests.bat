@echo off
echo ========================================
echo  Python Project - Run Integration Tests
echo ========================================
echo.

:: Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv is not installed or not in PATH
    echo Please install uv first: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

echo Running integration tests...
echo.
uv run pytest tests/integration/ -v
if %ERRORLEVEL% neq 0 (
    echo.
    echo ========================================
    echo  Some integration tests failed!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo  All integration tests passed!
    echo ========================================
)
echo.
pause
