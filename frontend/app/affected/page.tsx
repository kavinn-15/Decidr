"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Clock,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  CheckCircle2,
  HelpCircle,
  Layers,
  User,
  Info,
  Calendar,
  Wrench,
} from "lucide-react";
import {
  fetchAlerts,
  fetchAlertBlastRadius,
  AlertSummaryItem,
  BlastRadiusResponse,
  BlastRadiusAffectedTask,
  BlastRadiusUnaffectedTask,
  BlastRadiusNeedsConfirmationTask,
} from "@/lib/api";

export default function AffectedWorkPage() {
  const [alerts, setAlerts] = useState<AlertSummaryItem[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null);
  const [data, setData] = useState<BlastRadiusResponse | null>(null);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Expanded "why" state mapping task_id -> boolean
  const [expandedWhy, setExpandedWhy] = useState<Record<string, boolean>>({});

  const toggleWhy = (key: string) => {
    setExpandedWhy((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    loadAlerts();
  }, []);

  async function loadAlerts() {
    setLoadingAlerts(true);
    setError(null);
    try {
      const res = await fetchAlerts("all");
      setAlerts(res);
      if (res.length > 0) {
        setSelectedAlertId(res[0].id);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load alerts");
    } finally {
      setLoadingAlerts(false);
    }
  }

  useEffect(() => {
    if (selectedAlertId != null) {
      loadBlastRadius(selectedAlertId);
    } else {
      setData(null);
    }
  }, [selectedAlertId]);

  async function loadBlastRadius(alertId: number) {
    setLoadingData(true);
    setError(null);
    try {
      const res = await fetchAlertBlastRadius(alertId);
      setData(res);
    } catch (err: any) {
      setError(err?.message || "Failed to compute blast radius for alert");
    } finally {
      setLoadingData(false);
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-rose-600" />
            Decision Impact & Blast Radius
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Deterministic graph traversal over confirmed links with zero hallucination.
          </p>
        </div>

        {/* Alert Selector Dropdown */}
        <div className="flex items-center gap-2">
          <label htmlFor="alert-select" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
            Active Alert:
          </label>
          <select
            id="alert-select"
            value={selectedAlertId || ""}
            onChange={(e) => setSelectedAlertId(Number(e.target.value))}
            className="text-xs rounded-lg border border-slate-300 bg-white py-1.5 px-3 font-medium text-slate-800 shadow-xs focus:border-indigo-500 focus:outline-hidden"
            disabled={loadingAlerts || alerts.length === 0}
          >
            {alerts.length === 0 && <option value="">No open alerts</option>}
            {alerts.map((a) => (
              <option key={a.id} value={a.id}>
                Alert #{a.id} [{a.kind.replace("_", " ").toUpperCase()}] - {a.verdict}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading & Error States */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 font-medium">
          {error}
        </div>
      )}

      {loadingAlerts && (
        <div className="space-y-4 animate-pulse">
          <div className="h-28 bg-slate-100 rounded-xl"></div>
          <div className="h-64 bg-slate-100 rounded-xl"></div>
        </div>
      )}

      {!loadingAlerts && alerts.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-xs">
          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
          <h3 className="font-semibold text-slate-900">All Premises & Decisions Holding</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            No active premise breaks, conflicts, or expirations detected. The operational graph is stable.
          </p>
        </div>
      )}

      {!loadingAlerts && data && (
        <div className="space-y-6">
          {/* Trigger Evidence Card */}
          <div className="rounded-xl border border-rose-200 bg-linear-to-r from-rose-50/70 via-white to-amber-50/50 p-5 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider bg-rose-600 text-white shadow-2xs">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {data.alert_kind.replace("_", " ")}
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                  Verdict: {data.verdict}
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  Project: <strong className="text-slate-800">{data.project}</strong>
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="text-xs text-slate-500 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  {data.trigger_evidence.meeting_title} ({data.trigger_evidence.meeting_date})
                </div>
                {data.alert_id && (
                  <Link
                    href={`/review?open_plan=${data.alert_id}`}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-2xs transition-colors"
                  >
                    <Wrench className="w-3.5 h-3.5" />
                    Review Repair Plan
                  </Link>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs mt-3">
              <div className="p-3 bg-white/90 rounded-lg border border-slate-200 shadow-2xs">
                <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                  Baseline (Confirmed Premise / Earlier Decision)
                </div>
                <p className="text-slate-800 italic">"{data.trigger_evidence.old_quote || "N/A"}"</p>
              </div>

              <div className="p-3 bg-rose-50/90 rounded-lg border border-rose-200 shadow-2xs">
                <div className="text-[11px] font-bold text-rose-700 uppercase tracking-wider mb-1">
                  Trigger Event ({data.trigger_evidence.speaker})
                </div>
                <p className="text-rose-950 font-medium italic">
                  "{data.trigger_evidence.new_quote || data.trigger_evidence.explanation}"
                </p>
              </div>
            </div>

            {data.trigger_evidence.explanation && (
              <p className="text-xs text-slate-600 mt-3 pt-2 border-t border-rose-100/60">
                <strong className="text-slate-700">Explanation:</strong> {data.trigger_evidence.explanation}
              </p>
            )}
          </div>

          {/* Banner: Hours at Risk Metrics */}
          <div className="rounded-xl border border-amber-300 bg-linear-to-r from-amber-500 to-amber-600 text-white p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-white/20 rounded-xl backdrop-blur-xs">
                <Clock className="w-7 h-7 text-white" />
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-amber-100">
                  Total Operational Work At Risk
                </div>
                <div className="text-3xl font-extrabold tracking-tight flex items-baseline gap-2">
                  {data.metrics.hours_at_risk}h
                  {data.metrics.unestimated_count > 0 && (
                    <span className="text-xs font-medium bg-amber-700/60 px-2 py-0.5 rounded-full border border-amber-400/40 text-amber-100">
                      + {data.metrics.unestimated_count} unestimated task
                      {data.metrics.unestimated_count > 1 ? "s" : ""}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-6 border-t md:border-t-0 md:border-l border-amber-400/40 pt-3 md:pt-0 md:pl-6 text-xs text-amber-100">
              <div>
                <div className="text-amber-200 font-medium">Total Affected</div>
                <div className="text-xl font-bold text-white">{data.metrics.total_affected}</div>
              </div>
              <div>
                <div className="text-amber-200 font-medium">Direct (Depth 1)</div>
                <div className="text-xl font-bold text-white">{data.metrics.direct_affected}</div>
              </div>
              <div>
                <div className="text-amber-200 font-medium">Indirect (Depth 2+)</div>
                <div className="text-xl font-bold text-white">{data.metrics.indirect_affected}</div>
              </div>
            </div>
          </div>

          {/* Three Categorized Groups */}
          <div className="space-y-8">
            {/* 1. Affected Tasks */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                  Affected Work Items ({data.affected.length})
                </h3>
                <span className="text-xs text-slate-500">
                  Confirmed transitive dependencies
                </span>
              </div>

              {data.affected.length === 0 ? (
                <div className="p-4 bg-slate-50 rounded-lg text-xs text-slate-500 text-center">
                  No downstream tasks affected.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3">
                  {data.affected.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs hover:border-slate-300 transition-colors"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-900">Task #{item.id}:</span>
                          <span className="text-sm font-semibold text-slate-900">{item.title}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[11px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                              item.depth === 1
                                ? "bg-rose-100 text-rose-800"
                                : "bg-purple-100 text-purple-800"
                            }`}
                          >
                            {item.depth === 1 ? "Direct (Depth 1)" : `Indirect (Depth ${item.depth})`}
                          </span>
                          <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                            Status: {item.status}
                          </span>
                        </div>
                      </div>

                      {/* Connected Nodes Chain Visualization */}
                      <div className="my-3 py-2 px-3 bg-slate-50 rounded-lg border border-slate-100 flex flex-wrap items-center gap-2 text-xs">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mr-1">
                          Chain:
                        </span>
                        {item.chain_nodes.map((node, i) => (
                          <React.Fragment key={i}>
                            <span
                              className={`px-2 py-0.5 rounded-md font-mono text-xs font-bold shadow-2xs ${
                                node.type === "premise"
                                  ? "bg-rose-100 text-rose-800 border border-rose-200"
                                  : node.type === "decision"
                                  ? "bg-indigo-100 text-indigo-800 border border-indigo-200"
                                  : "bg-emerald-100 text-emerald-800 border border-emerald-200"
                              }`}
                            >
                              {node.label}
                            </span>
                            {i < item.chain_nodes.length - 1 && (
                              <ArrowRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            )}
                          </React.Fragment>
                        ))}
                      </div>

                      {/* Metadata Row */}
                      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 pt-2 border-t border-slate-100">
                        <div className="flex items-center gap-4">
                          <span className="flex items-center gap-1">
                            <User className="w-3.5 h-3.5 text-slate-400" />
                            {item.owner}
                          </span>
                          <span className="flex items-center gap-1 font-medium text-slate-700">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            {item.estimate_hours != null
                              ? `${item.estimate_hours} hrs estimate`
                              : "Unestimated"}
                          </span>
                          {item.due_date && <span>Due: {item.due_date}</span>}
                        </div>

                        {/* Per-item "Why" Expander */}
                        <button
                          onClick={() => toggleWhy(`aff-${item.id}`)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer"
                        >
                          {expandedWhy[`aff-${item.id}`] ? (
                            <>
                              Hide Explanation <ChevronUp className="w-3.5 h-3.5" />
                            </>
                          ) : (
                            <>
                              Why is this affected? <ChevronDown className="w-3.5 h-3.5" />
                            </>
                          )}
                        </button>
                      </div>

                      {/* Expanded Plain-Code Reason */}
                      {expandedWhy[`aff-${item.id}`] && (
                        <div className="mt-2.5 p-3 bg-indigo-50/70 border border-indigo-100 rounded-lg text-xs text-indigo-950 font-mono">
                          {item.reason}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 2. Needs Confirmation Tasks */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                  Needs Confirmation ({data.needs_confirmation.length})
                </h3>
                <span className="text-xs text-slate-500">
                  Unconfirmed candidate links (Invariant 4: nothing changed)
                </span>
              </div>

              {data.needs_confirmation.length === 0 ? (
                <div className="p-4 bg-slate-50 rounded-lg text-xs text-slate-500 text-center">
                  No uncertain tasks pending link confirmation.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3">
                  {data.needs_confirmation.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-xl border border-amber-200 bg-amber-50/30 p-4 shadow-2xs"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <HelpCircle className="w-4 h-4 text-amber-600 shrink-0" />
                          <span className="text-xs font-bold text-slate-900">Task #{item.id}:</span>
                          <span className="text-sm font-semibold text-slate-900">{item.title}</span>
                        </div>
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200 uppercase tracking-wider">
                          Needs Confirmation
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-xs text-slate-500 mt-2">
                        <span>Assignee: {item.owner}</span>
                        <button
                          onClick={() => toggleWhy(`conf-${item.id}`)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 hover:text-amber-900 cursor-pointer"
                        >
                          {expandedWhy[`conf-${item.id}`] ? (
                            <>
                              Hide Details <ChevronUp className="w-3.5 h-3.5" />
                            </>
                          ) : (
                            <>
                              Why is this pending? <ChevronDown className="w-3.5 h-3.5" />
                            </>
                          )}
                        </button>
                      </div>

                      {expandedWhy[`conf-${item.id}`] && (
                        <div className="mt-2.5 p-3 bg-white border border-amber-200 rounded-lg text-xs text-slate-700">
                          <p className="font-semibold text-amber-900 mb-1">
                            Invariant 4 Policy:
                          </p>
                          Candidate link to justifying decision remains unconfirmed. Until a reviewer approves the link in the Review queue, it is strictly isolated from blast radius updates and no execution state changes are triggered.
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 3. Not Affected Tasks */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  Not Affected ({data.unaffected.length})
                </h3>
                <span className="text-xs text-slate-500">
                  Explicitly verified independent work items
                </span>
              </div>

              {data.unaffected.length === 0 ? (
                <div className="p-4 bg-slate-50 rounded-lg text-xs text-slate-500 text-center">
                  No unaffected tasks in this project scope.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2.5">
                  {data.unaffected.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-lg border border-slate-200 bg-white p-3 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                          <span className="text-xs font-semibold text-slate-900">Task #{item.id}:</span>
                          <span className="text-xs font-medium text-slate-800">{item.title}</span>
                          {item.region && (
                            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                              {item.region}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="text-[11px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                          {item.reason}
                        </span>
                        <button
                          onClick={() => toggleWhy(`unaff-${item.id}`)}
                          className="text-slate-400 hover:text-slate-600 cursor-pointer"
                          title="View rationale"
                        >
                          <Info className="w-4 h-4" />
                        </button>
                      </div>

                      {expandedWhy[`unaff-${item.id}`] && (
                        <div className="w-full mt-2 p-2.5 bg-slate-50 rounded text-xs text-slate-600 border border-slate-100">
                          <strong>Verification Rationale:</strong> {item.reason}. Verified through scope_overlap evaluation and confirmed graph adjacency.
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
