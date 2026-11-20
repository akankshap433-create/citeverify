import Logo from "./Logo";
const links = ["Dashboard", "Upload", "History", "Settings"];
export default function Navbar({ onNav }) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
        <a href="#" onClick={(e) => { e.preventDefault(); onNav("Dashboard"); }} className="flex items-center gap-2.5 text-xl font-bold tracking-tight">
          <Logo />
          <span><span className="text-slate-800">Cite</span><span className="text-maritime">Verify</span></span>
        </a>
        <ul className="flex items-center gap-1 text-sm font-medium text-slate-600 sm:gap-2">
          {links.map((l) => (
            <li key={l}><button onClick={() => onNav(l)} className="rounded-md px-2.5 py-1.5 transition hover:bg-slate-100 hover:text-ink">{l}</button></li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
