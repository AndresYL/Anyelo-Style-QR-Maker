@echo off
REM Crea el .exe de Anyelo Style QR en dist\AnyeloStyleQR\AnyeloStyleQR.exe
REM Requisito: Python 3.11 o 3.12 instalado (marca "Add Python to PATH" al instalarlo).

python -m venv .venv || goto :error
call .venv\Scripts\activate || goto :error
python -m pip install --upgrade pip || goto :error
pip install -r requirements-dev.txt || goto :error

python -m pytest -q || goto :error

pyinstaller --noconfirm --clean --windowed --name AnyeloStyleQR ^
  --icon anyelo_qr\assets\icon.ico ^
  --add-data "anyelo_qr\assets;anyelo_qr\assets" ^
  --collect-all pypdfium2 --collect-all pypdfium2_raw --collect-all zxingcpp ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
  main.py || goto :error

echo.
echo Listo: dist\AnyeloStyleQR\AnyeloStyleQR.exe
pause
exit /b 0

:error
echo.
echo Algo fallo. Copia el mensaje de arriba y pegamelo en el chat.
pause
exit /b 1
