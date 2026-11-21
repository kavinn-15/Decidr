export default function DecisionLedgerPage() {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Decision Ledger</h1>
        <p className="text-sm text-slate-500 mt-1">
          Searchable, cross-meeting institutional memory of decisions and active premises.
        </p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-slate-600 text-sm">Decision ledger is empty.</p>
      </div>
    </div>
  );
}
