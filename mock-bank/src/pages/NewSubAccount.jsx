import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { findMember } from "../data/members.js";

export default function NewSubAccount() {
  const { id } = useParams();
  const navigate = useNavigate();
  const member = findMember(id);
  const [type, setType] = useState("Savings");
  const [deposit, setDeposit] = useState("");
  const [error, setError] = useState("");

  if (!member) {
    return (
      <div className="mx-auto max-w-xl text-sm text-slate-600">
        Unknown member. <Link to="/" className="text-accent">Back to lookup</Link>.
      </div>
    );
  }

  function onReview(e) {
    e.preventDefault();
    if (deposit && !/^\d+(\.\d{1,2})?$/.test(deposit.trim())) {
      setError("Initial deposit must be a dollar amount, e.g. 100.00.");
      return;
    }
    setError("");
    const q = new URLSearchParams({ type, deposit: deposit.trim() || "0.00" });
    navigate(`/member/${member.id}/sub-account/confirm?${q.toString()}`);
  }

  return (
    <div className="mx-auto max-w-xl">
      <div className="text-xs text-slate-400">
        <Link to={`/member/${member.id}`} className="hover:text-accent">
          {member.name}
        </Link>{" "}
        / New sub-account
      </div>
      <h1 className="mt-1 text-lg font-semibold text-ink">Open a sub-account</h1>
      <p className="mt-1 text-sm text-slate-500">
        Opening for <span className="font-mono">{member.id}</span> — {member.name}.
      </p>

      <form
        onSubmit={onReview}
        aria-label="New sub-account"
        className="mt-5 rounded-card border border-line bg-surface p-5 shadow-card"
      >
        <label htmlFor="acctType" className="block text-sm font-medium text-ink">
          Account type
        </label>
        <select
          id="acctType"
          name="acctType"
          data-testid="account-type"
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="mt-1.5 w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-accent"
        >
          <option>Savings</option>
          <option>Checking</option>
          <option>Money Market</option>
        </select>

        <label htmlFor="deposit" className="mt-4 block text-sm font-medium text-ink">
          Initial deposit (optional)
        </label>
        <input
          id="deposit"
          name="deposit"
          data-testid="initial-deposit"
          inputMode="decimal"
          value={deposit}
          onChange={(e) => setDeposit(e.target.value)}
          placeholder="0.00"
          className="mt-1.5 w-full rounded-md border border-line bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-accent"
        />
        {error && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="mt-5 flex items-center gap-3">
          <button
            type="submit"
            data-testid="review-btn"
            className="rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700"
          >
            Review
          </button>
          <Link
            to={`/member/${member.id}`}
            className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
