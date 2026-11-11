@echo off
cd /d D:\Starfield\bot
if exist STOP del STOP
"C:\Python313\python.exe" -I translate_bot.py run --parallel 3 %* >> work\log.txt 2>&1
