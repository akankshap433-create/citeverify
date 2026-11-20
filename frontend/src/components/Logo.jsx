// Quotation mark whose tail curves into a checkmark, with a small terracotta dot.
export default function Logo({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <circle cx="13" cy="14" r="6.5" fill="#1D4ED8" />
      <path d="M13 20C13 27 15 31 18 33L33 12" stroke="#1D4ED8" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="33" cy="29" r="2.6" fill="#DC2626" />
    </svg>
  );
}
