@echo off
echo ZC Decryption Tool
echo ------------------
echo.
set /p FILE_TO_DECRYPT="Enter the full path to the encrypted file (or drag and drop the file here): "

set FILE_TO_DECRYPT=%FILE_TO_DECRYPT:"=%

echo.
echo Starting decryption process...
echo.

cd /d %~dp0\..\windows\amd64
zc.exe %FILE_TO_DECRYPT%

echo.
echo If the decryption was successful, your files have been extracted.
echo Press any key to exit.
pause >nul
