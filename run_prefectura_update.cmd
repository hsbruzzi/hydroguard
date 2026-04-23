@echo off
cd /d "%~dp0"

call backend\.venv\Scripts\activate.bat
python publish_prefectura_gist.py