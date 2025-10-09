@echo off
setlocal

:: --- WebRequestTimer�v���W�F�N�g�̐ݒ� ---
set PROJECT_NAME=WebRequestTimer
set ENTRY_SCRIPT=main.py

:: --- ���z����L���� ---
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo ���z����L�������܂���
) else (
    echo �x��: ���z����������܂���
)

:: --- �K�v�ȃp�b�P�[�W���C���X�g�[�� ---
echo �K�v�ȃp�b�P�[�W���C���X�g�[����...
pip install -r requirements.txt
pip install pyinstaller
echo.

:: --- �Â��r���h���폜 ---
echo �Â��r���h�t�@�C�����폜��...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec
echo.

:: --- PyInstaller�̃I�v�V�������܂Ƃ߂� ---
set OPTIONS=--name %PROJECT_NAME% ^
 --onefile ^
 --noconsole ^
 --add-data "assets;assets" ^
 --add-data "modules;modules" ^
 --add-data "config.json;." ^
 --icon "assets\icon.ico" ^
 --hidden-import "aioconsole" ^
 --hidden-import "aiohttp" ^
 --hidden-import "croniter" ^
 --hidden-import "PIL" ^
 --hidden-import "PIL.Image" ^
 --hidden-import "pystray" ^
 --hidden-import "pystray._win32" ^
 --hidden-import "threading" ^
 --hidden-import "asyncio" ^
 --hidden-import "sqlite3" ^
 --hidden-import "json" ^
 --hidden-import "logging" ^
 --hidden-import "logging.handlers" ^
 --hidden-import "socket" ^
 --hidden-import "subprocess" ^
 --hidden-import "tempfile" ^
 --hidden-import "win32api" ^
 --hidden-import "win32con" ^
 --hidden-import "win32gui" ^
 --hidden-import "ctypes.wintypes"

:: --- PyInstaller�Ńr���h ---
echo %PROJECT_NAME%���r���h��...
echo �I�v�V����: %OPTIONS%
echo.
pyinstaller %OPTIONS% %ENTRY_SCRIPT%

:: --- �r���h���ʂ��m�F ---
echo.
if exist "dist\%PROJECT_NAME%.exe" (
    echo =====================================
    echo �r���h�����I dist �t�H���_���m�F���Ă�������
    echo =====================================
    echo.
    echo �r���h���ꂽ�t�@�C��:
    dir "dist\%PROJECT_NAME%.exe"
    echo.
    echo ���s�\�t�@�C���T�C�Y:
    for %%F in ("dist\%PROJECT_NAME%.exe") do echo %%~zF bytes
    echo.
    echo dist�t�H���_��logs�f�B���N�g�����쐬...
    if not exist "dist\logs" mkdir "dist\logs"
    echo config.json��dist�t�H���_�ɃR�s�[...
    if exist "config.json" copy "config.json" "dist\" >nul
) else (
    echo =====================================
    echo �r���h�Ɏ��s���܂���
    echo =====================================
    echo �G���[���O���m�F���Ă�������
)

echo.
pause
endlocal
