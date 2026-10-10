#!/usr/bin/env bash
# Roda o teste de acerto da IA (Gemini) no Linux/Mac. Uso: bash backend/evals/rodar_teste_ia.sh
set -e
cd "$(dirname "$0")/.."
[ -d .venv-eval ] || python3 -m venv .venv-eval
.venv-eval/bin/python -m pip install -q -r requirements.txt
read -r -s -p "Cole a chave do Google AI Studio (não aparece na tela): " GEMINI_API_KEY; echo
export GEMINI_API_KEY SPLIT_AI_PROVIDER=google
# Opcional: export EVAL_PRICE_IN=0.30 EVAL_PRICE_OUT=2.50   (exemplo; confira a tabela de preços do Google)
.venv-eval/bin/python -m evals.run_eval 2>&1 | tee evals/saida_teste_ia.txt
unset GEMINI_API_KEY
echo; echo "Pronto. Envie o conteúdo de backend/evals/saida_teste_ia.txt e depois APAGUE a chave no AI Studio."
