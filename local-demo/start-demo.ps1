$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$env:DEMO_DATA_DIR = Join-Path $Root 'data'
$env:LLM_MODE = if ($env:LLM_MODE) { $env:LLM_MODE } else { 'auto' }
Set-Location $Root
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

