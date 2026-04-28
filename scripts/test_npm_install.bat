@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo.
echo  ============================================================
echo    OpenClaw npm Install - Debug Test
echo  ============================================================
echo.

:: Check node/npm
where node >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Node.js not found in PATH
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do echo [OK] Node.js: %%v

where npm >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] npm not found in PATH
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('npm --version') do echo [OK] npm: %%v

echo.
echo -- npm config --
for /f "tokens=*" %%v in ('npm config get prefix') do echo   prefix: %%v
for /f "tokens=*" %%v in ('npm config get cache') do echo   cache: %%v
for /f "tokens=*" %%v in ('npm config get registry') do echo   registry: %%v
echo.

:: Test 1: standard global install
echo ============================================================
echo [TEST 1] npm install -g openclaw
echo ============================================================
echo.
call npm install -g openclaw
if !ERRORLEVEL! EQU 0 (
    echo.
    echo [SUCCESS] Test 1 passed!
    where openclaw 2>nul
    goto :done
)
echo.
echo [FAIL] Test 1 failed, errorlevel=!ERRORLEVEL!
echo.

:: Test 2: user prefix
echo ============================================================
echo [TEST 2] npm install -g openclaw --prefix "%USERPROFILE%\.npm-global"
echo ============================================================
echo.
if not exist "%USERPROFILE%\.npm-global" mkdir "%USERPROFILE%\.npm-global"
call npm install -g openclaw --prefix "%USERPROFILE%\.npm-global"
if !ERRORLEVEL! EQU 0 (
    echo.
    echo [SUCCESS] Test 2 passed!
    echo Installed to: %USERPROFILE%\.npm-global
    goto :done
)
echo.
echo [FAIL] Test 2 failed, errorlevel=!ERRORLEVEL!
echo.

:: Test 3: mirror registry
echo ============================================================
echo [TEST 3] npm install -g openclaw --registry https://registry.npmmirror.com
echo ============================================================
echo.
call npm install -g openclaw --registry https://registry.npmmirror.com
if !ERRORLEVEL! EQU 0 (
    echo.
    echo [SUCCESS] Test 3 passed!
    where openclaw 2>nul
    goto :done
)
echo.
echo [FAIL] Test 3 failed, errorlevel=!ERRORLEVEL!
echo.

:: Test 4: mirror + user prefix
echo ============================================================
echo [TEST 4] npm install -g openclaw --prefix "%USERPROFILE%\.npm-global" --registry https://registry.npmmirror.com
echo ============================================================
echo.
call npm install -g openclaw --prefix "%USERPROFILE%\.npm-global" --registry https://registry.npmmirror.com
if !ERRORLEVEL! EQU 0 (
    echo.
    echo [SUCCESS] Test 4 passed!
    goto :done
)
echo.
echo [FAIL] Test 4 failed, errorlevel=!ERRORLEVEL!
echo.

:: All failed
echo ============================================================
echo [ALL FAILED] None of the methods worked.
echo.
echo Possible causes:
echo   - Network firewall blocking npm registry
echo   - Antivirus blocking npm operations
echo   - Disk permission issues
echo   - Corporate proxy not configured
echo.
echo Try manually in Admin cmd:
echo   npm install -g openclaw
echo.
echo Or set proxy:
echo   npm config set proxy http://your-proxy:port
echo   npm config set https-proxy http://your-proxy:port
echo ============================================================

:done
echo.
echo ============================================================
echo Press any key to exit...
echo ============================================================
pause >nul
exit /b 0
