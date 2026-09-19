import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { findMember } from "../data/members.js";

export default function TransferNew() {
  const { id } = useParams();
  const navigate = useNavigate();
  const member = findMember(id);

  const [fromAccount, setFromAccount] = useState("");
  const [beneficiary, setBeneficiary] = useState("");
  const [amount, setAmount] = useState("");
  const [memo, setMemo] = useState("");
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
    if (!fromAccount) return setError("Choose a source account.");
    if (!beneficiary) return setError("Choose a beneficiary.");
    if (!/^\d+(\.\d{1,2})?$/.test(amount.trim())) {
      return setError("Enter a valid amount, e.g. 250.00.");
    }
    if (parseFloat(amount) <= 0) return setError("Amount must be greater than zero.");
    setError("");
    const q = new URLSearchParams({
      from: fromAccount, to: beneficiary, amount: amount.trim(), memo: memo.trim(),
    });
    navigate(`/member/${member.id}/transfer/confirm?${q.toString()}`);
  }

  const field = "mt-1.5 w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-accent";

  return (
    <div className="mx-auto max-w-xl">
      <div className="text-xs text-slate-400">
        <Link to={`/member/${member.id}`} className="hover:text-accent">{member.name}</Link>{" "}
        / Transfer funds
      </div>
      <h1 className="mt-1 text-lg font-semibold text-ink">Transfer funds</h1>
      <p className="mt-1 text-sm text-slate-500">
        Move money from <span className="font-mono">{member.id}</span> to a saved beneficiary.
      </p>

      <form onSubmit={onReview} aria-label="Transfer funds" className="mt-5 rounded-card border border-line bg-surface p-5 shadow-card">
        <label htmlFor="fromAccount" className="block text-sm font-medium text-ink">From account</label>
        <select id="fromAccount" name="fromAccount" data-testid="from-account" value={fromAccount}
          onChange={(e) => setFromAccount(e.target.value)} className={field}>
          <option value="">Select an account…</option>
          {member.accounts.map((a) => (
            <option value={a.number}>{a.type} — {a.number} ({a.balance})</option>
          ))}
        </select>

        <label htmlFor="beneficiary" className="mt-4 block text-sm font-medium text-ink">Beneficiary</label>
        <select id="beneficiary" name="beneficiary" data-testid="beneficiary" value={beneficiary}
          onChange={(e) => setBeneficiary(e.target.value)} className={field}>
          <option value="">Select a beneficiary…</option>
          {member.beneficiaries.map((b) => (
            <option key={b.id} value={b.name}>{b.name} — {b.account}</option>
          ))}
        </select>
        {member.beneficiaries.length === 0 && (
          <p className="mt-1.5 text-xs text-warning">No saved beneficiaries for this member.</p>
        )}

        <label htmlFor="amount" className="mt-4 block text-sm font-medium text-ink">Amount (USD)</label>
        <input id="amount" name="amount" data-testid="amount" inputMode="decimal" value={amount}
          onChange={(e) => setAmount(e.target.value)} placeholder="0.00"
          className={`${field} font-mono`} />

        <label htmlFor="memo" className="mt-4 block text-sm font-medium text-ink">Memo (optional)</label>
        <input id="memo" name="memo" data-testid="memo" value={memo}
          onChange={(e) => setMemo(e.target.value)} placeholder="e.g. September rent" className={field} />

        {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}

        <div className="mt-5 flex items-center gap-3">
          <button type="submit" data-testid="review-transfer"
            className="rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700">
            Review transfer
          </button>
          <Link to={`/member/${member.id}`}
            className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
