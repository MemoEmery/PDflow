# Deploy: site na Vercel + servidor num serviço de contêiner

A Vercel hospeda só o **site** (frontend). O **servidor** (FastAPI com LibreOffice, Tesseract e fila) precisa de um serviço que rode Docker,
porque as funções da Vercel limitam o corpo da requisição a 4,5 MB, não instalam o LibreOffice/Tesseract e não mantêm arquivos entre requisições.

## 1. Servidor (Render, Railway ou Fly.io)
1. Suba o repositório no Git (a raiz é a pasta `pdflow`).
2. No serviço escolhido, crie um **Web Service a partir do Dockerfile** na raiz do repositório.
3. Variáveis de ambiente:
   - `ALLOWED_ORIGINS` = endereço do site na Vercel, ex.: `https://pdflow.vercel.app` (vários, separados por vírgula)
   - (opcional) `GEMINI_API_KEY` ou `ANTHROPIC_API_KEY` para ativar a IA do "Separar PDF com IA"
4. Rode **uma única instância**: sem Redis, o estado das tarefas fica na memória do processo.
   Para várias instâncias, crie um Redis e defina `REDIS_URL` (e um serviço "worker" com o comando `rq worker --url $REDIS_URL`).
5. Verifique: `https://SEU-SERVIDOR/api/health` deve responder `{"status":"ok"}`.
6. Atenção a memória: o LibreOffice é pesado; se as conversões Office falharem, aumente a RAM do plano. Planos gratuitos podem "dormir" por inatividade.

## 2. Site (Vercel)
1. Em Vercel > Add New > Project, importe o mesmo repositório.
2. **Root Directory:** `frontend`. O `vercel.json` já define o build e o redirecionamento das rotas.
3. Em Settings > Environment Variables: `VITE_API_URL` = endereço do servidor (ex.: `https://pdflow-api.onrender.com`), sem barra no final.
4. Faça o deploy. Cada `git push` publica de novo. Se mudar `VITE_API_URL`, é preciso redeploy (o valor entra no build).

## 3. Antes de abrir ao público
- Teste com PDFs sem dados sensíveis. Proteja o acesso (senha/limite de IP) enquanto valida.
- Defina HTTPS (os dois serviços já entregam) e confira o limite de upload do provedor do servidor.
- Os PDFs ficam no servidor por até 30 min; revise o texto de privacidade (LGPD) antes de usar com dados de clientes.
- O limite de 20 conversões/min usa o IP real (`X-Forwarded-For`); confira que o provedor repassa esse cabeçalho.
