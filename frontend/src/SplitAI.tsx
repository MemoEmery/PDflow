import { API } from "./api";
import { useEffect, useState, DragEvent } from "react";

const GENERIC = "Não foi possível processar o PDF. Tente novamente.";
async function call(url: string, init?: RequestInit): Promise<any> {
  let r: Response;
  try { r = await fetch(url, init); } catch { throw new Error("Perdemos a conexão. Tente novamente."); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : GENERIC);
  return j;
}
const post = (url: string, body: unknown) => call(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const mb = (b: number) => (b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.ceil(b / 1024) + " KB");
const pad = (n: number) => String(n).padStart(2, "0");

type Form = { strategy: string; kw: string; rx: string; loc: string; idt: string; label: string; idr: string; idloc: string; combine: string; doctype: string; minp: string; single: boolean; thr: string; tpl: string };
const EMPTY: Form = { strategy: "keyword", kw: "", rx: "", loc: "anywhere", idt: "none", label: "", idr: "", idloc: "anywhere", combine: "any", doctype: "", minp: "1", single: true, thr: "85", tpl: "{identifier}" };
const fromParams = (p: any): Form => ({ strategy: p.strategy, kw: (p.start_keywords || []).join("\n"), rx: (p.start_regexes || []).join("\n"), loc: p.keyword_location, idt: p.identifier?.type || "none",
  label: p.identifier?.label || "", idr: p.identifier?.regex || "", idloc: p.identifier?.location || "anywhere", combine: p.combine, doctype: p.document_type || "", minp: String(p.min_document_pages),
  single: p.allow_single_page_documents, thr: String(Math.round(p.confidence_threshold * 100)), tpl: p.name_template });
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const toParams = (f: Form) => ({ strategy: f.strategy, start_keywords: lines(f.kw), start_regexes: lines(f.rx), keyword_location: f.loc,
  identifier: { type: f.idt, label: f.label || null, regex: f.idr || null, location: f.idloc }, combine: f.combine, document_type: f.doctype || null,
  min_document_pages: Math.max(1, +f.minp || 1), allow_single_page_documents: f.single, confidence_threshold: Math.min(100, Math.max(50, +f.thr || 85)) / 100, name_template: f.tpl || "{identifier}" });

const LEVEL: Record<string, string> = { alta: "Alta", media: "Média", baixa: "Baixa ⚠", manual: "Manual" };
const STATUS: Record<string, string> = { completed: "✓ Processamento concluído", completed_with_warnings: "✓ Processamento concluído, com alertas para conferir", review_required: "⚠ Revisão necessária: a validação encontrou inconsistências" };
const Select = ({ v, set, opts }: { v: string; set: (v: string) => void; opts: [string, string][] }) => <select value={v} onChange={(e) => set(e.target.value)}>{opts.map(([a, b]) => <option key={a} value={a}>{b}</option>)}</select>;

export default function SplitAI() {
  const [sid, setSid] = useState<string | null>(null);
  const [st, setSt] = useState<any>(null);
  const [fileName, setFileName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [over, setOver] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [form, setForm] = useState<Form | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [plan, setPlan] = useState<any>(null);
  const [names, setNames] = useState<Record<number, string>>({});
  const [ack, setAck] = useState(false);
  const [poll, setPoll] = useState(0);
  const [back, setBack] = useState(false);

  useEffect(() => {
    if (!sid) return;
    let stop = false;
    const tick = async () => {
      try {
        const s = await call(`${API}/api/split/${sid}`); if (stop) return; setSt(s);
        if (s.status === "pending" || s.status === "processing") setTimeout(tick, 800);
      } catch (e) { if (!stop) setErr(e instanceof Error ? e.message : GENERIC); }
    };
    tick(); return () => { stop = true; };
  }, [sid, poll]);

  const guard = async (label: string, fn: () => Promise<void>) => {
    setErr(""); setBusy(label);
    try { await fn(); } catch (e) { setErr(e instanceof Error ? e.message : GENERIC); } finally { setBusy(""); }
  };
  const reset = () => { if (sid) fetch(`${API}/api/split/${sid}`, { method: "DELETE" }).catch(() => {}); setSid(null); setSt(null); setPlan(null); setForm(null); setNotes([]); setInstruction(""); setAck(false); setBack(false); setNames({}); setErr(""); };

  const upload = (f: File | undefined) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) { setErr("Envie um arquivo PDF."); return; }
    guard("Enviando…", async () => {
      const fd = new FormData(); fd.append("file", f);
      const j = await call(API + "/api/split", { method: "POST", body: fd }); setFileName(f.name); setSid(j.split_id);
    });
  };
  const interpret = () => guard("Interpretando…", async () => {
    const j = await post(`${API}/api/split/${sid}/interpret`, { instruction }); setForm(fromParams(j.params)); setNotes(j.notes); setPlan(null);
  });
  const simulate = () => guard("Simulando…", async () => { setNames({}); setPlan(await post(`${API}/api/split/${sid}/simulate`, toParams(form!))); setAck(false); });
  const toDocs = (starts: number[]) => {   // starts 0-based -> documentos contíguos
    const s = [...new Set([0, ...starts])].sort((a, b) => a - b), n = st.info.page_count;
    return s.map((a, k) => ({ start: a + 1, end: k + 1 < s.length ? s[k + 1] : n, name: names[a + 1] }));
  };
  const edit = (starts: number[]) => guard("Atualizando prévia…", async () => { setPlan(await post(`${API}/api/split/${sid}/plan`, { documents: toDocs(starts) })); setAck(false); });
  const starts0 = (plan?.documents || []).map((d: any) => d.start - 1);
  const execute = () => guard("Separando…", async () => {
    await post(`${API}/api/split/${sid}/execute`, { documents: plan.documents.map((d: any) => ({ start: d.start, end: d.end, name: names[d.start] ?? d.name })), acknowledge_review: ack });
    setBack(false); setPoll((x) => x + 1);
  });

  const ready = st?.status === "completed" && st?.stage === "ready";
  const done = st?.stage === "done" && !back;
  const info = st?.info;
  const needAck = plan?.needs_review;
  const blocked = !plan || !plan.integrity.ok || (needAck && !ack);

  return (<main className="narrow xl">
    <h1>Separar PDF com IA</h1>
    <p className="sub">Envie um PDF com vários documentos e explique como separá-los. Você vê a prévia, confere os alertas e só então os arquivos são gerados e validados.</p>
    {err && <p className="err" role="alert">{err}</p>}

    {!sid && (<label className={"drop" + (over ? " over" : "")} onDragOver={(e: DragEvent) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e: DragEvent) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]); }}>
      <strong>Arraste seu PDF aqui</strong><span className="btn">Selecionar PDF</span>
      <small>PDFs com texto, digitalizados ou mistos · até 100 MB e 500 páginas</small>
      <input type="file" accept=".pdf,application/pdf" disabled={!!busy} onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
    </label>)}
    {busy && <p aria-live="polite"><strong>{busy}</strong></p>}

    {sid && st?.status === "failed" && (<section className="panel"><span className="err">{st.error || GENERIC}</span><br /><button className="btn" onClick={reset}>Enviar outro PDF</button></section>)}
    {sid && st && ["pending", "processing"].includes(st.status) && (<section className="panel" aria-live="polite">
      <strong>{st.stage === "splitting" ? "Separando e validando os arquivos gerados…" : `Analisando o PDF… página ${st.progress?.done || 0} de ${st.progress?.total || "?"}`}</strong><div className="bar"><i /></div>
      <small>Extração de texto e OCR quando necessário. Nada é separado antes da sua confirmação.</small></section>)}

    {(ready || done || back) && info && (<section className="panel">
      <h3 className="h3">{fileName || "PDF enviado"}</h3>
      <div className="tiles">
        <div><b>{info.page_count}</b><small>páginas</small></div><div><b>{mb(info.size_bytes)}</b><small>tamanho</small></div>
        <div><b>{info.text_pages}</b><small>com texto</small></div><div><b>{info.scanned_pages}</b><small>escaneadas</small></div>
        <div><b>{info.ocr_pages}</b><small>com OCR aplicado</small></div>
      </div>
      {info.scanned_pages > info.ocr_pages && <p className="err">Há {info.scanned_pages - info.ocr_pages} página(s) escaneada(s) sem OCR{st.ocr?.available ? "" : " (OCR indisponível neste servidor)"}: elas não podem ser identificadas pelo conteúdo.</p>}
      <p className="m">{st.ai?.enabled ? `IA ativada (${st.ai.model}). Trechos curtos do texto das páginas são enviados ao provedor de IA para interpretar a instrução e confirmar limites. A decisão final continua nas regras e na sua confirmação.` : "IA desativada: a instrução é interpretada por regras simples e não há confirmação semântica. Para ativar, configure ANTHROPIC_API_KEY no servidor."}</p>
      <button className="btn ghost sm" onClick={reset}>Trocar PDF</button>
    </section>)}
    {st?.exec_error && ready && <p className="err" role="alert">{st.exec_error}</p>}

    {(ready || back) && (<>
      <h2>1. Como você deseja separar este PDF?</h2>
      <label className="fld wide"><span>Como você deseja separar este PDF?</span>
        <textarea rows={4} value={instruction} maxLength={2000} placeholder={'Ex.: Separe sempre que começar uma nova nota fiscal. Considere início a página com "DANFE". Use o número da nota no nome do arquivo.'} onChange={(e) => setInstruction(e.target.value)} /></label>
      <button className="btn" disabled={!!busy || instruction.trim().length < 3} onClick={interpret}>Interpretar instrução</button>
      {!form && <button className="btn ghost" onClick={() => setForm({ ...EMPTY })}>Definir parâmetros manualmente</button>}

      {form && (<>
        <h2>2. Parâmetros de separação</h2>
        {notes.map((n, i) => <p key={i} className="m">• {n}</p>)}
        <p className="m">A separação usa estes parâmetros, não o texto livre. Confira e ajuste se precisar.</p>
        <div className="formgrid">
          <label className="fld">Estratégia<Select v={form.strategy} set={(v) => setForm({ ...form, strategy: v })} opts={[["keyword", "Palavra-chave"], ["pattern", "Padrão (expressão regular)"], ["identifier", "Mudança de identificador"], ["combined", "Combinação de regras"], ["semantic", "Estrutura / semântica"]]} /></label>
          <label className="fld">Palavras-chave de início (uma por linha)<textarea rows={3} value={form.kw} onChange={(e) => setForm({ ...form, kw: e.target.value })} /></label>
          <label className="fld">Onde procurar as palavras<Select v={form.loc} set={(v) => setForm({ ...form, loc: v })} opts={[["anywhere", "Em qualquer lugar da página"], ["header", "Só no cabeçalho (primeiras linhas)"]]} /></label>
          <label className="fld">Expressões regulares (uma por linha)<textarea rows={3} value={form.rx} onChange={(e) => setForm({ ...form, rx: e.target.value })} /></label>
          <label className="fld">Identificador<Select v={form.idt} set={(v) => setForm({ ...form, idt: v })} opts={[["none", "Nenhum"], ["invoice_number", "Número da nota"], ["contract_number", "Número do contrato"], ["process", "Número do processo"], ["cpf", "CPF"], ["cnpj", "CNPJ"], ["customer_name", "Nome (cliente/paciente)"], ["custom_regex", "Expressão personalizada"]]} /></label>
          {form.idt === "customer_name" && <label className="fld">Rótulo do nome (ex.: Paciente)<input value={form.label} maxLength={40} onChange={(e) => setForm({ ...form, label: e.target.value })} /></label>}
          {form.idt === "custom_regex" && <label className="fld">Expressão do identificador<input value={form.idr} maxLength={200} onChange={(e) => setForm({ ...form, idr: e.target.value })} /></label>}
          <label className="fld">Combinar regras<Select v={form.combine} set={(v) => setForm({ ...form, combine: v })} opts={[["any", "Qualquer uma (ou)"], ["all", "Todas (e)"]]} /></label>
          <label className="fld">Mínimo de páginas por documento<input type="number" min={1} value={form.minp} onChange={(e) => setForm({ ...form, minp: e.target.value })} /></label>
          <label className="fld">Confiança mínima (%)<input type="number" min={50} max={100} value={form.thr} onChange={(e) => setForm({ ...form, thr: e.target.value })} /></label>
          <label className="chk"><input type="checkbox" checked={form.single} onChange={(e) => setForm({ ...form, single: e.target.checked })} /> Permitir documentos de 1 página</label>
        </div>
        <button className="btn" disabled={!!busy} onClick={simulate}>Simular separação</button>
      </>)}

      {plan && (<>
        <h2>3. Prévia da separação</h2>
        <p><strong>{plan.summary.documents} documento(s)</strong> · {plan.summary.high} alta · {plan.summary.medium} média · {plan.summary.low} baixa{plan.summary.manual ? ` · ${plan.summary.manual} manual` : ""} · {plan.summary.review} para revisão</p>
        <p className="m">Camadas usadas: regras ✓ · estrutura {plan.layers.structure ? "✓" : "—"} · contador de páginas {plan.layers.footer ? "✓" : "—"} · IA {plan.layers.ai ? "✓" : "—"} · Cobertura: {plan.integrity.coverage_pct}% das {plan.integrity.pages_total} páginas</p>
        {plan.issues.map((i: any, k: number) => (<div key={k} className={"issue " + i.severity} role={i.severity === "error" ? "alert" : undefined}>
          <span>{i.severity === "info" ? "ℹ" : "⚠"} {i.message}</span>
          {i.alternatives?.length > 0 && <div className="alts">{i.alternatives.map((a: any, j: number) => <button key={j} className="btn ghost sm" disabled={!!busy} onClick={() => edit(a.starts)}>{a.label}</button>)}</div>}
        </div>))}
        <ul className="docs">{plan.documents.map((d: any, k: number) => (<li key={d.start} className={"dcard" + (d.review ? " review" : "")}>
          <div className="dhead"><strong>Documento {pad(d.index)}</strong><span>Páginas {d.start}–{d.end}</span>
            <span className={"badge " + d.level}>{d.level === "manual" ? "Manual" : `${LEVEL[d.level]} ${d.confidence}%`}</span></div>
          <label className="fld nm">Nome do arquivo<input value={names[d.start] ?? d.name} maxLength={80} onChange={(e) => setNames({ ...names, [d.start]: e.target.value })} /></label>
          {d.warnings.map((w: string, i: number) => <p key={i} className="err">⚠ {w}</p>)}
          <details><summary>Por que a separação nesta página?</summary><ul className="why">{d.evidence.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul></details>
          <details><summary>Visualizar páginas</summary><div className="thumbs"><img loading="lazy" alt={`Primeira página do documento ${d.index}`} src={`${API}/api/split/${sid}/page/${d.start}.png`} />{d.end > d.start && <img loading="lazy" alt={`Última página do documento ${d.index}`} src={`${API}/api/split/${sid}/page/${d.end}.png`} />}</div></details>
          <div className="acts">
            {k > 0 && <label className="inl">Começa na página <input type="number" aria-label={`Página inicial do documento ${d.index}`} defaultValue={d.start} min={plan.documents[k - 1].start + 1} max={d.end} key={d.start}
              onBlur={(e) => { const v = +e.target.value; if (v && v !== d.start) edit(starts0.map((s: number) => (s === d.start - 1 ? v - 1 : s))); }} /></label>}
            {k > 0 && <button className="btn ghost sm" disabled={!!busy} onClick={() => edit(starts0.filter((s: number) => s !== d.start - 1))}>Unir ao anterior</button>}
            {d.end > d.start && <label className="inl">Dividir na página <input type="number" aria-label={`Dividir documento ${d.index} na página`} min={d.start + 1} max={d.end} placeholder={String(d.start + 1)} onKeyDown={(e) => { if (e.key === "Enter") { const v = +(e.target as HTMLInputElement).value; if (v > d.start && v <= d.end) edit([...starts0, v - 1]); } }} /></label>}
          </div></li>))}</ul>
        {needAck && <label className="chk"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> Revisei os alertas e as divisões de baixa confiança e quero continuar.</label>}
        {!plan.integrity.ok && <p className="err">{plan.integrity.problems.join(" ")}</p>}
        <button className="btn" disabled={blocked || !!busy} onClick={execute}>Confirmar separação</button>
      </>)}
    </>)}

    {done && st.report && (() => { const r = st.report; return (<section className="panel" aria-live="polite">
      <h2 className="h2s">{STATUS[r.status] || "Processamento concluído"}</h2>
      <div className="tiles">
        <div><b>{r.pages_original}</b><small>páginas no original</small></div><div><b>{r.documents}</b><small>documentos</small></div>
        <div><b>{r.pages_processed}</b><small>páginas processadas</small></div><div><b>{r.lost}</b><small>perdidas</small></div><div><b>{r.duplicated}</b><small>duplicadas</small></div>
      </div>
      <p>Divisões com alta confiança: {r.high} · média: {r.medium} · baixa: {r.low} · manuais: {r.manual} · para revisão: {r.review}</p>
      <p><strong>Integridade: {r.integrity_ok ? "✓ Confirmada" : "⚠ Não confirmada"}</strong> <span className="m">(reconstrução virtual {r.digest})</span></p>
      <ul className="checks">{r.checks.map((c: any, i: number) => <li key={i}>{c.ok ? "✓" : "✗"} {c.name} <span className="m">— {c.detail}</span></li>)}</ul>
      {r.issues.map((i: any, k: number) => <p key={k} className="err">⚠ {i.message}</p>)}
      {r.corrections > 0 && <p className="issue warning">A validação encontrou problemas e o sistema fez {r.corrections} autocorreção(ões) em relação à prévia aprovada. Confira o histórico abaixo.</p>}
      <table className="ftable"><thead><tr><th>Arquivo</th><th>Páginas</th><th>Confiança</th><th /></tr></thead><tbody>{r.files.map((f: any) => (<tr key={f.index}>
        <td>{f.name}<div className="m">{mb(f.size)}</div></td><td>{f.pages}</td><td>{f.manual ? "Manual" : `${LEVEL[f.level]} ${f.confidence}%`}</td>
        <td><a className="btn sm" href={`${API}/api/split/${sid}/file/${f.index}`}>Baixar</a></td></tr>))}</tbody></table>
      <a className="btn" href={`${API}/api/split/${sid}/zip`}>Baixar ZIP</a>
      <button className="btn ghost" onClick={() => setBack(true)}>Revisar documentos</button>
      <button className="btn ghost" onClick={reset}>Separar outro PDF e excluir este</button>
      <details><summary>Histórico do processamento</summary><ul className="why">{r.history.map((h: any, i: number) => <li key={i}>{h.t} — {h.event}</li>)}</ul></details>
      <p className="m">Os arquivos ficam disponíveis por até 60 minutos e depois são apagados automaticamente.</p>
    </section>); })()}
  </main>);
}
