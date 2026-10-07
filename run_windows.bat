@echo off
setlocal
cd /d "%~dp0"
uv run twin-downloader-pro
if errorlevel 1 pause
