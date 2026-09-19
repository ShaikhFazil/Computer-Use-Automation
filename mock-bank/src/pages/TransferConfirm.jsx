import { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { findMember } from "../data/members.js";

export default function TransferConfirm() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const member = findMember(id);
  const [done, setDone] = useState(false);

  const from = params.get("from") || "";
  const to = params.get("to") || "";
  const amount = params.get("amount") || "0.00";
  const memo = params.get("memo") || "";

  if (!member) {
    return (
      <div className="mx-auto max-w-xl text-sm text-slate-600">
        Unknown member. <Link to="/" className="text-accent">Back to lookup</Link>.
      </div>
    );
  }

  if (done) {
    return (
      <div className="mx-auto max-w-xl">
        <div role="status" className="rounded-card border border-line bg-surface p-6 shadow-card">
          <h1 className="text-lg font-semibold text-positive">Transfer submitted</h1>
          <p className="mt-2 text-sm text-slate-600">
            ${amount} was sent to {to}. A confirmation number will be emailed to the member.
          </p>
          <Link to={`/member/${member.id}`}
            className="mt-4 inline-block rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas">
            Back to member
          </Link>
        </div>
      </div>
    );
  }

  const row = "flex justify-between border-b border-line py-2 text-sm last:border-0";
  return (
    <div className="mx-auto max-w-xl">
      <div className="text-xs text-slate-400">
        <Link to={`/member/${member.id}`} className="hover:text-accent">{member.name}</Link>{" "}
        / Confirm transfer
      </div>
      <h1 className="mt-1 text-lg font-semibold text-ink">Confirm transfer</h1>
      <p className="mt-1 text-sm text-slate-500">
        Review the details. Submitting moves money immediately and cannot be undone.
      </p>

      <dl className="mt-5 rounded-card border border-line bg-surface p-5 shadow-card">
        <div className={row}><dt className="text-slate-500">From</dt><dd className="font-mono text-ink">{from}</dd></div>
        <div className={row}><dt className="text-slate-500">To</dt><dd className="font-medium text-ink">{to}</dd></div>
        <div className={row}><dt className="text-slate-500">Amount</dt><dd className="font-mono font-semibold text-ink">${amount}</dd></div>
        <div className={row}><dt className="text-slate-500">Memo</dt><dd className="text-ink">{memo || "—"}</dd></div>
      </dl>

      <div className="mt-5 flex items-center gap-3">
        {/* RISKY / irreversible — replay gates this step and escalates for confirmation. */}
        <button type="button" data-testid="confirm-transfer" onClick={() => setDone(true)}
          className="rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700">
          Confirm transfer
        </button>
        <Link to={`/member/${member.id}/transfer/new`}
          className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas">
          Back
        </Link>
      </div>
    </div>
  );
}
