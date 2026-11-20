export const API_BASE = "https://citeverify-35m1.onrender.com/";

async function handle(res) {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} ${(await res.text().catch(() => "")).slice(0, 160)}`);
  return res.json();
}

export function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);
  return fetch(`${API_BASE}/api/upload`, { method: "POST", body: form }).then(handle);
}
export const startAnalysis = (id) => fetch(`${API_BASE}/api/analyze/${id}`, { method: "POST" }).then(handle);
export const getResults = (id) => fetch(`${API_BASE}/api/results/${id}`).then(handle);
export const getHistory = () => fetch(`${API_BASE}/api/history`).then(handle);
export const suggestCitations = (claim_text) =>
  fetch(`${API_BASE}/api/suggest-citations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ claim_text }) }).then(handle);
export const reportUrl = (id) => `${API_BASE}/api/report/${id}`;

// Maps the exact JSON returned by GET /api/results/{id}:
// { document_id, filename, status, error_message, summary{...}, claims:[{ claim_text, verdict, confidence (0-1),
//   explanation, evidence_passage, source_title, source_authors[], source_year, source_doi, source_url, ... }] }
// Best clickable link for a source: paper URL, else DOI resolved via doi.org.
export function sourceLink(src) {
  if (!src) return null;
  if (src.url) return src.url;
  if (!src.doi) return null;
  return /^https?:/i.test(src.doi) ? src.doi : `https://doi.org/${src.doi}`;
}

export const DISCLAIMER = "Automated verification indicator \u2014 intended to assist human review, not serve as final academic judgment.";

export function normalizeResults(r = {}) {
  const claims = (r.claims || []).map((c) => ({
    id: c.id,
    text: c.claim_text,
    citation: c.in_text_citation,
    reference: c.reference_string,
    verdict: c.verdict || "Unable to Verify", // Supported | Partially Supported | Unsupported | Contradictory | Potentially Outdated | Unable to Verify
    confidence: Math.round((c.confidence || 0) * 100),
    explanation: c.explanation,
    evidence: c.evidence_passage ? [c.evidence_passage] : [],
    source: c.source_title
      ? { title: c.source_title, authors: c.source_authors || [], year: c.source_year, doi: c.source_doi, url: c.source_url }
      : null,
  }));
  const sm = r.summary || {};
  const total = sm.total_claims ?? claims.length;
  const verified = (sm.supported || 0) + (sm.partially_supported || 0);
  const sources = new Set(claims.filter((c) => c.source).map((c) => (c.source.doi || c.source.title).toLowerCase())).size;
  return {
    status: String(r.status || "processing").toLowerCase(), // uploaded | extracting_claims | retrieving_sources | verifying_claims | completed | failed
    error: r.error_message,
    claims,
    total,
    verified,
    sources,
    accuracy: total ? Math.round((verified / total) * 100) : 0,
  };
}
