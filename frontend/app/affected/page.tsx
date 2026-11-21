export default function AffectedWorkPage() {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Affected Work</h1>
        <p className="text-sm text-slate-500 mt-1">
          Decision Impact Preview, blast radius tracing, and repair plan approval.
        </p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-slate-600 text-sm">No affected work or active premise breaks detected.</p>
      </div>
    </div>
  );
}
