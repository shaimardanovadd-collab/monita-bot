@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Monita Bot: qonun matnlarini Lex.uz dan yuklash
if not exist .env (echo .env fayli topilmadi! .env.example dan nusxa olib, DATABASE_URL ni yozing. & pause & exit /b)
python -m pip install -q -r requirements.txt
python load_texts.py %*
pause
