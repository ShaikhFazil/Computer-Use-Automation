import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { MEMBER_LIST } from "../data/members.js";

const STATUS_STYLE = {
  Active: "text-positive bg-emerald-50",
  Restricted: "text-warning bg-amber-50",
  Dormant: "text-slate-500 bg-slate-100",
};

export default function Lookup() {
  const [memberId, setMemberId] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const searchLabel = params.get("tenant") === "westside" ? "Find" : "Search";

  function onSubmit(e) {
    e.preventDefault();
    const id = memberId.trim();
    if (!id) {
      setError("Member ID is required.");
      return;
    }
    if (!/^\d+$/.test(id)) {
      setError("Member ID must be numeric.");
      return;
    }
    setError("");
    navigate(`/member/${id}`);
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-lg font-semibold text-ink">Member lookup</h1>
      <p className="mt-1 text-sm text-slate-500">
        Enter a member ID to open their servicing record.
      </p>

      <form
        onSubmit={onSubmit}
        aria-label="Member lookup"
        className="mt-5 rounded-card border border-line bg-surface p-5 shadow-card"
      >
        <label htmlFor="memberId" className="block text-sm font-medium text-ink">
          Member ID
        </label>
        <input
          id="memberId"
          name="memberId"
          data-testid="member-id-input"
          inputMode="numeric"
          autoComplete="off"
          value={memberId}
          onChange={(e) => setMemberId(e.target.value)}
          placeholder="e.g. 100200"
          aria-invalid={error ? "true" : "false"}
          aria-describedby={error ? "memberId-error" : undefined}
          className="mt-1.5 w-full rounded-md border border-line bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-accent"
        />
        {error && (
          <p id="memberId-error" role="alert" className="mt-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="mt-4 flex items-center gap-3">
          <button
            type="submit"
            data-testid="search-btn"
            className="rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700"
          >
            {searchLabel}
          </button>
          <span className="text-xs text-slate-400">
            Try 100200 (found), 999999 (not found), 100412 (restricted), 100521 (dormant).
          </span>
        </div>
      </form>

      <div className="mt-6">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-ink">Member directory</h2>
          <span className="text-xs text-slate-400">{MEMBER_LIST.length} members</span>
        </div>
        <div className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-slate-500">
                <th scope="col" className="px-4 py-2.5 font-medium">ID</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Name</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                <th scope="col" className="px-4 py-2.5 text-right font-medium">Accounts</th>
              </tr>
            </thead>
            <tbody>
              {MEMBER_LIST.map((m) => (
                <tr
                  key={m.id}
                  onClick={() => navigate(`/member/${m.id}`)}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-canvas"
                >
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{m.id}</td>
                  <td className="px-4 py-2.5 text-ink">{m.name}</td>
                  <td className="px-4 py-2.5">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[m.status] || ""}`}>
                      {m.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600">{m.accounts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
