$ErrorActionPreference = "SilentlyContinue"

Get-ChildItem -Path . -Recurse -Directory -Filter __pycache__ |
Remove-Item -Recurse -Force

Get-ChildItem -Path . -Recurse -File -Include *.pyc, *.pyo |
Remove-Item -Force

Write-Host "Pycache cleanup completed."
