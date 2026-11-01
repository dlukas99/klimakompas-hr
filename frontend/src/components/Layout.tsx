import { NavLink, Outlet } from "react-router";
import hr from "../i18n/hr.json";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-slate-900";
const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 ${FOCUS} ${isActive ? "font-semibold underline" : ""}`;

const LINKS = [
  { to: "/", label: hr.app.nav.home, end: true },
  { to: "/karta", label: hr.app.nav.map },
  { to: "/opcine", label: hr.app.nav.jls },
  { to: "/asistent", label: hr.app.nav.assistant },
  { to: "/podaci", label: hr.app.nav.data },
  { to: "/o-projektu", label: hr.app.nav.about },
];

export function Layout() {
  return (
    <div className="flex h-full flex-col bg-white text-slate-900">
      <a
        href="#sadrzaj"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2"
      >
        {hr.app.skipToContent}
      </a>
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-slate-200 px-4 py-2 print:hidden">
        <NavLink to="/" className={`font-bold ${FOCUS}`}>
          {hr.app.name}
        </NavLink>
        <nav
          aria-label={hr.app.navLabel}
          className="flex flex-wrap gap-x-1 text-sm"
        >
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={linkClass}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main id="sadrzaj" className="relative min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
