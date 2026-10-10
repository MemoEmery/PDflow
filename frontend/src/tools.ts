// Registro de ferramentas: para adicionar uma nova, basta incluir uma linha aqui
// (e o handler correspondente no backend).
export type Field = { key: string; label: string; type: "text" | "password" | "select"; def: string; options?: [string, string][] };
export type Tool = { slug: string; title: string; desc: string; tool: string; accept: string[]; multi: boolean; cat: string; icon: string; fields: Field[] };
const t = (slug: string, title: string, desc: string, tool: string, accept: string[], cat: string, icon: string, multi = false, fields: Field[] = []): Tool =>
  ({ slug, title, desc, tool, accept, multi, cat, icon, fields });
const IMG = [".jpg", ".jpeg", ".png", ".webp"];
export const TOOLS: Tool[] = [
  t("word-to-pdf", "Word para PDF", "Converta seus documentos Word para PDF gratuitamente.", "to-pdf", [".doc", ".docx", ".odt"], "Converter para PDF", "📄"),
  t("excel-to-pdf", "Excel para PDF", "Transforme planilhas em PDF mantendo o layout.", "to-pdf", [".xls", ".xlsx", ".ods", ".csv"], "Converter para PDF", "📊"),
  t("powerpoint-to-pdf", "PowerPoint para PDF", "Converta apresentações em PDF.", "to-pdf", [".ppt", ".pptx", ".odp"], "Converter para PDF", "📽️"),
  t("image-to-pdf", "Imagem para PDF", "Junte JPG, PNG e WEBP em um único PDF. Reordene antes de converter.", "to-pdf", IMG, "Converter para PDF", "🖼️", true, [
    { key: "size", label: "Tamanho da página", type: "select", def: "fit", options: [["fit", "Ajustar à imagem"], ["A4", "A4"], ["Letter", "Carta (Letter)"]] },
    { key: "orientation", label: "Orientação (A4/Carta)", type: "select", def: "auto", options: [["auto", "Automática"], ["portrait", "Retrato"], ["landscape", "Paisagem"]] },
    { key: "margin", label: "Margem", type: "select", def: "none", options: [["none", "Sem margem"], ["small", "Pequena"], ["medium", "Média"]] }]),
  t("text-to-pdf", "Texto para PDF", "Converta arquivos TXT em PDF.", "to-pdf", [".txt"], "Converter para PDF", "📑"),
  t("html-to-pdf", "HTML para PDF", "Converta arquivos HTML em PDF.", "to-pdf", [".html", ".htm"], "Converter para PDF", "🌐"),
  t("merge-pdf", "Juntar PDF", "Junte vários PDFs em um só. Use as setas para definir a ordem.", "merge-pdf", [".pdf"], "Organizar PDF", "🧩", true),
  t("extract-pages", "Extrair páginas", "Crie um novo PDF só com as páginas escolhidas.", "extract-pages", [".pdf"], "Organizar PDF", "📤", false,
    [{ key: "pages", label: "Páginas (ex.: 1-3,5,8-)", type: "text", def: "" }]),
  t("remove-pages", "Remover páginas", "Apague páginas do PDF.", "remove-pages", [".pdf"], "Organizar PDF", "🗑️", false,
    [{ key: "pages", label: "Páginas a remover (ex.: 2,4-6)", type: "text", def: "" }]),
  t("reorder-pages", "Reordenar páginas", "Defina a nova ordem. Páginas não citadas vão para o final.", "reorder-pages", [".pdf"], "Organizar PDF", "↕️", false,
    [{ key: "pages", label: "Nova ordem (ex.: 3,1,2)", type: "text", def: "" }]),
  t("split-pdf-ai", "Separar PDF com IA", "Separe um PDF com vários documentos pelo conteúdo, com prévia, validação e prova de integridade.", "split-ai", [".pdf"], "Organizar PDF", "🧠"),
  t("split-pdf", "Dividir PDF", "Separe cada página em um PDF individual (arquivo ZIP).", "split-pdf", [".pdf"], "Organizar PDF", "✂️"),
  t("compress-pdf", "Compactar PDF", "Reduza o tamanho do PDF.", "compress-pdf", [".pdf"], "Organizar PDF", "🗜️"),
  t("pdf-to-word", "PDF para Word", "Converta PDF em documento Word editável.", "pdf-to-word", [".pdf"], "Converter de PDF", "📝"),
  t("pdf-to-excel", "PDF para Excel", "Extraia tabelas do PDF para uma planilha. Sem tabelas, cada linha de texto vira uma linha.", "pdf-to-excel", [".pdf"], "Converter de PDF", "📊"),
  t("pdf-to-pptx", "PDF para PowerPoint", "Cada página vira um slide (como imagem, não editável).", "pdf-to-pptx", [".pdf"], "Converter de PDF", "📽️"),
  t("pdf-to-txt", "PDF para TXT", "Extraia o texto do PDF.", "pdf-to-txt", [".pdf"], "Converter de PDF", "📃"),
  t("pdf-to-jpg", "PDF para JPG", "Uma imagem JPG por página (arquivo ZIP).", "pdf-to-jpg", [".pdf"], "Converter de PDF", "🖼️"),
  t("pdf-to-png", "PDF para PNG", "Uma imagem PNG por página (arquivo ZIP).", "pdf-to-png", [".pdf"], "Converter de PDF", "🖼️"),
  t("rotate-pdf", "Girar PDF", "Gire todas as páginas do PDF.", "rotate-pdf", [".pdf"], "Editar PDF", "🔄", false,
    [{ key: "angle", label: "Rotação", type: "select", def: "90", options: [["90", "90° horário"], ["180", "180°"], ["270", "90° anti-horário"]] }]),
  t("watermark-pdf", "Adicionar marca d'água", "Escreva um texto na diagonal em todas as páginas.", "watermark-pdf", [".pdf"], "Editar PDF", "💧", false,
    [{ key: "text", label: "Texto da marca d'água", type: "text", def: "CONFIDENCIAL" }]),
  t("page-numbers-pdf", "Numerar páginas", "Adicione o número da página no rodapé.", "page-numbers-pdf", [".pdf"], "Editar PDF", "🔢", false,
    [{ key: "format", label: "Formato", type: "select", def: "n", options: [["n", "1, 2, 3…"], ["n/N", "1 / 10, 2 / 10…"]] }]),
  t("protect-pdf", "Proteger PDF", "Defina uma senha para abrir o PDF (criptografia AES-256).", "protect-pdf", [".pdf"], "Editar PDF", "🔒", false,
    [{ key: "password", label: "Senha (mín. 4 caracteres)", type: "password", def: "" }]),
  t("unlock-pdf", "Desbloquear PDF", "Remova a senha de um PDF que você tem permissão para abrir.", "unlock-pdf", [".pdf"], "Editar PDF", "🔓", false,
    [{ key: "password", label: "Senha atual do PDF", type: "password", def: "" }]),
];
export const SOON = ["Assinar PDF", "OCR (PDF pesquisável)"];
export const FROM_PDF = ["pdf-to-word", "pdf-to-excel", "pdf-to-pptx", "pdf-to-jpg"];
export const POPULAR = ["word-to-pdf", "excel-to-pdf", "powerpoint-to-pdf", "image-to-pdf", "text-to-pdf", "html-to-pdf"];
export const ORGANIZE = ["merge-pdf", "split-pdf-ai", "split-pdf", "compress-pdf"];
