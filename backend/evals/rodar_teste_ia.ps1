# Roda o teste de acerto da IA (Gemini) no Windows. Uso, na pasta do projeto:
#   powershell -ExecutionPolicy Bypass -File backend\evals\rodar_teste_ia.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)          # pasta backend
if (-not (Test-Path .venv-eval)) { python -m venv .venv-eval }
& .\.venv-eval\Scripts\python -m pip install -q -r requirements.txt
$k = Read-Host "Cole a chave do Google AI Studio (nao aparece na tela)" -AsSecureString
$env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k))
$env:SPLIT_AI_PROVIDER = "google"
# Opcional: informe os precos atuais (US$ por milhao de tokens) para calcular o custo:
#   $env:EVAL_PRICE_IN = "0.30"; $env:EVAL_PRICE_OUT = "2.50"   <- exemplo, confira na tabela do Google
& .\.venv-eval\Scripts\python -m evals.run_eval 2>&1 | Tee-Object -FilePath evals\saida_teste_ia.txt
Remove-Item Env:GEMINI_API_KEY
Write-Host "`nPronto. Envie o conteudo de backend\evals\saida_teste_ia.txt e depois APAGUE a chave no AI Studio."
