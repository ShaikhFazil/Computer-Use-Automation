import { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { findMember } from "../data/members.js";

export default function Confirm() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const member = findMember(id);
  const [done, setDone] = useState(false);

  const type = params.get("type") || "Savings";
  const deposit = params.get("deposit") || "0.00";

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
          <h1 className="text-lg font-semibold text-positive">Sub-account opened</h1>
          <p className="mt-2 text-sm text-slate-600">
            A new {type} sub-account was opened for {member.name}.
          </p>
          <Link
            to={`/member/${member.id}`}
            className="mt-4 inline-block rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
          >
            Back to member
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      <div className="text-xs text-slate-400">
        <Link to={`/member/${member.id}`} className="hover:text-accent">
          {member.name}
        </Link>{" "}
        / Confirmation
      </div>
      <h1 className="mt-1 text-lg font-semibold text-ink">Confirmation</h1>
      <p className="mt-1 text-sm text-slate-500">
        Review before opening. This action creates a real account and cannot be undone.
      </p>

      <dl className="mt-5 rounded-card border border-line bg-surface p-5 shadow-card">
        <div className="flex justify-between border-b border-line py-2 text-sm">
          <dt className="text-slate-500">Member</dt>
          <dd className="font-medium text-ink">
            {member.name} <span className="font-mono text-slate-400">({member.id})</span>
          </dd>
        </div>
        <div className="flex justify-between border-b border-line py-2 text-sm">
          <dt className="text-slate-500">Account type</dt>
          <dd className="font-medium text-ink">{type}</dd>
        </div>
        <div className="flex justify-between py-2 text-sm">
          <dt className="text-slate-500">Initial deposit</dt>
          <dd className="font-mono font-medium text-ink">${deposit}</dd>
        </div>
      </dl>

      <div className="mt-5 flex items-center gap-3">
        <button
          type="button"
          data-testid="confirm-btn"
          onClick={() => setDone(true)}
          className="rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700"
        >
          Confirm
        </button>
        <Link
          to={`/member/${member.id}/sub-account/new`}
          className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
        >
          Back
        </Link>
      </div>
    </div>
  );
}
