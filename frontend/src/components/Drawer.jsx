import { useEffect, useState } from "react";
import { API_BASE, DISCLAIMER } from "../api";

const STEPS = [
  ["Extract", "Gemini reads the paper and picks up to 10 claims that carry an in-text citation, mapped to the bibliography entry."],
  ["Retrieve", "Each cited paper is found by title, first author and year in OpenAlex, then Crossref. If no abstract comes back, Semantic Scholar and arXiv are tried."],
  ["Verify", "Gemini compares each claim with the retrieved abstract only, and must quote a verbatim passage as evidence."],
  ["Report", "You get a verdict, confidence score, evidence quote and a link to the source paper for every claim, plus a PDF report."],
];
const VERDICTS = [
  ["Supported", "The abstract directly backs the claim."],
  ["Partially Supported", "Backed in part, or the claim overstates it."],
  ["Unsupported", "Related abstract, but no evidence for this claim."],
  ["Contradictory", "The abstract opposes the claim."],
  ["Potentially Outdated", "A current, state-of-the-art claim resting on a pre-2015 source."],
  ["Unable to Verify", "No usable abstract was found."],
];

function SettingsPanel() {
  const [state, setState] = useState("checking");
  useEffect(() => {
    let live = true;
    fetch(`${API_BASE}/health`).then((r) => live && setState(r.ok ? "ok" : "down")).catch(() => live && setState("down"));
    return () => { live = false; };
  }, []);
  const tone = state === "ok" ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : state === "down" ? "bg-red-50 text-red-700 ring-red-200" : "bg-stone-100 text-stone-600 ring-stone-200";
  return (
    <div className="space-y-6 text-sm text-stone-600">
      <section>
        <h3 className="mb-2 font-bold text-ink">Backend connection</h3>
        <p className={`flex items-center gap-2 rounded-lg px-3 py-2 font-medium ring-1 ${tone}`} aria-live="polite">
          <span className={`h-2 w-2 rounded-full bg-current ${state === "checking" ? "animate-pulse" : ""}`} />
          {state === "ok" ? "Connected to " : state === "down" ? "Cannot reach " : "Checking "}
          <a href={API_BASE} target="_blank" rel="noopener noreferrer" className="underline">{API_BASE}</a>
        </p>
        <p className="mt-2 text-xs">Change <code>API_BASE</code> in <code>src/api.js</code> to use another backend.</p>
      </section>
      <section>
        <h3 className="mb-1 font-bold text-ink">About CiteVerify</h3>
        <p>CiteVerify checks whether the claims in a scientific paper are actually backed by the sources they cite, so reviewers can focus on the claims that need a closer look.</p>
      </section>
      <section>
        <h3 className="mb-2 font-bold text-ink">How verification works</h3>
        <ol className="space-y-2">
          {STEPS.map(([t, body], i) => (
            <li key={t} className="flex gap-3"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-maritime/10 text-xs font-bold text-maritime">{i + 1}</span><span><b className="text-ink">{t}.</b> {body}</span></li>
          ))}
        </ol>
      </section>
      <section>
        <h3 className="mb-2 font-bold text-ink">Verdicts</h3>
        <dl className="space-y-1.5">{VERDICTS.map(([k, v]) => <div key={k}><dt className="inline font-semibold text-ink">{k}: </dt><dd className="inline">{v}</dd></div>)}</dl>
        <p className="mt-2 text-xs">Foundational papers are judged on what they actually report. Age alone never lowers a verdict.</p>
      </section>
      <p className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">{DISCLAIMER}</p>
    </div>
  );
}

export default function Drawer({ panel, onClose, history, loading, error, onPick, activeId }) {
  if (!panel) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onClick={onClose}>
      <aside onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-md overflow-y-auto rounded-l-2xl bg-paper p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-xl font-extrabold">{panel === "history" ? "History" : "Settings"}</h2>
          <button onClick={onClose} className="rounded-md px-2 py-1 text-sm font-semibold text-stone-500 hover:bg-stone-100">Close</button>
        </div>
        {panel === "settings" ? (
          <SettingsPanel />
        ) : loading ? <p className="text-sm text-stone-500">Loading history…</p>
        : error ? <p role="alert" className="text-sm font-medium text-red-600">{error}</p>
        : !history.length ? <p className="text-sm text-stone-500">No papers yet. Upload one to see it here.</p>
        : (
          <ul className="space-y-2">
            {history.map((h, i) => {
              const id = h.document_id ?? h.id;
              return (
                <li key={id ?? i}>
                  <button onClick={() => onPick({ id, filename: h.filename || h.name || h.title || `Document ${id}` })} className={`w-full rounded-lg border p-3 text-left transition hover:bg-white ${activeId === id ? "border-maritime" : "border-stone-200"}`}>
                    <p className="truncate text-sm font-bold">{h.filename || h.name || h.title || `Document ${id}`}</p>
                    <p className="text-xs text-stone-500">{[h.status, h.created_at || h.uploaded_at].filter(Boolean).join(" · ")}</p>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </aside>
    </div>
  );
}
