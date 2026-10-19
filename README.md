# PDflow

Ferramentas online para trabalhar com PDF: converter, organizar e separar documentos direto pelo navegador, sem cadastro.

## O que ele faz

**Converter para PDF**
- Word, Excel, PowerPoint, ODT, ODS, ODP, CSV, TXT e HTML
- Imagens (JPG, PNG, WEBP), com várias imagens em um único PDF e opções de página (tamanho, orientação, margem)

**Organizar PDF**
- Juntar, dividir, compactar, extrair, remover e reordenar páginas
- Girar, numerar páginas, adicionar marca d'água, proteger e desbloquear com senha

**Converter de PDF**
- PDF para Word, Excel, PowerPoint, TXT, JPG e PNG

**Separar PDF com IA**
Divide um PDF que reúne vários documentos (por exemplo, contratos ou notas fiscais) em arquivos separados, a partir de uma instrução em linguagem natural.
- Mostra uma prévia da divisão antes de gerar qualquer arquivo, com o motivo e o nível de confiança de cada limite
- Permite revisar, unir e dividir manualmente
- Confere o resultado depois de gerar e apresenta um relatório
- A IA é **opcional**: sem ela, o separador funciona só com regras

## Privacidade

- O uso não exige cadastro nem conta.
- Os arquivos são processados no servidor e guardados apenas pelo tempo necessário. Resultados e originais são apagados automaticamente em pouco tempo, e o usuário pode excluí-los antes.
- Os arquivos não são usados para treinar modelos.
- Com a IA ativada pelo administrador do servidor, trechos curtos do texto de algumas páginas podem ser enviados ao provedor de IA configurado. Sem a IA ativada, nada é enviado a terceiros.

Antes de usar com dados pessoais ou sensíveis, o responsável pela instalação deve revisar essas regras e a legislação aplicável (por exemplo, a LGPD).

## Tecnologias

- **Interface:** React, TypeScript e Vite
- **Servidor:** Python e FastAPI
- **Processamento:** PyMuPDF, LibreOffice, Pillow, ReportLab, WeasyPrint e Tesseract (OCR)

## Como rodar localmente

Com Docker:

```bash
docker compose up --build
```

Abra `http://localhost:8000`. A documentação da API fica em `/docs`.

Para desenvolvimento, em dois terminais:

```bash
# servidor (precisa do LibreOffice instalado para as conversões de Office)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# interface
cd frontend
npm install
npm run dev
```

## Testes

```bash
# servidor
cd backend && pip install pytest && pytest -q

# interface (com o servidor rodando em localhost:8000)
cd frontend && npm test
```

## Configuração

O projeto funciona sem nenhuma configuração. Opções avançadas são definidas por variáveis de ambiente no servidor:

- Origens permitidas, quando o site e o servidor ficam em endereços diferentes
- Chave de um provedor de IA, para ativar a IA no "Separar PDF com IA"
- URL de um Redis, para executar o processamento em vários processos

Nunca grave chaves ou senhas no repositório. Use as variáveis de ambiente do seu provedor de hospedagem.

## Publicação

Veja [DEPLOY.md](DEPLOY.md). O site pode ficar em uma plataforma de sites estáticos, mas o servidor precisa de um serviço que execute contêineres Docker.

## Estrutura

```text
backend/     servidor, ferramentas de PDF e módulo de separação
frontend/    interface web
Dockerfile   imagem do servidor (inclui a interface compilada)
```

## Limitações

- Este é um projeto em evolução. Revise a segurança e a privacidade antes de abri-lo ao público.
- Não há verificação de vírus nos arquivos enviados.
- O resultado das conversões depende da complexidade do documento original, principalmente em PDF para Word.

## Licença

A definir.
