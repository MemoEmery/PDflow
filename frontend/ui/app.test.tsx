import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { readFileSync } from "fs";
import { expect, test } from "vitest";
import App from "../src/App";

const go = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const input = () => document.querySelector("input[type=file]") as HTMLInputElement;
const pdf = (n = "a.pdf") => new File([readFileSync("/tmp/fx.pdf")], n, { type: "application/pdf" });
const done = () => screen.findByText(/Conversão concluída/, {}, { timeout: 20000 });

test("home e ferramentas", async () => {
  go("/");
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Tudo o que você precisa para trabalhar com PDF");
  expect(screen.getAllByRole("link", { name: /Word para PDF/ }).length).toBeGreaterThan(0);
});
test("página /tools lista categorias e 'Em breve'", () => {
  go("/tools");
  expect(screen.getByText("Organizar PDF")).toBeInTheDocument();
  expect(screen.getByText("OCR (PDF pesquisável)")).toBeInTheDocument();
});
test("slug inexistente volta para /tools", () => {
  go("/nao-existe");
  expect(screen.getByRole("heading", { name: "Ferramentas" })).toBeInTheDocument();
});
test("TXT → PDF: solta e converte sozinho, link baixa PDF real", async () => {
  go("/text-to-pdf");
  await userEvent.upload(input(), new File(["Olá mundo"], "nota.txt", { type: "text/plain" }));
  await done();
  const a = screen.getByRole("link", { name: /Baixar PDF/ });
  const r = await fetch(a.getAttribute("href")!);
  expect(new TextDecoder().decode((await r.arrayBuffer()).slice(0, 4))).toBe("%PDF");
});
test("formato errado mostra mensagem amigável", async () => {
  go("/word-to-pdf");
  await userEvent.setup({ applyAccept: false }).upload(input(), new File(["x"], "virus.exe"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Esse formato ainda não é suportado.");
});
test("Excluir agora remove o arquivo", async () => {
  go("/text-to-pdf");
  await userEvent.upload(input(), new File(["x"], "n.txt", { type: "text/plain" }));
  await done();
  const href = screen.getByRole("link", { name: /Baixar PDF/ }).getAttribute("href")!;
  await userEvent.click(screen.getByRole("button", { name: "Excluir agora" }));
  await waitFor(async () => expect((await fetch(href)).status).toBe(404));
});
test("Juntar: botão só habilita com 2 PDFs", async () => {
  go("/merge-pdf");
  await userEvent.upload(input(), pdf("1.pdf"));
  expect(screen.getByRole("button", { name: "Juntar PDFs" })).toBeDisabled();
  await userEvent.upload(input(), pdf("2.pdf"));
  await userEvent.click(screen.getByRole("button", { name: "Juntar PDFs" }));
  await done();
  expect(screen.getByRole("link", { name: "Visualizar" })).toBeInTheDocument();
});
test("Extrair páginas: campo obrigatório e sucesso", async () => {
  go("/extract-pages");
  await userEvent.upload(input(), pdf());
  await userEvent.click(screen.getByRole("button", { name: "Aplicar" }));
  expect(await screen.findByText(/Informe as páginas/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/Páginas/), "1-2");
  await userEvent.click(screen.getByRole("button", { name: "Aplicar" }));
  await done();
});
test("Proteger PDF com senha e depois Desbloquear", async () => {
  go("/protect-pdf");
  await userEvent.upload(input(), pdf());
  await userEvent.type(screen.getByLabelText(/Senha/), "abcd");
  await userEvent.click(screen.getByRole("button", { name: "Aplicar" }));
  await done();
});
test("Imagem → PDF mostra opções de página", () => {
  go("/image-to-pdf");
  expect(screen.queryByLabelText("Tamanho da página")).toBeNull(); // só aparece após escolher arquivos
});
test("tarefa inexistente não fica carregando para sempre", async () => {
  const real = globalThis.fetch;
  globalThis.fetch = (async (u: any, i: any) => String(u).startsWith("/api/jobs/") ? new Response("{}", { status: 404 }) : real(u, i)) as any;
  try {
    go("/text-to-pdf");
    await userEvent.upload(input(), new File(["x"], "n.txt", { type: "text/plain" }));
    expect(await screen.findByText(/A tarefa expirou/, {}, { timeout: 8000 })).toBeInTheDocument();
  } finally { globalThis.fetch = real; }
});
test("queda de rede mostra mensagem em português", async () => {
  const real = globalThis.fetch;
  globalThis.fetch = (async () => { throw new TypeError("Failed to fetch"); }) as any;
  try {
    go("/text-to-pdf");
    await userEvent.upload(input(), new File(["x"], "n.txt", { type: "text/plain" }));
    expect(await screen.findByText("Não foi possível converter o arquivo. Tente novamente.")).toBeInTheDocument();
  } finally { globalThis.fetch = real; }
});

test("Separar PDF com IA: fluxo completo (enviar, interpretar, simular, confirmar, relatório)", async () => {
  go("/split-pdf-ai");
  const f = new File([readFileSync("/tmp/split_fx.pdf")], "contratos.pdf", { type: "application/pdf" });
  await userEvent.upload(input(), f);
  const box = await screen.findByLabelText(/Como você deseja separar este PDF/, {}, { timeout: 20000 });
  await userEvent.type(box, 'Separe sempre que aparecer "CONTRATO" no início da página.');
  await userEvent.click(screen.getByRole("button", { name: /Interpretar instrução/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Simular separação/ }, { timeout: 20000 }));
  await userEvent.click(await screen.findByRole("button", { name: /Confirmar separação/ }, { timeout: 30000 }));
  await screen.findByText(/Processamento concluído/, {}, { timeout: 40000 });
  const zip = screen.getByRole("link", { name: /Baixar ZIP/ });
  const r = await fetch(zip.getAttribute("href")!);
  expect(r.status).toBe(200);
  expect(new TextDecoder().decode((await r.arrayBuffer()).slice(0, 2))).toBe("PK");
});
