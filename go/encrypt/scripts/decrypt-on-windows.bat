@echo off
setlocal enabledelayedexpansion

echo ZC Decryption Tool
echo ------------------
echo.

set COUNT=0
for %%F in ("%~dp0*.enc") do set /a COUNT+=1

if !COUNT!==1 (
    for %%F in ("%~dp0*.enc") do set "FILE_TO_DECRYPT=%%~fF"
    for %%F in ("%~dp0*.enc") do echo Found encrypted file: %%~nxF
    echo You will be prompted for your password next.
    echo.
) else if not "%~1"=="" (
    set "FILE_TO_DECRYPT=%~1"
) else (
    set /p FILE_TO_DECRYPT="Enter the full path to the encrypted file (or drag and drop the file here): "
    set FILE_TO_DECRYPT=!FILE_TO_DECRYPT:"=!
)

echo.
echo Starting decryption process...
echo.

set ZC=%~dp0tools\windows\amd64\zc.exe
"%ZC%" "%FILE_TO_DECRYPT%"
