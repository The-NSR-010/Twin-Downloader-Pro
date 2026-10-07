$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

uv add --dev pyinstaller
uv run pyinstaller --noconfirm --clean --onedir --windowed --name MediaDownloaderStudio `
  --add-data "resources;resources" `
  launcher.py

Write-Host "Build complete: dist\MediaDownloaderStudio\MediaDownloaderStudio.exe"
