@echo off
rem Wrapper: bypass PowerShell execution policy, then run backup_apps.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup_apps.ps1" %*
