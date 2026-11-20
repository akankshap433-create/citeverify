// CiteGuide: minimalist academic owl. Palette: #1D4ED8, #DC2626, #FFFFFF.
// mode: "idle" (breathe + blink) | "analyzing" (looks down, scans, lens glows) | "done" (nod + check badge)
export default function CiteGuide({ mode = "idle", className = "h-20 w-20" }) {
  return (
    <svg viewBox="0 0 120 120" className={`owl-${mode} ${className}`} role="img" aria-label={`CiteGuide owl, ${mode}`}>
      <g className="owl-body">
        <path d="M34 34L38 14L53 27Z M86 34L82 14L67 27Z" fill="#1D4ED8" />
        <ellipse cx="60" cy="70" rx="35" ry="38" fill="#1D4ED8" />
        <ellipse cx="60" cy="86" rx="18" ry="20" fill="#FFFFFF" opacity="0.14" />
        <path d="M52 80q4 4 8 0M60 80q4 4 8 0M56 90q4 4 8 0" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" fill="none" opacity="0.4" />
        <path d="M27 66q-5 18 6 34M93 66q5 18 -6 34" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" fill="none" opacity="0.3" />
        <g className="owl-head">
          <g className="owl-eye"><circle cx="45" cy="52" r="13" fill="#FFFFFF" /></g>
          <g className="owl-eye"><circle cx="75" cy="52" r="13" fill="#FFFFFF" /></g>
          <circle className="owl-glow" cx="75" cy="52" r="13" fill="#DC2626" />
          <g className="owl-pupils"><circle cx="45" cy="52" r="5.5" fill="#1D4ED8" /><circle cx="75" cy="52" r="5.5" fill="#1D4ED8" /></g>
          <g stroke="#DC2626" strokeWidth="2" fill="none" strokeLinecap="round">
            <circle cx="45" cy="52" r="15.5" /><circle cx="75" cy="52" r="15.5" />
            <path d="M60.5 51q-.5-2-1 0M29.5 50L22 46M90.5 50L98 46" />
          </g>
          <path d="M60 62L55.5 71H64.5Z" fill="#DC2626" />
        </g>
        <path d="M48 106v8M44 114h8M72 106v8M68 114h8" stroke="#DC2626" strokeWidth="2.4" strokeLinecap="round" />
      </g>
      <g className="owl-badge">
        <circle cx="98" cy="24" r="12" fill="#FFFFFF" stroke="#1D4ED8" strokeWidth="2" />
        <path d="M92 24.5l4.2 4.2L104 19" stroke="#1D4ED8" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </g>
    </svg>
  );
}
