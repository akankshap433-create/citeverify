import { useState } from "react";
import { reportUrl, sourceLink, suggestCitations, DISCLAIMER } from "../api";

const VERDICT = {
  "Supported": { cls: "bg-emerald-50 text-emerald-800 border-emerald-200", bar: "bg-emerald-600", tip: "The source's abstract clearly backs this claim." },
  "Partially Supported": { cls: "bg-lime-50 text-lime-800 border-lime-200", bar: "bg-lime-600", tip: "The source backs part of the claim, or the claim goes a bit further than the source." },
  "Unsupported": { cls: "bg-amber-50 text-amber-800 border-amber-200", bar: "bg-amber-500", tip: "The source is related, but nothing in it backs this claim." },
  "Contradictory": { cls: "bg-red-50 text-red-800 border-red-200", bar: "bg-red-600", tip: "The source says something that goes against this claim." },
  "Potentially Outdated": { cls: "bg-indigo-50 text-indigo-800 border-indigo-200", bar: "bg-indigo-500", tip: "This claim describes today's state of the art, but its source is old and may have been superseded." },
  "Unable to Verify": { cls: "bg-slate-100 text-slate-600 border-slate-200", bar: "bg-slate-400", tip: "We couldn't find the source's abstract, so we couldn't check this claim." },
};
const NEEDS_FIX = new Set(["Unsupported", "Contradictory", "Potentially Outdated", "Unable to Verify"]);
const REVIEW = new Set(["Partially Supported", "Unsupported", "Contradictory", "Potentially Outdated"]);
const FILTERS = [
  ["all", "All", () => true],
  ["supported", "Supported", (c) => c.verdict === "Supported"],
  ["review", "Needs Review", (c) => REVIEW.has(c.verdict)],
  ["unable", "Unable to Verify", (c) => c.verdict === "Unable to Verify"],
];
const EMPTY = { status: "processing", claims: [], accuracy: 0, sources: 0, verified: 0, total: 0 };

async function copyText(t) {
  try { await navigator.clipboard.writeText(t); return true; } catch {
    const a = document.createElement("textarea"); a.value = t; document.body.appendChild(a); a.select();
    const ok = document.execCommand("copy"); a.remove(); return ok;
  }
}

function Verdict({ v }) {
  const m = VERDICT[v] || VERDICT["Unable to Verify"];
  return (
    <span className="group relative inline-block shrink-0">
      <span className={`inline-block rounded-md border px-2 py-0.5 text-xs font-semibold ${m.cls}`}>{v}</span>
      <span role="tooltip" className="pointer-events-none absolute left-0 top-full z-20 mt-1 hidden w-60 rounded-lg bg-slate-900 px-3 py-2 text-xs font-normal leading-snug text-white shadow-lg group-hover:block">{m.tip}</span>
    </span>
  );
}

function CopyBtn({ text }) {
  const [ok, setOk] = useState(false);
  return (
    <button onClick={async () => { if (await copyText(text)) { setOk(true); setTimeout(() => setOk(false), 1800); } }} className="btn-ghost shrink-0 !px-3 !py-1.5 text-xs">
      {ok ? "Copied ✓" : "Copy Citation"}
    </button>
  );
}

