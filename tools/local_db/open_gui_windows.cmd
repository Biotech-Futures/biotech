@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
set "BASE_COMPOSE=%REPO_ROOT%\docker-compose.dev.yml"
set "TOOL_COMPOSE=%SCRIPT_DIR%compose.generator.yml"
set "GUI_URL=http://127.0.0.1:8765"

if not exist "%BASE_COMPOSE%" (
  echo Could not find the project Compose file:
  echo   "%BASE_COMPOSE%"
  goto failure
)
if not exist "%TOOL_COMPOSE%" (
  echo Could not find the local database Compose file:
  echo   "%TOOL_COMPOSE%"
  goto failure
)

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker CLI is not installed or is not available on PATH.
  echo Install and start Docker Desktop, then run this launcher again.
  goto failure
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo Docker Compose v2 is not available.
  echo Update Docker Desktop, then run this launcher again.
  goto failure
)

where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo Windows PowerShell is unavailable and is required for the local health check.
  goto failure
)

if defined DOCKER_CONTEXT if defined DOCKER_HOST (
  echo Both DOCKER_CONTEXT and DOCKER_HOST are set.
  echo Clear one override so the launcher can verify the effective local endpoint.
  goto failure
)

powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$prefix = 'npipe:////./pipe/'; $comparison = [System.StringComparison]::OrdinalIgnoreCase; if ($env:DOCKER_HOST -and -not ($env:DOCKER_HOST.StartsWith($prefix, $comparison))) { exit 2 }; $endpoint = (& docker context inspect --format '{{.Endpoints.docker.Host}}' 2>$null); if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$endpoint)) { exit 1 }; $endpoint = ([string]$endpoint).Trim(); if (-not ($endpoint.StartsWith($prefix, $comparison))) { exit 2 }; exit 0" >nul 2>&1
if errorlevel 2 (
  echo Refusing to use a Docker endpoint outside the local Windows named-pipe namespace.
  echo Switch Docker Desktop to a local context, then run this launcher again.
  goto failure
)
if errorlevel 1 (
  echo The active Docker context could not be inspected.
  goto failure
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not running or the current user cannot access it.
  echo Start Docker Desktop, wait until it is ready, then retry.
  goto failure
)

powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$dockerOs = (& docker info --format '{{.OSType}}' 2>$null); if ($LASTEXITCODE -ne 0 -or ([string]$dockerOs).Trim() -cne 'linux') { exit 1 }; exit 0" >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not using Linux containers.
  echo Switch Docker Desktop to Linux containers, then retry.
  goto failure
)

powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$state = ''; try { $job = Invoke-RestMethod -Uri '%GUI_URL%/api/job' -TimeoutSec 2 -ErrorAction Stop; $state = [string]$job.state } catch { exit 0 }; if ($state -eq 'queued' -or $state -eq 'running') { exit 2 }; exit 0" >nul 2>&1
if errorlevel 2 (
  echo A local database generation job is currently queued or running.
  echo Wait for it to finish before running this launcher again.
  goto failure
)
if errorlevel 1 (
  echo The current GUI job state could not be inspected safely.
  goto failure
)

echo Starting the BIOTech local dataset GUI...
docker compose --project-directory "%REPO_ROOT%" -f "%BASE_COMPOSE%" -f "%TOOL_COMPOSE%" build local-db-gui
if errorlevel 1 (
  echo Docker Compose could not build the GUI image.
  goto failure
)

docker compose --project-directory "%REPO_ROOT%" -f "%BASE_COMPOSE%" -f "%TOOL_COMPOSE%" up --detach --wait --no-recreate postgres
if errorlevel 1 (
  echo Docker Compose could not start a healthy local PostgreSQL service.
  goto failure
)

powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$metadata = $null; try { $metadata = Invoke-RestMethod -Uri '%GUI_URL%/api/config' -TimeoutSec 2 -ErrorAction Stop } catch { $running = (& docker compose --project-directory $env:REPO_ROOT -f $env:BASE_COMPOSE -f $env:TOOL_COMPOSE ps --status running --quiet local-db-gui 2>$null); if ($LASTEXITCODE -ne 0) { exit 1 }; if (-not [string]::IsNullOrWhiteSpace([string]$running)) { exit 1 }; exit 0 }; if ([string]::IsNullOrWhiteSpace([string]$metadata.csrf_token)) { exit 1 }; $headers = @{'Origin' = $env:GUI_URL; 'X-Local-DB-Token' = [string]$metadata.csrf_token}; try { $body = @{confirm_restart = $true} | ConvertTo-Json -Compress; Invoke-RestMethod -Method Post -Uri '%GUI_URL%/api/prepare-restart' -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 2 -ErrorAction Stop | Out-Null; exit 0 } catch { $code = 0; try { $code = [int]$_.Exception.Response.StatusCode } catch {}; if ($code -eq 409) { exit 2 }; if ($code -eq 404) { exit 3 }; exit 1 }" >nul 2>&1
if errorlevel 3 (
  echo The running GUI predates atomic safe-reload support.
  echo Stop only local-db-gui once, then run this launcher again.
  goto failure
)
if errorlevel 2 (
  echo A generation job or another GUI reload is currently active.
  echo Wait for it to finish before running this launcher again.
  goto failure
)
if errorlevel 1 (
  echo The running GUI could not be prepared safely for reload.
  goto failure
)

echo Recreating only the GUI so it uses the current checkout...
docker compose --project-directory "%REPO_ROOT%" -f "%BASE_COMPOSE%" -f "%TOOL_COMPOSE%" up --detach --force-recreate --no-deps local-db-gui
if errorlevel 1 (
  echo Docker Compose could not recreate the GUI.
  goto gui_failed
)

powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$deadline = (Get-Date).AddSeconds(30); while ((Get-Date) -lt $deadline) { try { $response = Invoke-RestMethod -Uri '%GUI_URL%/api/health' -TimeoutSec 1 -ErrorAction Stop; if ($response.status -eq 'ok') { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1" >nul 2>&1
if errorlevel 1 goto health_failed

echo GUI ready: %GUI_URL%
if "%LOCAL_DB_GUI_SKIP_OPEN%"=="1" exit /b 0
start "" "%GUI_URL%"
if errorlevel 1 (
  echo The default browser could not be opened automatically.
  echo Open this URL manually: %GUI_URL%
)
exit /b 0

:health_failed
echo The GUI did not become ready at %GUI_URL%.

:gui_failed
echo Recent container output:
docker compose --project-directory "%REPO_ROOT%" -f "%BASE_COMPOSE%" -f "%TOOL_COMPOSE%" logs --tail 50 local-db-gui
docker compose --project-directory "%REPO_ROOT%" -f "%BASE_COMPOSE%" -f "%TOOL_COMPOSE%" stop local-db-gui >nul 2>&1
goto failure

:failure
echo.
if "%LOCAL_DB_GUI_NO_PAUSE%"=="1" exit /b 1
pause
exit /b 1
