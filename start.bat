@echo off
chcp 65001 >nul
title t2x-suite (Novel Studio + T2VN / T2C)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
