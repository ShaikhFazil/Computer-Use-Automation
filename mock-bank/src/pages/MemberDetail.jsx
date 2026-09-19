import { useState } from "react";
import { useParams, useSearchParams, Link, useNavigate } from "react-router-dom";
import { findMember } from "../data/members.js";

function Interstitial({ onDismiss }) {

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="System notice"
      className="fixed inset-0 z-20 grid place-items-center bg-ink/40 p-4"
    >
      <div className="w-full max-w-sm rounded-card border border-line bg-surface p-5 shadow-card">
        <h2 className="text-sm font-semibold text-ink">Scheduled maintenance notice</h2>
        <p className="mt-2 text-sm text-slate-600">
          A brief maintenance window is planned for tonight. No action is needed.
        </p>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onDismiss}
            className="rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}

function NotFound({ id }) {
  return (
    <div className="mx-auto max-w-xl">
      <div
        role="status"
        className="rounded-card border border-line bg-surface p-6 shadow-card"
      >
        <h1 className="text-lg font-semibold text-ink">No member found</h1>
        <p className="mt-2 text-sm text-slate-600">
          No member matches ID <span className="font-mono">{id}</span>. Check the
          number and try again.
        </p>
        <Link
          to="/"
          className="mt-4 inline-block rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
        >
          Back to lookup
        </Link>
      </div>
    </div>
  );
}

function Restricted({ member }) {
  return (
    <div className="mx-auto max-w-xl">
      <div role="status" className="rounded-card border border-line bg-surface p-6 shadow-card">
        <h1 className="text-lg font-semibold text-ink">Access restricted</h1>
        <p className="mt-2 text-sm text-slate-600">
          Member <span className="font-mono">{member.id}</span> is flagged{" "}
          <span className="font-medium text-warning">Restricted</span>. You do not
          have permission to view these balances.
        </p>
        <Link
          to="/"
          className="mt-4 inline-block rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
        >
          Back to lookup
        </Link>
      </div>
    </div>
  );
}

export default function MemberDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [showNotice, setShowNotice] = useState(params.get("notice") === "1");

  const member = findMember(id);
  if (!member) return <NotFound id={id} />;
  if (member.status === "Restricted") return <Restricted member={member} />;

  const savings = member.accounts.find((a) => a.type === "Savings");

  return (
    <div className="mx-auto max-w-3xl">
      {showNotice && <Interstitial onDismiss={() => setShowNotice(false)} />}

      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-slate-400">
            <Link to="/" className="hover:text-accent">
              Members
            </Link>{" "}
            / <span className="font-mono">{member.id}</span>
          </div>
          <h1 className="mt-1 text-lg font-semibold text-ink">{member.name}</h1>
          <p className="text-sm text-slate-500">
            Member since {member.since} · {member.status} · {member.phone}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            data-testid="transfer-funds"
            onClick={() => navigate(`/member/${member.id}/transfer/new`)}
            className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
          >
            Transfer funds
          </button>
          <button
            type="button"
            data-testid="open-sub-account"
            onClick={() => navigate(`/member/${member.id}/sub-account/new`)}
            className="rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700"
          >
            Open sub-account
          </button>
        </div>
      </div>

      {member.status === "Dormant" && (
        <div
          role="status"
          className="mt-4 rounded-card border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-warning"
        >
          This account is dormant. Reactivation is required before new
          transactions can be posted.
        </div>
      )}

      {/* Balance summary — the primary extraction target. */}
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          <div className="text-sm text-slate-500">Savings balance</div>
          <div
            data-testid="savings-balance"
            aria-label="Savings balance"
            className="mt-1 font-mono text-2xl font-semibold text-positive"
          >
            {savings ? savings.balance : "—"}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {savings ? savings.number : "No savings account"}
          </div>
        </div>
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          <div className="text-sm text-slate-500">Accounts on file</div>
          <div className="mt-1 font-mono text-2xl font-semibold text-ink">
            {member.accounts.length}
          </div>
          <div className="mt-1 text-xs text-slate-400">{member.email}</div>
        </div>
      </div>

      {/* Full account table. */}
      <div className="mt-4 overflow-hidden rounded-card border border-line bg-surface shadow-card">
        <table className="w-full text-sm">
          <caption className="sr-only">Accounts for member {member.id}</caption>
          <thead>
            <tr className="border-b border-line text-left text-slate-500">
              <th scope="col" className="px-4 py-2.5 font-medium">Account</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Type</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Opened</th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">Balance</th>
            </tr>
          </thead>
          <tbody>
            {member.accounts.map((a) => (
              <tr key={a.number} className="border-b border-line last:border-0">
                <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{a.number}</td>
                <td className="px-4 py-2.5">{a.type}</td>
                <td className="px-4 py-2.5 text-slate-500">{a.opened}</td>
                <td className="px-4 py-2.5 text-right font-mono text-ink">{a.balance}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent activity. */}
      <h2 className="mt-6 text-sm font-semibold text-ink">Recent activity</h2>
      <div className="mt-2 overflow-hidden rounded-card border border-line bg-surface shadow-card">
        {member.transactions.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-400">
            No recent transactions.
          </div>
        ) : (
          <table className="w-full text-sm">
            <caption className="sr-only">Recent transactions for member {member.id}</caption>
            <thead>
              <tr className="border-b border-line text-left text-slate-500">
                <th scope="col" className="px-4 py-2.5 font-medium">Date</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Description</th>
                <th scope="col" className="px-4 py-2.5 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {member.transactions.map((t, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{t.date}</td>
                  <td className="px-4 py-2.5 text-ink">{t.desc}</td>
                  <td
                    className={`px-4 py-2.5 text-right font-mono ${
                      t.kind === "credit" ? "text-positive" : "text-ink"
                    }`}
                  >
                    {t.amount}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
