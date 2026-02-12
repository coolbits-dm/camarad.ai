export default function StatusBadge({ label, value, tone = 'text-slate-100' }) {
  return (
    <div className="rounded-2xl bg-surface-light p-4">
      <dt className="text-sm text-slate-400">{label}</dt>
      <dd className={`text-lg font-medium ${tone}`}>{value}</dd>
    </div>
  );
}
