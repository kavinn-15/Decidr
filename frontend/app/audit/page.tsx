"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  Download,
  Filter,
  ChevronDown,
  ChevronRight,
  Clock,
  User,
  Activity,
  Layers,
  RefreshCw,
  Search,
  X,
  FileCode,
} from "lucide-react";
import {
  fetchAuditLogs,
  fetchAuditFilters,
  getAuditExportUrl,
  AuditLogItem,
  AuditFilters,
} from "@/lib/api";

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters State
  const [filters, setFilters] = useState<AuditFilters>({
    actors: [],
    actions: [],
    entity_types: [],
  });
  const [selectedActor, setSelectedActor] = useState<string>("");
  const [selectedAction, setSelectedAction] = useState<string>("");
  const [selectedEntityType, setSelectedEntityType] = useState<string>("");

  // Expandable row state
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});

  const loadFilters = async () => {
    try {
      const data = await fetchAuditFilters();
      setFilters(data);
    } catch {
      // ignore
    }
  };

  const loadLogs = async () => {
    try {
      setLoading(true);
      const res = await fetchAuditLogs({
        actor: selectedActor || undefined,
        action: selectedAction || undefined,
        entity_type: selectedEntityType || undefined,
        limit: 100,
        offset: 0,
      });
      setLogs(res.items);
      setTotal(res.total);
    } catch (err: any) {
      console.error("Failed to load audit logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFilters();
  }, []);

  useEffect(() => {
    loadLogs();
  }, [selectedActor, selectedAction, selectedEntityType]);

  const toggleRow = (id: number) => {
    setExpandedRows((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const clearFilters = () => {
    setSelectedActor("");
    setSelectedAction("");
    setSelectedEntityType("");
  };

  const hasActiveFilters = Boolean(selectedActor || selectedAction || selectedEntityType);

  const exportUrl = getAuditExportUrl({
    actor: selectedActor || undefined,
    action: selectedAction || undefined,
    entity_type: selectedEntityType || undefined,
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Audit Trail</h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5" /> Append-Only (Invariant 7)
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Immutable, read-only record of every state transition, proposal execution, and approval event.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <a
            href={exportUrl}
            download
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-2xs transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-slate-500" />
            Export to CSV
          </a>
          <button
            onClick={loadLogs}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200 transition-colors"
            title="Refresh logs"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 font-semibold text-slate-600 uppercase tracking-wider">
              <Filter className="w-3.5 h-3.5 text-slate-400" /> Filters:
            </div>

            {/* Actor filter */}
            <select
              value={selectedActor}
              onChange={(e) => setSelectedActor(e.target.value)}
              className="bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">All Actors</option>
              {filters.actors.map((act) => (
                <option key={act} value={act}>
                  {act}
                </option>
              ))}
            </select>

            {/* Action filter */}
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              className="bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">All Actions</option>
              {filters.actions.map((act) => (
                <option key={act} value={act}>
                  {act}
                </option>
              ))}
            </select>

            {/* Entity Type filter */}
            <select
              value={selectedEntityType}
              onChange={(e) => setSelectedEntityType(e.target.value)}
              className="bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">All Entity Types</option>
              {filters.entity_types.map((ent) => (
                <option key={ent} value={ent}>
                  {ent}
                </option>
              ))}
            </select>

            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-rose-600 font-medium"
              >
                <X className="w-3.5 h-3.5" /> Clear Filters
              </button>
            )}
          </div>

          <div className="text-xs text-slate-400 font-mono">
            Showing {logs.length} of {total} entries (newest-first)
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="animate-pulse flex items-center justify-between py-2 border-b border-slate-100">
                <div className="h-4 bg-slate-200 rounded w-16"></div>
                <div className="h-4 bg-slate-100 rounded w-32"></div>
                <div className="h-4 bg-slate-200 rounded w-48"></div>
                <div className="h-4 bg-slate-100 rounded w-24"></div>
              </div>
            ))}
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-16 px-4">
            <ShieldCheck className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-900">No Audit Logs Found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {hasActiveFilters
                ? "No audit records match the current filter criteria. Try clearing filters."
                : "All state mutations and execution actions will appear here in append-only fashion."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm divide-y divide-slate-200">
              <thead className="bg-slate-50/70 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="w-10 px-4 py-3"></th>
                  <th className="px-4 py-3">Timestamp (UTC)</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Entity</th>
                  <th className="px-4 py-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {logs.map((log) => {
                  const isExpanded = Boolean(expandedRows[log.id]);
                  const hasDetails = Boolean(log.before || log.after);

                  return (
                    <React.Fragment key={log.id}>
                      <tr
                        onClick={() => hasDetails && toggleRow(log.id)}
                        className={`transition-colors ${
                          hasDetails ? "cursor-pointer hover:bg-slate-50/80" : ""
                        } ${isExpanded ? "bg-indigo-50/30" : ""}`}
                      >
                        <td className="px-4 py-3 text-slate-400 text-center">
                          {hasDetails && (
                            <button
                              type="button"
                              className="text-slate-400 hover:text-slate-700 focus:outline-none"
                            >
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4 text-indigo-600" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                            </button>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs font-mono text-slate-600">
                          {log.created_at ? log.created_at.slice(0, 19).replace("T", " ") : "—"}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                            <User className="w-3.5 h-3.5 text-slate-400" />
                            {log.actor}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span
                            className={`inline-block px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold ${
                              log.action.includes("approve")
                                ? "bg-emerald-100 text-emerald-800"
                                : log.action.includes("reject") || log.action.includes("failed")
                                ? "bg-rose-100 text-rose-800"
                                : log.action.includes("execute")
                                ? "bg-blue-100 text-blue-800"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {log.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs">
                          <span className="text-slate-500 font-mono">
                            {log.entity_type} #{log.entity_id}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-right text-xs">
                          {hasDetails ? (
                            <span className="text-indigo-600 font-medium hover:underline">
                              {isExpanded ? "Hide JSON" : "View JSON"}
                            </span>
                          ) : (
                            <span className="text-slate-300">—</span>
                          )}
                        </td>
                      </tr>

                      {/* Expandable Before / After JSON row */}
                      {isExpanded && hasDetails && (
                        <tr className="bg-slate-50/90 border-b border-indigo-100">
                          <td colSpan={6} className="px-8 py-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                              {/* Before JSON */}
                              <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs">
                                <div className="font-semibold text-slate-600 text-[11px] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                  <FileCode className="w-3.5 h-3.5 text-slate-400" />
                                  Before State
                                </div>
                                <pre className="font-mono text-[11px] text-slate-800 bg-slate-50 p-2.5 rounded border border-slate-100 overflow-x-auto max-h-56">
                                  {log.before
                                    ? JSON.stringify(log.before, null, 2)
                                    : "// No prior state"}
                                </pre>
                              </div>

                              {/* After JSON */}
                              <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs">
                                <div className="font-semibold text-emerald-700 text-[11px] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                  <FileCode className="w-3.5 h-3.5 text-emerald-500" />
                                  After State
                                </div>
                                <pre className="font-mono text-[11px] text-slate-800 bg-slate-50 p-2.5 rounded border border-slate-100 overflow-x-auto max-h-56">
                                  {log.after
                                    ? JSON.stringify(log.after, null, 2)
                                    : "// No subsequent state"}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
