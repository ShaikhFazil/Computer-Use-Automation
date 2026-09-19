
export default function Placeholder({ title }) {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-lg font-semibold text-ink">{title}</h1>
      <div className="mt-4 grid place-items-center rounded-card border border-dashed border-line bg-surface p-12 text-sm text-slate-400">
        {title} is out of scope for this demo.
      </div>
    </div>
  );
}
