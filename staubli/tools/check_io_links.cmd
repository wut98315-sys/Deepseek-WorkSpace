@echo off
rem Wrapper: bypass PowerShell execution policy, then run check_io_links.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_io_links.ps1" %*
