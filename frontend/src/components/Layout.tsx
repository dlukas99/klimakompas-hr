import { NavLink, Outlet } from "react-router";
import hr from "../i18n/hr.json";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 focus-visible:outline-2 focus-visible:outline-slate-900 ${isActive ? "font-semibold underline" : ""}`;

export function Layout() {
  return (
    <div className="flex h-full flex-col bg-white text-slate-900">
      <a
        href="#sadrzaj"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2"
      >
        {hr.app.skipToContent}
      </a>
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-2">
        <NavLink
          to="/"
          className="font-bold focus-visible:outline-2 focus-visible:outline-slate-900"
        >
          {hr.app.name}
        </NavLink>
        <nav aria-label={hr.app.navLabel} className="flex gap-1 text-sm">
          <NavLink to="/" end className={linkClass}>
            {hr.app.navHome}
          </NavLink>
          <NavLink to="/karta" className={linkClass}>
            {hr.app.navMap}
          </NavLink>
        </nav>
      </header>
      <main id="sadrzaj" className="relative min-h-0 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
