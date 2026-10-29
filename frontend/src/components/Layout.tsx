import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Overview" },
  { to: "/jobs", label: "Job Listings" },
  { to: "/skills", label: "Skill Intelligence" },
  { to: "/salaries", label: "Salary Insights" },
  { to: "/locations-roles", label: "Locations & Roles" },
  { to: "/sources", label: "Data Sources" },
  { to: "/methodology", label: "Methodology" },
] as const;

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="7" fill="#16233f" />
        <path d="M5 19h5l3-8 5 14 3-9 2 3h4" fill="none" stroke="#f5c542" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-text">JobMarket Pulse</p>
        <p className="text-[11px] text-muted">Open job-market intelligence</p>
      </div>
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { search } = useLocation();
  // Keep period/dimension filters when moving between analytics pages.
  const keep = new URLSearchParams(search);
  ["page", "q", "sort", "company", "skill", "status", "employment_type", "salary_disclosed"].forEach((k) => keep.delete(k));
  const qs = keep.toString() ? `?${keep.toString()}` : "";
  return (
    <ul className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => (
        <li key={item.to}>
          <NavLink
            to={`${item.to}${qs}`}
            end={item.to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              `block rounded-md px-3 py-2 text-sm ${isActive ? "bg-accent/15 font-semibold text-accent" : "text-soft hover:bg-panel-2 hover:text-text"}`
            }
          >
            {item.label}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

export function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-ink">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">
        Skip to content
      </a>
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-ink/95 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button
          type="button"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-soft"
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>
      {open && (
        <nav id="mobile-nav" aria-label="Main" className="border-b border-line bg-panel px-4 py-3 lg:hidden">
          <NavItems onNavigate={() => setOpen(false)} />
        </nav>
      )}
      <div className="mx-auto flex max-w-[1440px]">
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col gap-6 border-r border-line px-4 py-6 lg:flex">
          <Logo />
          <nav aria-label="Main">
            <NavItems />
          </nav>
          <p className="mt-auto text-[11px] leading-relaxed text-muted">
            Data from public job APIs that permit this use. Listings link to their original source.
          </p>
        </aside>
        <main id="main" className="min-w-0 flex-1 px-4 py-6 md:px-8">
          <Outlet />
          <footer className="mt-12 border-t border-line pt-4 text-xs text-muted">
            JobMarket Pulse is an independent open-source project. Coverage is limited to the sources listed on the
            Data Sources page and is not representative of the whole job market.
          </footer>
        </main>
      </div>
    </div>
  );
}
