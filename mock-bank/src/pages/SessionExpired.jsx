import { Link } from "react-router-dom";

export default function SessionExpired() {
  return (
    <div className="mx-auto max-w-xl">
      <div role="alert" className="rounded-card border border-line bg-surface p-6 shadow-card">
        <h1 className="text-lg font-semibold text-danger">Session expired</h1>
        <p className="mt-2 text-sm text-slate-600">
          Your session has timed out. Please log in to continue.
        </p>
        <Link
          to="/"
          className="mt-4 inline-block rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-700"
        >
          Sign in to continue
        </Link>
      </div>
    </div>
  );
}
