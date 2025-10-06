@echo off
setlocal

:: --- LoudSyncプロジェクトの設定 ---
set PROJECT_NAME=LoudSync
set ENTRY_SCRIPT=main.py

:: --- PyInstallerのオプションをまとめる ---
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

:: --- 仮想環境を有効化（必要なら） ---
:: call venv\Scripts\activate.bat

:: --- 古いビルドを削除 ---
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec

:: --- PyInstallerでビルド ---
echo Building %PROJECT_NAME%...
echo Options: %OPTIONS%
echo.
pyinstaller %OPTIONS% %ENTRY_SCRIPT%

:: --- ビルド完了メッセージ ---
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
