import CiteGuide from "./CiteGuide";

export const STAGES = ["Reading PDF…", "Extracting claims…", "Searching academic databases…", "Comparing evidence…"];
export const stageIndex = (p) => {
  if (!p || p.phase === "uploading") return 0;
  return { extracting_claims: 1, retrieving_sources: 2, verifying_claims: 3 }[p.data?.status] ?? 0;
};

export default function StatusPanel({ paper }) {
  const busy = paper && (paper.phase === "uploading" || paper.phase === "analyzing");
  const done = paper?.phase === "completed";
  const failed = paper?.phase === "failed";
  const idx = stageIndex(paper);
  const title = busy ? STAGES[idx] : done ? `Done: ${paper.data.total} claims checked` : failed ? "Something went wrong" : "Ready when you are";
  const sub = busy ? paper.error || paper.filename : done ? `${paper.data.accuracy}% of claims are backed by their sources` : failed ? paper.error || "Try uploading the paper again." : "Upload a PDF and I'll check every citation.";
  return (
    <div className="card flex items-center gap-4 p-4" aria-live="polite">
      <CiteGuide mode={busy ? "analyzing" : done ? "done" : "idle"} className="h-20 w-20 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{title}</p>
        <p className={`truncate text-sm ${failed || paper?.error ? "text-red-700" : "text-slate-500"}`}>{sub}</p>
        {busy && (
          <ol className="mt-3 flex gap-1.5" aria-label="Progress">
            {STAGES.map((s, i) => <li key={s} title={s} className={`h-1.5 flex-1 rounded-full ${i < idx ? "bg-maritime" : i === idx ? "animate-pulse bg-maritime" : "bg-slate-200"}`} />)}
          </ol>
        )}
      </div>
    </div>
  );
}
