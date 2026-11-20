import { useEffect, useRef, useState } from "react";
import Navbar from "./components/Navbar";
import Hero3D from "./components/Hero3D";
import UploadZone from "./components/UploadZone";
import StatusPanel from "./components/StatusPanel";
import CiteGuide from "./components/CiteGuide";
import ResultsPanel from "./components/ResultsPanel";
import Drawer from "./components/Drawer";
import { uploadPdf, startAnalysis, getResults, getHistory, normalizeResults } from "./api";

const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export default function App() {
  const [papers, setPapers] = useState([]); // { uid, docId, filename, phase, data, error }
  const [activeId, setActiveId] = useState(null);
  const [panel, setPanel] = useState(null);
  const [history, setHistory] = useState([]);
  const [hLoading, setHLoading] = useState(false);
  const [hError, setHError] = useState("");
  const ref = useRef(papers);
  ref.current = papers;

  const patch = (id, p) => setPapers((ps) => ps.map((x) => (x.uid === id ? { ...x, ...p } : x)));

  async function pollOne(id, docId) {
    try {
      const d = normalizeResults(await getResults(docId));
      const end = d.status === "completed" || d.status === "failed";
      patch(id, { data: d, phase: end ? d.status : "analyzing", error: "" });
    } catch (e) { patch(id, { error: `Could not fetch results: ${e.message}` }); }
  }

  // One 3-second loop polls every paper that is still being analyzed.
  useEffect(() => {
    const t = setInterval(() => ref.current.filter((p) => p.docId && p.phase === "analyzing").forEach((p) => pollOne(p.uid, p.docId)), 3000);
    return () => clearInterval(t);
  }, []);

  async function handleFiles(files) {
    for (const file of files) {
      const id = uid();
      setPapers((ps) => [...ps, { uid: id, docId: null, filename: file.name, phase: "uploading", data: null, error: "" }]);
      setActiveId(id);
      try {
        const { document_id } = await uploadPdf(file);
        patch(id, { docId: document_id });
        await startAnalysis(document_id);
        patch(id, { phase: "analyzing" });
        pollOne(id, document_id);
      } catch (e) {
        patch(id, { phase: "failed", error: `Upload failed: ${e.message}. Is the API running at http://127.0.0.1:8000?` });
      }
    }
    setTimeout(() => scrollTo("results"), 150);
  }

  async function openHistory() {
    setPanel("history"); setHLoading(true); setHError("");
    try {
      const h = await getHistory();
      setHistory(Array.isArray(h) ? h : h.items || h.documents || h.history || []);
    } catch (e) { setHError(`Could not load history: ${e.message}`); }
    setHLoading(false);
  }

  function loadPast({ id, filename }) {
    setPanel(null);
    const have = ref.current.find((p) => p.docId === id);
    if (have) setActiveId(have.uid);
    else {
      setPapers((ps) => [...ps, { uid: id, docId: id, filename, phase: "analyzing", data: null, error: "" }]);
      setActiveId(id);
      pollOne(id, id);
    }
    setTimeout(() => scrollTo("results"), 150);
  }

  function onNav(l) {
    if (l === "Dashboard") window.scrollTo({ top: 0, behavior: "smooth" });
    else if (l === "Upload") scrollTo("upload-zone");
    else if (l === "History") openHistory();
    else setPanel("settings");
  }

  const active = papers.find((p) => p.uid === activeId) || papers[papers.length - 1];
  const scanning = papers.some((p) => p.phase === "uploading" || p.phase === "analyzing");

  return (
    <div className="min-h-screen">
      <Navbar onNav={onNav} />
      <main>
        <section className="mx-auto grid max-w-7xl items-center gap-8 px-5 pb-12 pt-10 lg:grid-cols-2 lg:pt-14">
          <div>
            <h1 className="max-w-xl font-serif text-5xl font-semibold leading-[1.08] tracking-tight sm:text-[3.4rem]">AI scientific citation verifier</h1>
            <p className="mt-4 max-w-md text-base text-slate-600">Upload a paper. CiteVerify checks every claim against the sources it cites and shows you which citations need attention.</p>
            <button onClick={() => document.getElementById("pdf-input")?.click()} className="btn-red mt-6">Upload Now</button>
            <div className="mt-6 max-w-lg space-y-4">
              <StatusPanel paper={active} />
              <UploadZone onFiles={handleFiles} />
            </div>
          </div>
          <div className="relative h-[360px] sm:h-[460px] lg:h-[580px]" aria-hidden="true"><Hero3D scanning={scanning} /></div>
        </section>

        {papers.length ? (
          <ResultsPanel papers={papers} activeId={active?.uid} onSelect={setActiveId} onAdd={() => document.getElementById("pdf-input")?.click()} />
        ) : (
          <section className="mx-auto max-w-7xl px-5 pb-24">
            <div className="card flex flex-col items-center gap-3 p-10 text-center">
              <CiteGuide mode="idle" className="h-28 w-28" />
              <h2 className="font-serif text-2xl font-semibold">Your results will appear here</h2>
              <p className="max-w-md text-sm text-slate-500">Upload a scientific paper above. I'll check each cited claim against its original source and flag what needs a closer look.</p>
            </div>
          </section>
        )}
      </main>
      <Drawer panel={panel} onClose={() => setPanel(null)} history={history} loading={hLoading} error={hError} onPick={loadPast} activeId={active?.docId} />
    </div>
  );
}
