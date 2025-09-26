@echo off
call venv\Scripts\activate
python tester.py > app.log 2>&1
pause
