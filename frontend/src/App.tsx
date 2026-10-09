import { useMemo, useState, DragEvent } from "react";
import { Link, NavLink, Navigate, Route, Routes, useParams } from "react-router-dom";
import SplitAI from "./SplitAI";
import { FROM_PDF, ORGANIZE, POPULAR, SOON, TOOLS, Tool } from "./tools";

const fmt = (b: number) => (b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.ceil(b / 1024) + " KB");
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const GENERIC = "Não foi possível converter o arquivo. Tente novamente.";
class AppErr extends Error {} // só mensagens nossas chegam à tela; o resto vira GENERIC

const badge = (t: Tool) => (t.cat === "Converter para PDF" ? t.accept[0].slice(1).toUpperCase() : "PDF");

function Card({ t }: { t: Tool }) {
  return (<Link to={"/" + t.slug} className="card"><span className="tile" aria-hidden="true">{badge(t)}</span>
    <div><strong>{t.title}</strong><small>{t.desc}</small><span className="go">Abrir →</span></div></Link>);
}

function Home() {
  return (<>
    <div className="band"><section className="hero">
      <div>
        <Link className="notice" to="/word-to-pdf">✦ Sem cadastro: é só enviar o arquivo →</Link>
        <h1>Tudo o que você precisa para trabalhar com PDF</h1>
        <p className="sub">Converta arquivos para PDF, ou transforme PDFs em Word, Excel, PowerPoint e imagens, direto pelo navegador.</p>
        <ul className="bul"><li>Word, Excel, PowerPoint e imagens para PDF</li><li>Juntar, dividir e compactar PDFs</li><li>PDF para Word, Excel, PowerPoint e JPG</li><li>Arquivos apagados em até 30 minutos</li></ul>
        <Link className="btn" to="/word-to-pdf">Começar agora →</Link>
        <Link className="btn ghost" to="/tools">Ver todas as ferramentas</Link>
      </div>
      <div className="mock" aria-hidden="true">
        <div className="mock-row"><span className="tile">DOCX</span><div><b>relatorio-anual.docx</b><small>2,4 MB · Convertendo…</small></div></div>
        <div className="mock-bar"><i /></div><hr />
        <div className="mock-row"><span className="tile">PDF</span><div><b>relatorio-anual.pdf</b><small>Conversão concluída</small></div><span className="mock-btn">Baixar PDF</span></div><hr />
        <div className="mock-row"><span className="tile">XLSX</span><div><b>vendas-2026.xlsx</b><small>Na fila…</small></div></div>
      </div>
    </section></div>
    <main>
      <h2>Converter para PDF</h2>
      <div className="grid">{POPULAR.map((s) => <Card key={s} t={TOOLS.find((x) => x.slug === s)!} />)}</div>
      <h2>Organizar PDF</h2>
      <div className="grid">{ORGANIZE.map((s) => <Card key={s} t={TOOLS.find((x) => x.slug === s)!} />)}</div>
      <h2>Converter de PDF para outros formatos</h2>
      <div className="grid">{FROM_PDF.map((s) => <Card key={s} t={TOOLS.find((x) => x.slug === s)!} />)}</div>
      <section className="glass"><h2>Como funciona</h2>
        <ol className="how"><li><span><b>Envie</b>Arraste seu arquivo ou selecione no computador.</span></li><li><span><b>Escolha</b>Use a ferramenta que você precisa.</span></li><li><span><b>Aguarde</b>Acompanhe o processamento em tempo real.</span></li><li><span><b>Baixe</b>Visualize ou baixe o resultado.</span></li></ol></section>
      <section className="cta"><h2>Pronto para começar?</h2><p className="sub">Sem cadastro: é só enviar o arquivo.</p><Link className="btn" to="/tools">Explorar ferramentas →</Link></section>
      <Privacy />
    </main>
  </>);
}

