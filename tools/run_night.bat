@echo off
cd /d D:\Starfield\bot
"C:\Python313\python.exe" -I translate_bot.py run --until 07:30 >> work\log.txt 2>&1
