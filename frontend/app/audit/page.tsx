export default function AuditPage() {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Audit Log</h1>
        <p className="text-sm text-slate-500 mt-1">
          Append-only record of every state transition, approval, and execution event.
        </p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-slate-600 text-sm">No audit logs recorded yet.</p>
      </div>
    </div>
  );
}