function Finder({ claim }) {
  const [st, setSt] = useState({ s: "idle", items: [], err: "" });
  async function run() {
    setSt({ s: "loading", items: [], err: "" });
    try { const r = await suggestCitations(claim); setSt({ s: "done", items: r.suggestions || [], err: "" }); }
    catch (e) { setSt({ s: "error", items: [], err: e.message }); }
  }
  return (
    <div className="mt-3">
      {st.s !== "loading" && <button onClick={run} className="btn-ghost !py-1.5 text-xs">{st.s === "idle" ? "Find Better Source (AI)" : "Search again"}</button>}
      {st.s === "loading" && <p className="flex items-center gap-2 text-sm text-slate-600" aria-live="polite"><span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-maritime" />Searching academic databases for better sources…</p>}
      {st.s === "error" && <p role="alert" className="mt-2 text-sm text-red-700">Couldn't fetch suggestions: {st.err}</p>}
      {st.s === "done" && !st.items.length && <p className="mt-2 text-sm text-slate-500">No strong replacements were found. Try rewording the claim.</p>}
      {st.items.length > 0 && (
        <ul className="mt-3 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          {st.items.map((s, i) => {
            const link = sourceLink({ url: s.url, doi: s.doi });
            return (
              <li key={i}>
                {link ? <a href={link} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-maritime hover:underline">{s.title}</a> : <span className="text-sm font-semibold">{s.title}</span>}
                <p className="text-xs text-slate-500">{s.authors.slice(0, 3).join(", ")}{s.authors.length > 3 ? " et al." : ""}{s.year ? ` · ${s.year}` : ""}</p>
                <p className="mt-1 text-sm text-slate-700">{s.why}</p>
                <div className="mt-2 flex items-start gap-2">
                  <p className="flex-1 select-all rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600">{s.apa}</p>
                  <CopyBtn text={s.apa} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

const Label = ({ children }) => <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{children}</p>;

function Claim({ c }) {
  const [open, setOpen] = useState(false);
  const m = VERDICT[c.verdict] || VERDICT["Unable to Verify"];
  const link = sourceLink(c.source);
  return (
    <li className="card p-4">
      <div className="flex items-start gap-3">
        <Verdict v={c.verdict} />
        <div className="min-w-0 flex-1"><Label>Paper's claim</Label><p className="text-sm font-medium">{c.text}</p></div>
        <button onClick={() => setOpen(!open)} aria-expanded={open} className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold text-maritime hover:bg-slate-50">{open ? "Hide details" : "Show details"}</button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
        {c.source ? (
          <>
            <span className="max-w-full truncate">Source: <span className="font-semibold text-slate-700">{c.source.title}</span>{c.source.year ? ` (${c.source.year})` : ""}</span>
            {link && <a href={link} target="_blank" rel="noopener noreferrer" className="font-semibold text-maritime underline-offset-2 hover:underline">View source paper ↗</a>}
          </>
        ) : <span>No source paper was found for this citation.</span>}
      </div>
      {open && (
        <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-2">
          <div><Label>What the source says</Label>
            {c.evidence.length ? <blockquote className="mt-1 border-l-2 border-terra/60 pl-3 text-sm italic text-slate-700">“{c.evidence[0]}”</blockquote> : <p className="mt-1 text-sm text-slate-500">No matching passage was found in the source's abstract.</p>}
          </div>
          <div><Label>Why this verdict</Label><p className="mt-1 text-sm text-slate-700">{c.explanation || "No explanation provided."}</p></div>
          <div className="sm:col-span-2">
            <div className="mb-1 flex justify-between text-xs text-slate-500"><span>Confidence</span><span>{c.confidence}%</span></div>
            <div className="h-1.5 rounded-full bg-slate-100"><div className={`h-1.5 rounded-full ${m.bar}`} style={{ width: `${c.confidence}%` }} /></div>
          </div>
        </div>
      )}
      {NEEDS_FIX.has(c.verdict) && <Finder claim={c.text} />}
    </li>
  );
}

function Stat({ title, sub, value, bar }) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between"><div><p className="text-sm font-semibold">{title}</p><p className="text-xs text-slate-500">{sub}</p></div><span className="font-serif text-3xl font-semibold text-maritime">{value}</span></div>
      {bar != null && <div className="mt-3 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full bg-maritime transition-all duration-700" style={{ width: `${bar}%` }} /></div>}
    </div>
  );
}

function PaperResults({ paper }) {
  const [filter, setFilter] = useState("all");
  const data = paper.data || EMPTY;
  const done = data.status === "completed";
  const shown = data.claims.filter(FILTERS.find((f) => f[0] === filter)[2]);
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="truncate text-sm text-slate-500">{paper.filename}</p>
        {done && <a href={reportUrl(paper.docId)} download className="btn">Download Verification Report (PDF)</a>}
      </div>
      <p role="note" className="mb-5 flex items-start gap-2 rounded-lg border border-slate-200 bg-white/60 px-3 py-2 text-xs text-slate-500">
        <svg className="mt-0.5 h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>{DISCLAIMER}
      </p>
      {(paper.phase === "failed" || data.status === "failed") && <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">Analysis failed{(data.error || paper.error) ? `: ${data.error || paper.error}` : ""}. Upload the paper again to retry.</p>}
      <div className="grid gap-4 md:grid-cols-3">
        <Stat title="Citation Accuracy" sub="Claims backed by their sources" value={done ? `${data.accuracy}%` : "…"} bar={done ? data.accuracy : 0} />
        <Stat title="Scanned Sources" sub="Papers cross-checked" value={done ? data.sources : "…"} />
        <Stat title="Verified Claims" sub={`of ${data.total} extracted`} value={done ? data.verified : "…"} />
      </div>
      {done && (
        <>
          <div className="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Filter claims">
            {FILTERS.map(([k, label, fn]) => (
              <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)}
                className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition ${filter === k ? "border-maritime bg-maritime text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"}`}>
                {label} <span className={filter === k ? "text-white/80" : "text-slate-400"}>({data.claims.filter(fn).length})</span>
              </button>
            ))}
          </div>
          <ul className="mt-4 space-y-3">
            {shown.length ? shown.map((c) => <Claim key={c.id} c={c} />) : <li className="text-sm text-slate-500">Nothing in this group.</li>}
          </ul>
        </>
      )}
    </div>
  );
}

export default function ResultsPanel({ papers, activeId, onSelect, onAdd }) {
  const paper = papers.find((p) => p.uid === activeId) || papers[0];
  return (
    <section id="results" className="mx-auto max-w-7xl px-5 pb-24">
      <h2 className="mb-4 font-serif text-3xl font-semibold tracking-tight">Results</h2>
      <div className="mb-6 flex flex-wrap items-center gap-2" role="tablist" aria-label="Analyzed papers">
        {papers.map((p) => {
          const active = p.uid === paper.uid;
          const busy = p.phase === "uploading" || p.phase === "analyzing";
          return (
            <button key={p.uid} role="tab" aria-selected={active} onClick={() => onSelect(p.uid)}
              className={`flex max-w-[16rem] items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${active ? "border-maritime bg-white shadow-sm" : "border-slate-200 bg-white/60 hover:bg-white"}`}>
              <span className="truncate font-medium">{p.filename}</span>
              {busy ? <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-maritime" aria-label="Analyzing" />
                : p.phase === "failed" ? <span className="shrink-0 text-xs font-semibold text-red-700">Failed</span>
                : <span className="shrink-0 rounded bg-maritime/10 px-1.5 py-0.5 text-xs font-bold text-maritime">{p.data?.accuracy ?? 0}%</span>}
            </button>
          );
        })}
        <button onClick={onAdd} className="rounded-lg border border-dashed border-slate-400 px-3 py-2 text-sm font-medium text-maritime hover:bg-white">+ Add Another Paper</button>
      </div>
      <PaperResults key={paper.uid} paper={paper} />
    </section>
  );
}
