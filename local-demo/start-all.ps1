$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Workspace = Split-Path -Parent $Root
$Ollama = Join-Path $Workspace 'tools\ollama\ollama.exe'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Logs = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force $Logs | Out-Null

$env:OLLAMA_MODELS = Join-Path $Workspace 'tools\models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_KEEP_ALIVE = '2m'
$env:CUDA_VISIBLE_DEVICES = '-1'
$env:GGML_VK_VISIBLE_DEVICES = '-1'
$env:OLLAMA_LLM_LIBRARY = 'cpu'
$env:DEMO_DATA_DIR = Join-Path $Root 'data'
$env:LLM_MODE = 'auto'

if (-not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $Ollama -ArgumentList 'serve' -WorkingDirectory (Split-Path $Ollama) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'ollama.out.log') -RedirectStandardError (Join-Path $Logs 'ollama.err.log')
    Start-Sleep -Seconds 3
}
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'demo.out.log') -RedirectStandardError (Join-Path $Logs 'demo.err.log')
    Start-Sleep -Seconds 3
}

Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health' | ConvertTo-Json -Depth 5
Write-Output 'Open http://127.0.0.1:8000'

