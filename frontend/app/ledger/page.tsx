"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  Filter,
  X,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Layers,
  ArrowRight,
  ExternalLink,
  RefreshCw,
  GitBranch,
  Quote,
  ShieldAlert,
  User,
  Info,
  ChevronRight,
  Sparkles,
  History,
  Check,
  AlertCircle,
  FileText,
} from "lucide-react";
import {
  fetchDecisions,
  fetchDecisionDetail,
  fetchUtterances,
  DecisionSummary,
  DecisionDetailResponse,
  DecisionPremiseItem,
  DecisionLinkedTask,
  DecisionVersionItem,
  DecisionTimelineItem,
  UtteranceItem,
} from "@/lib/api";

// --- Color Helpers ---

function getStatusBadge(status: string) {
  switch (status.toLowerCase()) {
    case "active":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Active
        </span>
      );
    case "at_risk":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <AlertTriangle className="w-3 h-3 text-amber-500" />
          At Risk
        </span>
      );
    case "superseded":
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
          <Clock className="w-3 h-3 text-slate-500" />
          Superseded
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-50 text-slate-600 border border-slate-200">
          {status}
        </span>
      );
  }
}

function getPremiseStatusChip(status: string) {
  switch (status.toLowerCase()) {
    case "holding":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          Holding
        </span>
      );
    case "shaky":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
          Shaky
        </span>
      );
    case "broken":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
          Broken
        </span>
      );
    case "expired":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
          <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
          Expired
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-50 text-slate-600 border border-slate-200">
          {status}
        </span>
      );
  }
}

function getTaskStatusBadge(status: string) {
  switch (status.toLowerCase()) {
    case "open":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
          Open
        </span>
      );
    case "at_risk":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
          At Risk
        </span>
      );
    case "done":
    case "completed":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          Done
        </span>
      );
    case "cancelled":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
          Cancelled
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200">
          {status}
        </span>
      );
  }
}

// --- Small Graph Component at the top of drawer ---

interface GraphProps {
  decision: DecisionDetailResponse["decision"];
  premises: DecisionPremiseItem[];
  tasks: DecisionLinkedTask[];
}

