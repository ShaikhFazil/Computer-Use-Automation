import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Members", icon: "M" },
  { to: "/accounts", label: "Accounts", icon: "A" },
  { to: "/transactions", label: "Transactions", icon: "T" },
  { to: "/settings", label: "Settings", icon: "S" },
];

function SideLink({ to, label, icon }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        [
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
          isActive
            ? "bg-navy text-white"
            : "text-slate-300 hover:bg-navy-700 hover:text-white",
        ].join(" ")
      }
    >
      <span className="grid h-6 w-6 place-items-center rounded bg-white/10 font-mono text-[11px]">
        {icon}
      </span>
      {label}
    </NavLink>
  );
}

export default function Shell({ children }) {
  return (
    <div className="flex min-h-full">
      {/* Sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col bg-navy-900 px-3 py-5 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <div className="grid h-8 w-8 place-items-center rounded-md bg-accent font-semibold text-white">
            M
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-white">Meridian Trust</div>
            <div className="text-[11px] text-slate-400">Servicing Console</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1" aria-label="Primary">
          {NAV.map((n) => (
            <SideLink key={n.to} {...n} />
          ))}
        </nav>
        <div className="mt-auto rounded-md bg-white/5 px-3 py-2 text-[11px] text-slate-400">
          Internal use only. Mock data — no real PII.
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-line bg-surface px-6">
          <div className="text-sm text-slate-500">
            Back-office · <span className="text-ink">Member Servicing</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">Operator</span>
            <div className="grid h-8 w-8 place-items-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
              OP
            </div>
          </div>
        </header>
        <main className="flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
