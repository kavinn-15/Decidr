export default function MyWeekPage() {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">My Week</h1>
        <p className="text-sm text-slate-500 mt-1">
          Per-person commitments, upcoming deadlines, and weekly digest preview.
        </p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-slate-600 text-sm">No commitments or tasks assigned yet.</p>
      </div>
    </div>
  );
}