function DecisionKnowledgeGraph({ decision, premises, tasks }: GraphProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 shadow-inner">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 uppercase tracking-wider">
          <GitBranch className="w-3.5 h-3.5 text-indigo-500" />
          Knowledge Graph Connection
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 bg-emerald-500 rounded" /> Confirmed Link
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 bg-amber-400 border-b border-dashed border-amber-500" /> Provisional Link
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
        {/* Column 1: Premises */}
        <div className="space-y-2">
          <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wide px-1">
            Premises ({premises.length})
          </div>
          {premises.length === 0 ? (
            <div className="p-2.5 rounded-lg border border-dashed border-slate-200 bg-white text-xs text-slate-400 text-center">
              No premises recorded
            </div>
          ) : (
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {premises.map((p) => {
                const statusColor =
                  p.status === "holding"
                    ? "border-emerald-300 bg-emerald-50/70 text-emerald-900"
                    : p.status === "shaky"
                    ? "border-amber-300 bg-amber-50/70 text-amber-900"
                    : p.status === "broken"
                    ? "border-rose-300 bg-rose-50/70 text-rose-900"
                    : "border-purple-300 bg-purple-50/70 text-purple-900";
                return (
                  <div
                    key={p.id}
                    className={`p-2 rounded-lg border text-xs shadow-xs transition-all hover:shadow-sm ${statusColor}`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-0.5">
                      <span className="font-bold text-[11px]">P{p.id}</span>
                      {getPremiseStatusChip(p.status)}
                    </div>
                    <p className="line-clamp-2 text-[11px] leading-tight font-medium opacity-90">{p.text}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Column 2: Decision (Center Node) */}
        <div className="flex flex-col items-center justify-center p-2">
          <div className="w-full flex items-center justify-center mb-1">
            <div className="hidden md:flex items-center w-full justify-between px-2 text-indigo-400">
              <span className="text-[10px] font-semibold text-slate-400">supports →</span>
              <span className="text-[10px] font-semibold text-slate-400">→ justifies</span>
            </div>
          </div>
          <div className="w-full rounded-xl border-2 border-indigo-300 bg-white p-3.5 shadow-sm text-center relative">
            <div className="flex items-center justify-center gap-1.5 mb-1.5">
              <span className="px-2 py-0.5 rounded-md text-xs font-bold bg-indigo-100 text-indigo-800">
                Decision #{decision.id}
              </span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700">
                v{decision.version}
              </span>
            </div>
            <p className="text-xs font-semibold text-slate-900 line-clamp-3 leading-snug mb-2">
              {decision.text}
            </p>
            <div className="flex items-center justify-center gap-1.5">
              {getStatusBadge(decision.status)}
              {decision.scope_region && (
                <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-teal-50 text-teal-700 border border-teal-200">
                  {decision.scope_region}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Column 3: Tasks */}
        <div className="space-y-2">
          <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wide px-1">
            Tasks ({tasks.length})
          </div>
          {tasks.length === 0 ? (
            <div className="p-2.5 rounded-lg border border-dashed border-slate-200 bg-white text-xs text-slate-400 text-center">
              No tasks linked
            </div>
          ) : (
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {tasks.map((t) => {
                const isConfirmed = t.link_confirmed ?? !t.provisional;
                return (
                  <div
                    key={t.id}
                    className={`p-2 rounded-lg border text-xs shadow-xs transition-all hover:shadow-sm bg-white ${
                      isConfirmed ? "border-slate-200" : "border-amber-300 border-dashed bg-amber-50/30"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-0.5">
                      <span className="font-bold text-[11px] text-slate-700">T{t.id}</span>
                      <div className="flex items-center gap-1">
                        {isConfirmed ? (
                          <span className="inline-flex items-center text-[10px] font-semibold text-emerald-700" title="Confirmed link">
                            <Check className="w-3 h-3 text-emerald-600" />
                          </span>
                        ) : (
                          <span className="inline-flex items-center text-[10px] font-semibold text-amber-700" title="Provisional link">
                            <AlertCircle className="w-3 h-3 text-amber-600" />
                          </span>
                        )}
                        {getTaskStatusBadge(t.status)}
                      </div>
                    </div>
                    <p className="line-clamp-2 text-[11px] text-slate-800 leading-tight font-medium">
                      {t.title}
                    </p>
                    {t.owner_name && (
                      <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
                        <User className="w-2.5 h-2.5" /> {t.owner_name}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Main Page Component ---

export default function DecisionLedgerPage() {
  const [decisions, setDecisions] = useState<DecisionSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [selectedProject, setSelectedProject] = useState<string>("all");
  const [selectedRegion, setSelectedRegion] = useState<string>("all");

  // Drawer state
  const [selectedDecisionId, setSelectedDecisionId] = useState<number | null>(null);
  const [drawerDetail, setDrawerDetail] = useState<DecisionDetailResponse | null>(null);
  const [drawerLoading, setDrawerLoading] = useState<boolean>(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  // Transcript Quote Inspector Modal
  const [inspectingPremise, setInspectingPremise] = useState<DecisionPremiseItem | null>(null);
  const [transcriptUtterances, setTranscriptUtterances] = useState<UtteranceItem[]>([]);
  const [transcriptLoading, setTranscriptLoading] = useState<boolean>(false);

  // Load decisions list
  const loadDecisions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params: Parameters<typeof fetchDecisions>[0] = {};
      if (searchTerm.trim()) params.text = searchTerm.trim();
      if (selectedStatus !== "all") params.status = selectedStatus;
      if (selectedProject !== "all") params.project = selectedProject;
      if (selectedRegion !== "all") params.region = selectedRegion;

      const data = await fetchDecisions(params);
      setDecisions(data);
    } catch (err: any) {
      setError(err.message || "Failed to load decisions from ledger");
    } finally {
      setLoading(false);
    }
  }, [searchTerm, selectedStatus, selectedProject, selectedRegion]);

  useEffect(() => {
    loadDecisions();
  }, [loadDecisions]);

  // Handle row click & drawer opening
  const handleOpenDrawer = async (id: number) => {
    setSelectedDecisionId(id);
    setDrawerLoading(true);
    setDrawerError(null);
    try {
      const detail = await fetchDecisionDetail(id);
      setDrawerDetail(detail);
    } catch (err: any) {
      setDrawerError(err.message || "Failed to load decision detail");
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleCloseDrawer = () => {
    setSelectedDecisionId(null);
    setDrawerDetail(null);
    setDrawerError(null);
  };

  // Close drawer on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (inspectingPremise) {
          setInspectingPremise(null);
        } else if (selectedDecisionId) {
          handleCloseDrawer();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedDecisionId, inspectingPremise]);

  // Open Transcript Quote Inspector
  const handleOpenQuoteInspector = async (premise: DecisionPremiseItem) => {
    setInspectingPremise(premise);
    const meetingId = premise.meeting_id || drawerDetail?.decision.meeting_id;
    if (meetingId) {
      setTranscriptLoading(true);
      try {
        const utts = await fetchUtterances(meetingId);
        setTranscriptUtterances(utts);
      } catch (e) {
        console.error("Failed to fetch meeting transcript utterances:", e);
      } finally {
        setTranscriptLoading(false);
      }
    } else {
      setTranscriptUtterances([]);
    }
  };

  // Extract unique projects and regions for filters
  const { availableProjects, availableRegions } = useMemo(() => {
    const projects = new Set<string>();
    const regions = new Set<string>();

    decisions.forEach((d) => {
      if (d.scope_project) projects.add(d.scope_project);
      if (d.scope_region) regions.add(d.scope_region);
    });

    return {
      availableProjects: Array.from(projects),
      availableRegions: Array.from(regions),
    };
  }, [decisions]);

  // Summary Metrics
  const summaryMetrics = useMemo(() => {
    const total = decisions.length;
    const active = decisions.filter((d) => d.status === "active").length;
    const atRisk = decisions.filter((d) => d.status === "at_risk").length;
    const superseded = decisions.filter((d) => d.status === "superseded").length;
    return { total, active, atRisk, superseded };
  }, [decisions]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="border-b border-slate-200 pb-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
            <Layers className="w-6 h-6 text-indigo-600" />
            Decision Ledger
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Searchable, cross-meeting institutional memory of decisions and active premises.
          </p>
        </div>

        {/* Quick Stats Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700">
            Total: <span className="font-bold text-slate-900">{summaryMetrics.total}</span>
          </div>
          <div className="px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs font-semibold text-emerald-800">
            Active: <span className="font-bold text-emerald-900">{summaryMetrics.active}</span>
          </div>
          <div className="px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-lg text-xs font-semibold text-amber-800">
            At Risk: <span className="font-bold text-amber-900">{summaryMetrics.atRisk}</span>
          </div>
          <div className="px-3 py-1.5 bg-slate-100 border border-slate-300 rounded-lg text-xs font-semibold text-slate-800">
            Superseded: <span className="font-bold text-slate-900">{summaryMetrics.superseded}</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Text search */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search decisions and premises by keyword (e.g. 'UPI', 'Provider A', 'contract')..."
              className="w-full pl-9 pr-9 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 placeholder:text-slate-400"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Status Filter */}
          <div className="w-full md:w-44">
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="at_risk">At Risk</option>
              <option value="superseded">Superseded</option>
            </select>
          </div>

          {/* Project Filter */}
          <div className="w-full md:w-48">
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Projects</option>
              {availableProjects.map((proj) => (
                <option key={proj} value={proj}>
                  {proj}
                </option>
              ))}
            </select>
          </div>

          {/* Region Filter */}
          <div className="w-full md:w-40">
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Regions</option>
              {availableRegions.map((reg) => (
                <option key={reg} value={reg}>
                  {reg}
                </option>
              ))}
            </select>
          </div>

          {/* Refresh / Clear Button */}
          {(searchTerm || selectedStatus !== "all" || selectedProject !== "all" || selectedRegion !== "all") && (
            <button
              onClick={() => {
                setSearchTerm("");
                setSelectedStatus("all");
                setSelectedProject("all");
                setSelectedRegion("all");
              }}
              className="px-3 py-2 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors flex items-center justify-center gap-1.5"
            >
              <X className="w-3.5 h-3.5" /> Clear Filters
            </button>
          )}
        </div>

        {/* Search indicator */}
        {searchTerm.trim() && (
          <div className="flex items-center gap-1.5 text-xs text-indigo-700 bg-indigo-50/70 px-3 py-1.5 rounded-lg border border-indigo-100">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>
              Ranking decisions by BM25 relevance score over decisions and supporting premise texts.
            </span>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {loading ? (
        // Loading Skeleton
        <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4 shadow-sm animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/4 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-14 bg-slate-100 rounded-lg w-full" />
            ))}
          </div>
        </div>
      ) : error ? (
        // Error State
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-rose-600 mx-auto" />
          <h3 className="text-base font-semibold text-rose-900">Failed to Load Decisions</h3>
          <p className="text-sm text-rose-700">{error}</p>
          <button
            onClick={loadDecisions}
            className="px-4 py-2 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700 transition-colors inline-flex items-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Retry
          </button>
        </div>
      ) : decisions.length === 0 ? (
        // Empty State
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center space-y-3 shadow-sm">
          <Layers className="w-10 h-10 text-slate-300 mx-auto" />
          <h3 className="text-base font-semibold text-slate-800">No decisions found</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            {searchTerm || selectedStatus !== "all" || selectedProject !== "all" || selectedRegion !== "all"
              ? "No decisions matched your search query or filter criteria. Try broadening your filters."
              : "No decisions have been approved yet. Decisions will appear here once meeting items are confirmed in the review queue."}
          </p>
          {(searchTerm || selectedStatus !== "all" || selectedProject !== "all" || selectedRegion !== "all") && (
            <button
              onClick={() => {
                setSearchTerm("");
                setSelectedStatus("all");
                setSelectedProject("all");
                setSelectedRegion("all");
              }}
              className="mt-2 px-3 py-1.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-semibold hover:bg-indigo-100 transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        // Decisions Table
        <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50/80 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Decision</th>
                  <th className="py-3 px-4">Project & Region</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Effective Dates</th>
                  <th className="py-3 px-4">Premises</th>
                  <th className="py-3 px-4 text-center">Version</th>
                  {searchTerm.trim() && <th className="py-3 px-4 text-right">BM25 Score</th>}
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {decisions.map((dec) => {
                  const isSelected = selectedDecisionId === dec.id;
                  return (
                    <tr
                      key={dec.id}
                      onClick={() => handleOpenDrawer(dec.id)}
                      className={`cursor-pointer transition-colors group ${
                        isSelected ? "bg-indigo-50/50" : "hover:bg-slate-50/70"
                      }`}
                    >
                      {/* Decision text & ID */}
                      <td className="py-3.5 px-4 max-w-md">
                        <div className="flex items-start gap-2">
                          <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-700 shrink-0 mt-0.5">
                            D{dec.id}
                          </span>
                          <div>
                            <div className="font-medium text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-2">
                              {dec.text}
                            </div>
                            {dec.supersedes_id && (
                              <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
                                <span className="font-semibold text-amber-700">Supersedes:</span> Decision #{dec.supersedes_id}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Project & Region Scope */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="space-y-1">
                          <div className="font-medium text-slate-800 text-xs">
                            {dec.scope_project}
                          </div>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {dec.scope_region ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-teal-50 text-teal-700 border border-teal-200">
                                {dec.scope_region}
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-50 text-slate-500 border border-slate-200">
                                Global Region
                              </span>
                            )}
                            {dec.scope_release && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-50 text-purple-700 border border-purple-200">
                                {dec.scope_release}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getStatusBadge(dec.status)}
                      </td>

                      {/* Effective Dates */}
                      <td className="py-3.5 px-4 whitespace-nowrap text-xs text-slate-600">
                        {dec.effective_from ? (
                          <div className="flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5 text-slate-400" />
                            <span>{dec.effective_from}</span>
                            {dec.effective_to ? (
                              <span>→ {dec.effective_to}</span>
                            ) : (
                              <span className="text-slate-400">→ Present</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">Not specified</span>
                        )}
                      </td>

                      {/* Premises & Mini status indicators */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-slate-700">
                            {dec.premises_count} premise{dec.premises_count !== 1 ? "s" : ""}
                          </span>
                          {/* Mini indicator dots */}
                          <div className="flex items-center gap-1">
                            {dec.premises.slice(0, 4).map((p) => {
                              const dotColor =
                                p.status === "holding"
                                  ? "bg-emerald-500"
                                  : p.status === "shaky"
                                  ? "bg-amber-500"
                                  : p.status === "broken"
                                  ? "bg-rose-500"
                                  : "bg-purple-500";
                              return (
                                <span
                                  key={p.id}
                                  className={`w-2 h-2 rounded-full ${dotColor}`}
                                  title={`P${p.id}: ${p.status}`}
                                />
                              );
                            })}
                          </div>
                        </div>
                      </td>

                      {/* Version */}
                      <td className="py-3.5 px-4 whitespace-nowrap text-center">
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                          v{dec.version}
                        </span>
                      </td>

                      {/* BM25 Score */}
                      {searchTerm.trim() && (
                        <td className="py-3.5 px-4 whitespace-nowrap text-right">
                          <span className="font-mono text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                            {dec.score.toFixed(3)}
                          </span>
                        </td>
                      )}

                      {/* Actions */}
                      <td className="py-3.5 px-4 whitespace-nowrap text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDrawer(dec.id);
                          }}
                          className="px-2.5 py-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded-lg transition-colors inline-flex items-center gap-1"
                        >
                          Detail <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* DETAIL DRAWER (Slide-over) */}
      {selectedDecisionId !== null && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-in fade-in"
            onClick={handleCloseDrawer}
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-2xl bg-white shadow-2xl flex flex-col border-l border-slate-200 animate-in slide-in-from-right duration-200">
              {/* Drawer Header */}
              <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <span className="px-2 py-0.5 rounded-md text-xs font-bold bg-indigo-600 text-white">
                    Decision #{selectedDecisionId}
                  </span>
                  {drawerDetail && (
                    <>
                      {getStatusBadge(drawerDetail.decision.status)}
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-200 text-slate-800">
                        v{drawerDetail.decision.version}
                      </span>
                    </>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCloseDrawer}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors"
                    title="Close drawer (Esc)"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Drawer Body */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {drawerLoading ? (
                  <div className="space-y-4 animate-pulse">
                    <div className="h-28 bg-slate-100 rounded-xl" />
                    <div className="h-6 bg-slate-200 rounded w-1/3" />
                    <div className="h-20 bg-slate-100 rounded-lg" />
                    <div className="h-20 bg-slate-100 rounded-lg" />
                  </div>
                ) : drawerError ? (
                  <div className="p-4 rounded-xl border border-rose-200 bg-rose-50 text-rose-800 text-sm">
                    {drawerError}
                  </div>
                ) : drawerDetail ? (
                  <>
                    {/* 1. Small Graph at Top: premises > decision > tasks */}
                    <DecisionKnowledgeGraph
                      decision={drawerDetail.decision}
                      premises={drawerDetail.premises}
                      tasks={drawerDetail.linked_tasks}
                    />

                    {/* 2. Decision Overview Card */}
                    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                      <div>
                        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                          Decision Text
                        </div>
                        <h2 className="text-base font-bold text-slate-900 leading-snug">
                          {drawerDetail.decision.text}
                        </h2>
                      </div>

                      {/* Scope and Effective Dates Grid */}
                      <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100 text-xs">
                        <div>
                          <span className="text-slate-500 font-medium">Project:</span>{" "}
                          <span className="font-semibold text-slate-800">
                            {drawerDetail.decision.scope_project}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 font-medium">Region:</span>{" "}
                          <span className="font-semibold text-slate-800">
                            {drawerDetail.decision.scope_region || "Global (All Regions)"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 font-medium">Release:</span>{" "}
                          <span className="font-semibold text-slate-800">
                            {drawerDetail.decision.scope_release || "Not specified"}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-500 font-medium">Effective Period:</span>{" "}
                          <span className="font-semibold text-slate-800">
                            {drawerDetail.decision.effective_from || "N/A"}{" "}
                            {drawerDetail.decision.effective_to
                              ? `to ${drawerDetail.decision.effective_to}`
                              : "(Ongoing)"}
                          </span>
                        </div>
                      </div>

                      {/* Source Meeting */}
                      {drawerDetail.decision.meeting_title && (
                        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                          <span className="text-slate-500">
                            Source Meeting:{" "}
                            <span className="font-semibold text-slate-800">
                              {drawerDetail.decision.meeting_title}
                            </span>{" "}
                            ({drawerDetail.decision.meeting_date || ""})
                          </span>
                          {drawerDetail.decision.meeting_id && (
                            <Link
                              href={`/review?meeting_id=${drawerDetail.decision.meeting_id}`}
                              className="text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1"
                            >
                              Open in Review <ExternalLink className="w-3 h-3" />
                            </Link>
                          )}
                        </div>
                      )}
                    </div>

                    {/* 3. Status Timeline built from audit_log with dates and cause of each change */}
                    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          <History className="w-4 h-4 text-indigo-600" />
                          Status Timeline & Audit Trail
                        </div>
                        <span className="text-[11px] text-slate-500">
                          {drawerDetail.status_timeline.length} transition(s)
                        </span>
                      </div>

                      <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                        {drawerDetail.status_timeline.map((entry, idx) => {
                          const isLatest = idx === drawerDetail.status_timeline.length - 1;
                          const dotColor =
                            entry.status === "active"
                              ? "bg-emerald-500"
                              : entry.status === "at_risk"
                              ? "bg-amber-500"
                              : entry.status === "superseded"
                              ? "bg-slate-500"
                              : "bg-indigo-500";

                          return (
                            <div key={entry.id || idx} className="relative">
                              <span
                                className={`absolute -left-6 top-1.5 w-4 h-4 rounded-full border-2 border-white ${dotColor} shadow-xs`}
                              />
                              <div className="bg-slate-50/80 rounded-lg p-3 border border-slate-200/80 text-xs space-y-1">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-bold text-slate-800 capitalize">
                                      {entry.status || entry.action}
                                    </span>
                                    {isLatest && (
                                      <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-indigo-100 text-indigo-700">
                                        Current
                                      </span>
                                    )}
                                  </div>
                                  <span className="text-[11px] text-slate-500 font-mono">
                                    {entry.created_at ? new Date(entry.created_at).toLocaleString() : "Date N/A"}
                                  </span>
                                </div>
                                <div className="text-slate-700 font-medium">
                                  <span className="text-slate-500 font-normal">Cause:</span>{" "}
                                  {entry.cause || `Action: ${entry.action}`}
                                </div>
                                <div className="text-[11px] text-slate-500 flex items-center gap-1">
                                  <User className="w-3 h-3" /> By {entry.actor}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* 4. Premises Section (Chips colored by status, clicking quote opens transcript) */}
                    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          Underlying Premises ({drawerDetail.premises.length})
                        </div>
                        <span className="text-[11px] text-slate-500">
                          Click quote to inspect transcript utterance
                        </span>
                      </div>

                      {drawerDetail.premises.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">No premises attached to this decision.</p>
                      ) : (
                        <div className="space-y-3">
                          {drawerDetail.premises.map((p) => {
                            return (
                              <div
                                key={p.id}
                                className="rounded-lg border border-slate-200 bg-slate-50/50 p-3.5 space-y-2 hover:border-slate-300 transition-colors"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <div className="flex items-center gap-2">
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-700">
                                      P{p.id}
                                    </span>
                                    {getPremiseStatusChip(p.status)}
                                  </div>
                                  <span className="text-[11px] text-slate-500 font-medium capitalize">
                                    State: {p.state}
                                  </span>
                                </div>

                                <p className="text-xs font-medium text-slate-900 leading-snug">
                                  {p.text}
                                </p>

                                {/* Source Quote Box */}
                                {p.evidence_quote && (
                                  <div
                                    onClick={() => handleOpenQuoteInspector(p)}
                                    className="cursor-pointer group flex items-start gap-2 p-2.5 rounded-md bg-white border border-slate-200/90 text-xs text-slate-700 hover:border-indigo-400 hover:bg-indigo-50/30 transition-all"
                                    title="Click to inspect this utterance in the transcript"
                                  >
                                    <Quote className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600 shrink-0 mt-0.5" />
                                    <div className="flex-1">
                                      <span className="italic font-serif text-slate-800">
                                        &ldquo;{p.evidence_quote}&rdquo;
                                      </span>
                                      <div className="text-[10px] text-indigo-600 group-hover:underline font-semibold mt-1 flex items-center gap-1">
                                        Inspect source utterance in transcript →
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* 5. Linked Tasks (With status and whether link is confirmed) */}
                    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          <CheckCircle2 className="w-4 h-4 text-blue-600" />
                          Linked Execution Tasks ({drawerDetail.linked_tasks.length})
                        </div>
                        <span className="text-[11px] text-slate-500">
                          Implements this decision
                        </span>
                      </div>

                      {drawerDetail.linked_tasks.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">No tasks linked to this decision.</p>
                      ) : (
                        <div className="space-y-2">
                          {drawerDetail.linked_tasks.map((task) => {
                            const isConfirmed = task.link_confirmed ?? !task.provisional;
                            return (
                              <div
                                key={task.id}
                                className={`rounded-lg border p-3 text-xs bg-white space-y-2 ${
                                  isConfirmed
                                    ? "border-slate-200"
                                    : "border-amber-300 border-dashed bg-amber-50/20"
                                }`}
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <div className="flex items-center gap-2">
                                    <span className="font-bold text-slate-800">Task #{task.id}</span>
                                    {getTaskStatusBadge(task.status)}
                                    {isConfirmed ? (
                                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                        <Check className="w-3 h-3 text-emerald-600" />
                                        Confirmed Link
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                        <AlertCircle className="w-3 h-3 text-amber-600" />
                                        Unconfirmed / Provisional
                                      </span>
                                    )}
                                  </div>

                                  {task.tracker_ref && (
                                    <span className="font-mono text-[11px] font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100 flex items-center gap-1">
                                      {task.tracker_ref}
                                      {task.tracker_url && (
                                        <a
                                          href={task.tracker_url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="text-indigo-500 hover:text-indigo-700"
                                          onClick={(e) => e.stopPropagation()}
                                        >
                                          <ExternalLink className="w-3 h-3" />
                                        </a>
                                      )}
                                    </span>
                                  )}
                                </div>

                                <p className="text-slate-900 font-semibold">{task.title}</p>

                                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                                  <div className="flex items-center gap-1">
                                    <User className="w-3 h-3" />
                                    <span>{task.owner_name || "Unassigned"}</span>
                                  </div>
                                  <div className="flex items-center gap-1">
                                    <Calendar className="w-3 h-3" />
                                    <span>Due: {task.due_date || "No deadline"}</span>
                                  </div>
                                  {task.estimate_hours !== null && (
                                    <div className="flex items-center gap-1">
                                      <Clock className="w-3 h-3" />
                                      <span>{task.estimate_hours} hrs</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* 6. Version History */}
                    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 uppercase tracking-wider">
                          <FileText className="w-4 h-4 text-slate-600" />
                          Version History ({drawerDetail.version_history.length})
                        </div>
                      </div>

                      <div className="divide-y divide-slate-100 text-xs">
                        {drawerDetail.version_history.map((ver) => (
                          <div key={ver.id} className="py-2.5 space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-800">
                                Version {ver.version}
                              </span>
                              <span className="text-[11px] text-slate-500">
                                {ver.changed_at ? new Date(ver.changed_at).toLocaleString() : ""} by {ver.changed_by}
                              </span>
                            </div>
                            <p className="text-slate-700 leading-snug">{ver.text}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TRANSCRIPT QUOTE INSPECTOR MODAL */}
      {inspectingPremise && (
        <div className="fixed inset-0 z-60 overflow-y-auto">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={() => setInspectingPremise(null)}
          />

          <div className="flex min-h-full items-center justify-center p-4">
            <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <Quote className="w-4 h-4 text-indigo-600" />
                    Source Transcript Utterance
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Meeting: {inspectingPremise.meeting_title || "Transcript Dialogue"}
                  </p>
                </div>
                <button
                  onClick={() => setInspectingPremise(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
                <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-100 text-xs space-y-1">
                  <div className="font-semibold text-indigo-900">
                    Premise #{inspectingPremise.id}: {inspectingPremise.text}
                  </div>
                  <div className="text-indigo-700">
                    Quote citation: &ldquo;{inspectingPremise.evidence_quote}&rdquo;
                  </div>
                </div>

                {transcriptLoading ? (
                  <div className="space-y-2 animate-pulse py-4">
                    <div className="h-4 bg-slate-200 rounded w-1/2" />
                    <div className="h-12 bg-slate-100 rounded" />
                    <div className="h-12 bg-slate-100 rounded" />
                  </div>
                ) : transcriptUtterances.length > 0 ? (
                  <div className="space-y-3">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      Dialogue Excerpt Around Cited Statement:
                    </div>
                    {/* Find index of utterance matching quote or utterance_idx */}
                    {(() => {
                      const quote = inspectingPremise.evidence_quote?.toLowerCase() || "";
                      const matchingIdx = transcriptUtterances.findIndex((u) =>
                        u.text.toLowerCase().includes(quote) || u.idx === inspectingPremise.utterance_idx
                      );

                      // Display window around matching utterance
                      const start = Math.max(0, matchingIdx !== -1 ? matchingIdx - 2 : 0);
                      const end = Math.min(
                        transcriptUtterances.length,
                        matchingIdx !== -1 ? matchingIdx + 3 : 5
                      );
                      const windowUtterances = transcriptUtterances.slice(start, end);

                      return windowUtterances.map((u) => {
                        const isFocal =
                          (quote && u.text.toLowerCase().includes(quote)) ||
                          u.idx === inspectingPremise.utterance_idx;

                        return (
                          <div
                            key={u.id || u.idx}
                            className={`p-3 rounded-xl border text-xs transition-all ${
                              isFocal
                                ? "border-indigo-300 bg-indigo-50/80 shadow-xs ring-1 ring-indigo-200"
                                : "border-slate-200 bg-white"
                            }`}
                          >
                            <div className="flex items-center justify-between text-[11px] mb-1 font-semibold">
                              <span className={isFocal ? "text-indigo-900" : "text-slate-800"}>
                                {u.speaker_name || "Speaker"}
                              </span>
                              <span className="text-slate-400 font-mono">
                                {u.start_ts !== undefined && u.start_ts !== null ? `${u.start_ts}s` : `Utterance #${u.idx}`}
                              </span>
                            </div>
                            <p
                              className={`leading-relaxed ${
                                isFocal ? "text-indigo-950 font-medium" : "text-slate-700"
                              }`}
                            >
                              {u.text}
                            </p>
                            {isFocal && (
                              <div className="mt-2 pt-1.5 border-t border-indigo-200/60 text-[10px] text-indigo-700 font-semibold flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3 text-indigo-600" />
                                Exact quote matched inside this utterance
                              </div>
                            )}
                          </div>
                        );
                      });
                    })()}
                  </div>
                ) : (
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-600">
                    <p className="font-semibold text-slate-800 mb-1">Evidence Citation:</p>
                    <p className="italic font-serif">&ldquo;{inspectingPremise.evidence_quote}&rdquo;</p>
                    <p className="text-[11px] text-slate-400 mt-2">
                      Full meeting transcript can be inspected in the Review Queue.
                    </p>
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
                {inspectingPremise.meeting_id ? (
                  <Link
                    href={`/review?meeting_id=${inspectingPremise.meeting_id}`}
                    className="text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1"
                  >
                    Open Meeting #{inspectingPremise.meeting_id} in Review Queue <ExternalLink className="w-3 h-3" />
                  </Link>
                ) : (
                  <span />
                )}
                <button
                  onClick={() => setInspectingPremise(null)}
                  className="px-3.5 py-1.5 rounded-lg bg-slate-200 text-slate-800 font-semibold hover:bg-slate-300 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