function Tools() {
  const cats = [...new Set(TOOLS.map((t) => t.cat))];
  return (<main>
    <h1>Ferramentas</h1>
    {cats.map((c) => (<section key={c}><h2>{c}</h2><div className="grid">{TOOLS.filter((t) => t.cat === c).map((t) => <Card key={t.slug} t={t} />)}</div></section>))}
    <h2>Em breve</h2>
    <div className="grid">{SOON.map((s) => <div key={s} className="card soon"><span className="tile" aria-hidden="true">···</span><div><strong>{s}</strong><small>Em breve</small></div></div>)}</div>
  </main>);
}

function Privacy() {
  return <p className="priv"><strong>Seus arquivos são processados com segurança.</strong> Eles são enviados ao nosso servidor apenas para o processamento. Os originais são apagados assim que ele termina. O resultado é apagado em até 30 minutos, e você pode excluí-lo antes pelo botão “Excluir agora”. Em “Separar PDF com IA”, o PDF fica guardado pelo mesmo prazo para você revisar e baixar. Se a análise por IA estiver ativada neste servidor (a página avisa), trechos curtos do texto de algumas páginas, de até 40 por análise, são enviados ao provedor de IA para identificar inícios de documentos. Sem a IA ativada, nada é enviado a terceiros. Não usamos seus arquivos para treinar modelos.</p>;
}

type St = { s: "idle" | "busy" | "done" | "fail"; msg?: string; id?: string };

