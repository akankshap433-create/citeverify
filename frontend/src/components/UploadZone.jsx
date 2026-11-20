import { useRef, useState } from "react";

const STEPS = ["Upload PDF", "AI Checks Original Papers", "Review & Fix Citations"];

export default function UploadZone({ onFiles }) {
  const input = useRef();
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState("");
  const pick = (list) => {
    const all = Array.from(list || []);
    const pdfs = all.filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) return all.length && setErr("Only PDF files are supported.");
    setErr(pdfs.length < all.length ? "Some files were skipped: only PDFs are supported." : "");
    onFiles(pdfs);
  };
  return (
    <div>
      <div
        id="upload-zone"
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files); }}
        className={`flex flex-col items-center rounded-xl border-2 border-dashed p-7 text-center transition ${drag ? "border-maritime bg-sky-50" : "border-slate-300 bg-white"}`}
      >
        <input id="pdf-input" ref={input} type="file" accept="application/pdf" multiple hidden onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
        <div className="grid h-12 w-10 place-items-center rounded-md bg-maritime text-[11px] font-bold text-white">PDF</div>
        <h3 className="mt-3 font-semibold">Drag and drop your scientific paper</h3>
        <p className="mt-1 text-sm text-slate-500">You can add several papers and switch between them.</p>
        <button onClick={() => input.current.click()} className="btn mt-4">Upload</button>
        {err && <p role="alert" className="mt-3 text-sm font-medium text-red-700">{err}</p>}
      </div>
      <ol className="mt-3 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs font-medium text-slate-600">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-maritime/10 text-[11px] font-bold text-maritime">{i + 1}</span>{s}
            {i < STEPS.length - 1 && <span aria-hidden="true" className="text-slate-400">→</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}
