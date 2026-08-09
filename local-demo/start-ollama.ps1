$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AiRuntime = if ($env:AI_RUNTIME_DIR) { $env:AI_RUNTIME_DIR } else { 'C:\AI' }
$Ollama = Join-Path $AiRuntime 'ollama\ollama.exe'
$env:OLLAMA_MODELS = Join-Path $AiRuntime 'models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_KEEP_ALIVE = '2m'
$env:CUDA_VISIBLE_DEVICES = '-1'
$env:GGML_VK_VISIBLE_DEVICES = '-1'
$env:OLLAMA_LLM_LIBRARY = 'cpu'
& $Ollama serve
