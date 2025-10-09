@echo off
setlocal

:: --- WebRequestTimerプロジェクトの設定 ---
set PROJECT_NAME=WebRequestTimer
set ENTRY_SCRIPT=main.py

:: --- 仮想環境を有効化 ---
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo 仮想環境を有効化しました
) else (
    echo 警告: 仮想環境が見つかりません
)

:: --- 必要なパッケージをインストール ---
echo 必要なパッケージをインストール中...
pip install -r requirements.txt
pip install pyinstaller
echo.

:: --- 古いビルドを削除 ---
echo 古いビルドファイルを削除中...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec
echo.

:: --- PyInstallerのオプションをまとめる ---
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

:: --- PyInstallerでビルド ---
echo %PROJECT_NAME%をビルド中...
echo オプション: %OPTIONS%
echo.
pyinstaller %OPTIONS% %ENTRY_SCRIPT%

:: --- ビルド結果を確認 ---
echo.
if exist "dist\%PROJECT_NAME%.exe" (
    echo =====================================
    echo ビルド完了！ dist フォルダを確認してください
    echo =====================================
    echo.
    echo ビルドされたファイル:
    dir "dist\%PROJECT_NAME%.exe"
    echo.
    echo 実行可能ファイルサイズ:
    for %%F in ("dist\%PROJECT_NAME%.exe") do echo %%~zF bytes
    echo.
    echo distフォルダにlogsディレクトリを作成...
    if not exist "dist\logs" mkdir "dist\logs"
    echo config.jsonをdistフォルダにコピー...
    if exist "config.json" copy "config.json" "dist\" >nul
) else (
    echo =====================================
    echo ビルドに失敗しました
    echo =====================================
    echo エラーログを確認してください
)

echo.
pause
endlocal
