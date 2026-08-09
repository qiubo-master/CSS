$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AiRuntime = if ($env:AI_RUNTIME_DIR) { $env:AI_RUNTIME_DIR } else { 'C:\AI' }
$Ollama = Join-Path $AiRuntime 'ollama\ollama.exe'
$Models = Join-Path $AiRuntime 'models'

if (-not (Test-Path $Ollama)) {
    throw "Ollama is not installed at $Ollama"
}

$env:OLLAMA_MODELS = $Models
$env:OLLAMA_HOST = '127.0.0.1:11434'

$server = Start-Process -FilePath $Ollama -ArgumentList 'serve' -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3
try {
    & $Ollama pull 'qwen3:1.7b-q4_K_M'
    & $Ollama pull 'qwen3-embedding:0.6b'
    & $Ollama list
} finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
}