function Converter({ t }: { t: Tool }) {
  const [files, setFiles] = useState<File[]>([]);
  const [st, setSt] = useState<St>({ s: "idle" });
  const [over, setOver] = useState(false);
  const [note, setNote] = useState("");
  const urls = useMemo(() => files.map((f) => (f.type.startsWith("image/") ? URL.createObjectURL(f) : "")), [files]);
  const [opts, setOpts] = useState<Record<string, string>>(Object.fromEntries(t.fields.map((f) => [f.key, f.def])));
  const minFiles = t.tool === "merge-pdf" ? 2 : 1;

  async function run(list: File[]) {
    setSt({ s: "busy", msg: "Enviando…" });
    try {
      const fd = new FormData(); fd.append("tool", t.tool); fd.append("options", JSON.stringify(opts)); list.forEach((f) => fd.append("files", f));
      const r = await fetch("/api/convert", { method: "POST", body: fd });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new AppErr(typeof j.detail === "string" ? j.detail : GENERIC);
      for (;;) {
        const pr = await fetch("/api/jobs/" + j.job_id);
        if (!pr.ok) throw new AppErr("A tarefa expirou. Envie o arquivo novamente.");
        const p = await pr.json();
        if (p.status === "completed") { setSt({ s: "done", id: j.job_id, msg: p.filename }); return; }
        if (p.status === "failed") throw new AppErr(typeof p.error === "string" ? p.error : GENERIC);
        setSt({ s: "busy", msg: p.status === "pending" ? "Na fila…" : "Convertendo…" });
        await sleep(1000);
      }
    } catch (e) { setSt({ s: "fail", msg: e instanceof AppErr ? e.message : GENERIC }); }
  }

  function add(fl: File[]) {
    const ok = fl.filter((f) => t.accept.includes("." + (f.name.split(".").pop() || "").toLowerCase()));
    setNote(ok.length < fl.length ? "Esse formato ainda não é suportado." : "");
    if (!ok.length) return;
    const next = t.multi ? [...files, ...ok] : ok.slice(0, 1);
    setFiles(next); setSt({ s: "idle" });
    if (!t.multi && !t.fields.length) run(next); // um arquivo: converte sem clique extra
  }
  const move = (i: number, d: number) => { const j = i + d; if (j < 0 || j >= files.length) return; const n = [...files]; [n[i], n[j]] = [n[j], n[i]]; setFiles(n); };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); add([...e.dataTransfer.files]); };
  const del = async () => { await fetch("/api/files/" + st.id, { method: "DELETE" }); setSt({ s: "idle" }); setFiles([]); };
  const busy = st.s === "busy";

  return (<main className="narrow">
    <h1>{t.title}</h1><p className="sub">{t.desc}</p>
    <label className={"drop" + (over ? " over" : "")} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop} onPaste={(e) => add([...e.clipboardData.files])}>
      <strong>Arraste {t.multi ? "seus arquivos" : "seu arquivo"} aqui</strong>
      <span className="btn">Selecionar {t.multi ? "arquivos" : "arquivo"}</span>
      <small>Formatos aceitos: {t.accept.join(" ")} · até 25 MB por arquivo</small>
      <input type="file" multiple={t.multi} accept={t.accept.join(",")} disabled={busy} onChange={(e) => { add([...(e.target.files || [])]); e.target.value = ""; }} />
    </label>
    {note && <p className="err" role="alert">{note}</p>}
    <ul className="files">{files.map((f, i) => (<li key={f.name + i}>
      {urls[i] && <img src={urls[i]} alt="" />}
      <div className="n">{f.name}<div className="m">{(f.name.split(".").pop() || "").toUpperCase()} · {fmt(f.size)}</div></div>
      {t.multi && !busy && <><button aria-label="Mover para cima" onClick={() => move(i, -1)}>↑</button><button aria-label="Mover para baixo" onClick={() => move(i, 1)}>↓</button></>}
      {!busy && <button className="rm" aria-label={"Remover " + f.name} onClick={() => setFiles(files.filter((_, k) => k !== i))}>✕</button>}
    </li>))}</ul>
    {files.length > 0 && st.s !== "done" && t.fields.map((f) => (<label key={f.key} className="fld">{f.label}
      {f.type === "select"
        ? <select value={opts[f.key]} onChange={(e) => setOpts({ ...opts, [f.key]: e.target.value })}>{f.options!.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        : <input type={f.type} value={opts[f.key]} maxLength={f.type === "password" ? 128 : 200} autoComplete="off" onChange={(e) => setOpts({ ...opts, [f.key]: e.target.value })} />}
    </label>))}
    {(t.multi || t.fields.length > 0) && files.length > 0 && st.s !== "done" && <button className="btn" disabled={busy || files.length < minFiles} onClick={() => run(files)}>{t.tool === "merge-pdf" ? "Juntar PDFs" : t.tool === "to-pdf" ? "Converter para PDF" : "Aplicar"}</button>}
    {t.multi && files.length === 1 && minFiles > 1 && <p className="m">Adicione pelo menos mais um arquivo.</p>}
    {st.s !== "idle" && (<section className="panel" aria-live="polite">
      {busy && <><strong>{st.msg}</strong><div className="bar"><i /></div></>}
      {st.s === "fail" && <span className="err">{st.msg}</span>}
      {st.s === "done" && <><div className="ok">✓ Conversão concluída</div><p>{st.msg}</p>
        {st.msg?.endsWith(".pdf") && <a className="btn ghost" target="_blank" rel="noopener" href={`/api/files/${st.id}?download=false`}>Visualizar</a>}
        <a className="btn" href={"/api/files/" + st.id}>Baixar {st.msg?.split(".").pop()?.toUpperCase()}</a>
        <button className="btn ghost" onClick={del}>Excluir agora</button></>}
    </section>)}
    <Privacy />
  </main>);
}

function ToolPage() {
  const { slug } = useParams();
  const t = TOOLS.find((x) => x.slug === slug);
  if (t?.tool === "split-ai") return <SplitAI />;
  return t ? <Converter key={t.slug} t={t} /> : <Navigate to="/tools" replace />;
}

export default function App() {
  return (<>
    <header><Link to="/" className="logo"><i aria-hidden="true" />PDflow</Link>
      <nav><NavLink to="/tools" className="btn ghost sm">Ferramentas</NavLink><Link to="/word-to-pdf" className="btn sm">Começar</Link></nav></header>
    <Routes><Route path="/" element={<Home />} /><Route path="/tools" element={<Tools />} /><Route path="/:slug" element={<ToolPage />} /></Routes>
    <footer>© PDflow · Seus arquivos são processados com segurança</footer>
  </>);
}
