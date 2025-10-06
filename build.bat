@echo off
setlocal

:: --- LoudSync�v���W�F�N�g�̐ݒ� ---
set PROJECT_NAME=LoudSync
set ENTRY_SCRIPT=main.py

:: --- PyInstaller�̃I�v�V�������܂Ƃ߂� ---
set OPTIONS=--name %PROJECT_NAME% ^
 --onefile ^
 --windowed ^
 --add-data "bin;bin" ^
 --add-data "assets;assets" ^
 --add-data "modules;modules" ^
 --icon "assets\icon.ico" ^
 --hidden-import "asyncio" ^
 --hidden-import "tkinter" ^
 --hidden-import "tkinter.ttk" ^
 --hidden-import "tkinter.filedialog" ^
 --hidden-import "tkinter.messagebox" ^
 --hidden-import "tkinter.scrolledtext"

:: --- ���z����L�����i�K�v�Ȃ�j ---
:: call venv\Scripts\activate.bat

:: --- �Â��r���h���폜 ---
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec

:: --- PyInstaller�Ńr���h ---
echo Building %PROJECT_NAME%...
echo Options: %OPTIONS%
echo.
pyinstaller %OPTIONS% %ENTRY_SCRIPT%

:: --- �r���h�������b�Z�[�W ---
echo.
echo =====================================
echo Build complete! Check /dist folder.
echo =====================================
echo.
echo Built files:
dir dist\%PROJECT_NAME%.exe
echo.

pause
endlocal
