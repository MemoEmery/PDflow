# PDflow (MVP)

Upload → conversão real no backend → PDF → download.

## Design
Interface baseada no style reference Dimension (tema escuro): fundo `#0a0a0a`, painéis de vidro fosco (`rgba(212,212,212,.1)`), botões em pílula (branca para a ação principal, fantasma com filete `#e5e5e5`), navegação flutuante, gradiente âmbar→cobalto apenas no hero e lavagem violeta só como divisor. Fontes: DM Sans (texto e título principal, peso 500) e Geist (títulos de seção), empacotadas via `@fontsource`. Os tokens estão no topo de `frontend/src/styles.css`. A versão clara anterior (Coda + Dropbox) foi guardada em `frontend/src/styles.coda-dropbox.css`; para voltar, copie-a por cima de `styles.css` e restaure as fontes em `main.tsx`.

## Deploy
Veja `DEPLOY.md` (site na Vercel + servidor em contêiner; o servidor não roda em funções da Vercel).

## Estrutura
`backend/` FastAPI + serviços (`services/converters.py`, `services/pdf_tools.py`); `frontend/` React + TypeScript + Vite (registro de ferramentas em `src/tools.ts`).

## Rodar
    docker compose up --build
O Dockerfile compila o frontend e o serve pelo FastAPI. Abra http://localhost:8000 (API/Swagger: http://localhost:8000/docs)

## Desenvolvimento local
Backend: `cd backend && pip install -r requirements.txt && uvicorn main:app --reload` (precisa de LibreOffice).
Frontend: `cd frontend && npm install && npm run dev` (proxy de /api para :8000).

## Local sem Docker (legado)
Instale LibreOffice e `pip install -r backend/requirements.txt`, depois `cd backend && uvicorn main:app --reload`.

## Conversões do MVP
Word/Excel/PowerPoint/ODF/CSV (LibreOffice headless), JPG/PNG/WEBP (Pillow, várias imagens → um PDF), TXT (ReportLab), HTML (WeasyPrint, sem acesso a recursos externos).

## Fase 2 incluída
Juntar, dividir (ZIP), compactar, PDF→Word (pdf2docx), PDF→Excel (tabelas via PyMuPDF), PDF→PowerPoint (páginas como imagens), PDF→TXT e PDF→JPG/PNG (ZIP, 150 dpi). Limite de 200 páginas; PDFs com senha são recusados.

## Fase 3 (parcial)
Girar, marca d'água, numerar páginas, proteger (AES-256) e desbloquear. As opções (texto, senha, ângulo) vão no campo `options` (JSON) de `POST /api/convert`.

## Páginas e imagens
Extrair, remover e reordenar páginas (campo `pages`, ex.: `1-3,5,8-`) e opções de Imagem→PDF (tamanho, orientação, margem).

## Testes
- Backend: `cd backend && pip install pytest httpx && pytest -q`
- Interface (13 testes, exigem a API rodando em localhost:8000 e um PDF de exemplo em /tmp/fx.pdf): `cd frontend && npm install && npm test`

## Separar PDF com IA (em construção, por fases)
Módulo `backend/pdf_splitter/`, desacoplado das demais ferramentas.
- **Fase 1 (pronta):** extração de texto, detecção de páginas escaneadas, interface de OCR (Tesseract), motor de regras e interpretação da instrução em parâmetros validados (`text.py`, `rules.py`, `parser.py`, `llm.py`).
- **Fase 2:** detecção dos limites, camadas de validação cruzada, score de confiança, validação dos critérios e simulação.
- **Fase 3:** API, separação real, validação pós-separação (hash de páginas), integridade, autocorreção e relatório.
- **Fase 4:** interface (upload, instrução, prévia editável, revisão humana, relatório, downloads).
- **Fase 5:** Tesseract no Docker, teste de ponta a ponta e documentação.

## Fila
Com `REDIS_URL` definido, a API enfileira no Redis (RQ) e o container `worker` processa; sem ele, roda em thread (dev local). Timeout de 180 s por tarefa. Não há contas: o uso é anônimo e os resultados são apagados em 30 min (ajuste `TTL` em `main.py` e o texto de privacidade juntos).

## Segurança implementada
Whitelist de extensão + verificação de MIME para imagens, limite de 25 MB e 20 arquivos, nomes sanitizados, pasta isolada por job (UUID), originais apagados após o processamento, PDFs apagados em 30 min, rate limit (20/min por IP), timeout de 90 s no LibreOffice, container sem root, erros genéricos ao usuário.

## Ainda não implementado
assinatura, OCR, PDF→Excel/PowerPoint, planos/preços. Antes de produção: storage S3 compartilhado se a API e os workers ficarem em máquinas diferentes, antivírus nos uploads.

## IA no "Separar PDF com IA" (opcional)
Sem chave, o separador usa só regras. Para ativar a IA, defina **uma** das chaves (o servidor, não o usuário, decide):
- `ANTHROPIC_API_KEY` (Claude, modelo padrão `claude-haiku-4-5-20251001`)
- `GEMINI_API_KEY` ou `GOOGLE_API_KEY` (Google AI Studio, modelo padrão `gemini-2.5-flash`)

Com as duas definidas, `SPLIT_AI_PROVIDER=anthropic|google` escolhe; `SPLIT_AI_MODEL` troca o modelo. Confira nomes de modelos e preços na tabela atual do provedor.
Medir acerto e custo: `cd backend && python -m evals.run_eval` (veja o cabeçalho do arquivo).
**Privacidade:** com a IA ativa, trechos curtos do texto de algumas páginas saem do servidor. Em planos gratuitos, alguns provedores podem usar o conteúdo enviado para melhorar produtos; para documentos reais, confira os termos e prefira plano pago.
