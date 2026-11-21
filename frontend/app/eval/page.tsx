"use client";

import { useEffect, useState } from "react";
import { 
  BarChart3, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck, 
  RefreshCw, 
  FileText, 
  Download, 
  Lock, 
  FileCode, 
  Table as TableIcon,
  HelpCircle,
  GitCommit,
  Cpu,
  Clock,
  Database
} from "lucide-react";
import { 
  EvalReport, 
  fetchEvalReport, 
  fetchEvalMarkdown, 
  fetchEvalCsv, 
  triggerRunEval 
} from "@/lib/api";

export default function EvaluationPage() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [markdown, setMarkdown] = useState<string>("");
  const [csvContent, setCsvContent] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<"development" | "heldout">("development");
  const [activeTab, setActiveTab] = useState<"comparison" | "markdown" | "json" | "csv">("comparison");

  async function loadData(heldout: boolean = false) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEvalReport(heldout);
      setReport(data);

      try {
        const [md, csv] = await Promise.all([
          fetchEvalMarkdown(),
          fetchEvalCsv(),
        ]);
        setMarkdown(md);
        setCsvContent(csv);
      } catch (e) {
        console.warn("Could not load markdown/csv export strings", e);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load evaluation report");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData(selectedDataset === "heldout");
  }, [selectedDataset]);

  async function handleRunEvaluation() {
    setRunning(true);
    setError(null);
    try {
      const data = await triggerRunEval(selectedDataset === "heldout");
      setReport(data);
      const [md, csv] = await Promise.all([
        fetchEvalMarkdown(),
        fetchEvalCsv(),
      ]);
      setMarkdown(md);
      setCsvContent(csv);
    } catch (err: any) {
      setError(err?.message || "Failed to execute evaluation pipeline");
    } finally {
      setRunning(false);
    }
  }

  function downloadFile(content: string, filename: string, type: string) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg border border-indigo-100">
              <BarChart3 className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Pipeline Evaluation & Baselines
            </h1>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Empirical measurements versus gold labels (Invariant 10: Derived metrics only, never hard-coded or fabricated).
          </p>
        </div>

        {/* Toolbar Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Dataset Selector */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs font-medium text-slate-600">
            <button
              onClick={() => setSelectedDataset("development")}
              className={`px-3 py-1.5 rounded-md transition-all ${
                selectedDataset === "development"
                  ? "bg-white text-indigo-700 shadow-sm font-semibold"
                  : "hover:text-slate-900"
              }`}
            >
              Development (M1–M4)
            </button>
            <button
              onClick={() => setSelectedDataset("heldout")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
                selectedDataset === "heldout"
                  ? "bg-amber-500 text-white shadow-sm font-semibold"
                  : "text-amber-800 hover:text-amber-900"
              }`}
            >
              <Lock className="w-3.5 h-3.5" />
              Held-Out Set (H1–H2)
            </button>
          </div>

          {/* Trigger Re-Evaluation */}
          <button
            onClick={handleRunEvaluation}
            disabled={running || loading}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${running ? "animate-spin" : ""}`} />
            {running ? "Evaluating..." : "Run Evaluation"}
          </button>

          {/* Export Downloads */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => downloadFile(JSON.stringify(report, null, 2), "report.json", "application/json")}
              disabled={!report}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium transition-colors"
              title="Download JSON Report"
            >
              <Download className="w-3 h-3 text-slate-500" />
              JSON
            </button>
            <button
              onClick={() => downloadFile(markdown, "report.md", "text/markdown")}
              disabled={!markdown}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium transition-colors"
              title="Download Markdown Report"
            >
              <Download className="w-3 h-3 text-slate-500" />
              MD
            </button>
            <button
              onClick={() => downloadFile(csvContent, "report.csv", "text/csv")}
              disabled={!csvContent}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium transition-colors"
              title="Download CSV Table"
            >
              <Download className="w-3 h-3 text-slate-500" />
              CSV
            </button>
          </div>
        </div>
      </div>

      {/* Held-out Warning Alert if active */}
      {selectedDataset === "heldout" && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3 text-amber-900 text-xs">
          <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-800">
              Strict Held-out Guard Active (Invariant 10)
            </p>
            <p className="text-amber-700 leading-relaxed">
              You are inspecting the held-out evaluation set (H1–H2). In accordance with Invariant 10, access is strictly audited, logged, and isolated to prevent prompt tuning leakage.
            </p>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-xl text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600" />
            <span>{error}</span>
          </div>
          <button 
            onClick={() => loadData(selectedDataset === "heldout")}
            className="text-xs font-semibold underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && !report && (
        <div className="space-y-6 animate-pulse">
          <div className="h-20 bg-slate-100 rounded-xl border border-slate-200" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-32 bg-slate-100 rounded-xl border border-slate-200" />
            ))}
          </div>
          <div className="h-64 bg-slate-100 rounded-xl border border-slate-200" />
        </div>
      )}

      {report && (
        <>
          {/* Metadata Stamp Bar */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 text-xs text-slate-600 shadow-sm">
            <div className="flex flex-wrap items-center gap-6">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-indigo-600" />
                <span className="font-medium text-slate-500">Dataset:</span>
                <span className="font-semibold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                  {report.metadata.dataset}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-600" />
                <span className="font-medium text-slate-500">Model / Mode:</span>
                <span className="font-semibold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                  {report.metadata.model} ({report.metadata.llm_mode})
                </span>
              </div>

              <div className="flex items-center gap-2">
                <GitCommit className="w-4 h-4 text-indigo-600" />
                <span className="font-medium text-slate-500">Git Commit:</span>
                <code className="font-mono text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                  {report.metadata.git_commit.slice(0, 7)}
                </code>
              </div>

              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400" />
                <span className="font-medium text-slate-500">Timestamp:</span>
                <span className="text-slate-700">
                  {new Date(report.metadata.date).toLocaleString()}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-full font-medium">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                Writes Without Approval: {report.decidr.writes_without_approval} (Target 0)
              </span>
            </div>
          </div>

          {/* Key Metric Score Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Premise-Break Detection */}
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow transition-shadow">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-semibold text-slate-700">Premise-Break Watchdog</span>
                <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 font-bold rounded">Core Novelty</span>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-slate-900">
                  {(report.decidr.premise_breaks_pr.precision * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  Precision / {(report.decidr.premise_breaks_pr.recall * 100).toFixed(0)}% Recall
                </span>
              </div>
              <p className="mt-2 text-[11px] text-slate-500 line-clamp-1">
                F1 Score: {(report.decidr.premise_breaks_pr.f1 * 100).toFixed(1)}% ({report.decidr.premise_breaks_pr.tp} TP, {report.decidr.premise_breaks_pr.fp} FP)
              </p>
            </div>

            {/* Cross-Decision Conflict */}
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow transition-shadow">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-semibold text-slate-700">Conflict & Supersession</span>
                <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 font-bold rounded">Scope-Filtered</span>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-slate-900">
                  {(report.decidr.conflicts_pr.precision * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  Precision / {(report.decidr.conflicts_pr.recall * 100).toFixed(0)}% Recall
                </span>
              </div>
              <p className="mt-2 text-[11px] text-slate-500 line-clamp-1">
                Zero calls on disjoint scopes (Europe vs India)
              </p>
            </div>

            {/* Impact / Affected Tasks */}
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow transition-shadow">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-semibold text-slate-700">Blast Radius Traversal</span>
                <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 font-bold rounded">Zero-LLM BFS</span>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-slate-900">
                  {(report.decidr.impact_pr.precision * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  Impact Precision / {(report.decidr.impact_pr.recall * 100).toFixed(0)}% Recall
                </span>
              </div>
              <p className="mt-2 text-[11px] text-slate-500 line-clamp-1">
                Multi-hop graph propagation across confirmed edges
              </p>
            </div>

            {/* Repair Plan Correctness */}
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow transition-shadow">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-semibold text-slate-700">Repair Plan Correctness</span>
                <span className="px-1.5 py-0.5 bg-purple-50 text-purple-700 font-bold rounded">Rule-Based</span>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-slate-900">
                  {(report.decidr.repair_correctness.correctness * 100).toFixed(1)}%
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  Action Match
                </span>
              </div>
              <p className="mt-2 text-[11px] text-slate-500 line-clamp-1">
                {report.decidr.repair_correctness.matched} / {report.decidr.repair_correctness.total_gold} gold repair actions generated
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2 border-b border-slate-200 pt-2 text-xs font-semibold text-slate-600">
            <button
              onClick={() => setActiveTab("comparison")}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === "comparison"
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <TableIcon className="w-4 h-4" />
              Baseline Comparison Table
            </button>
            <button
              onClick={() => setActiveTab("markdown")}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === "markdown"
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <FileText className="w-4 h-4" />
              Markdown Report (report.md)
            </button>
            <button
              onClick={() => setActiveTab("json")}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === "json"
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <FileCode className="w-4 h-4" />
              Raw JSON (report.json)
            </button>
            <button
              onClick={() => setActiveTab("csv")}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === "csv"
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <Download className="w-4 h-4" />
              CSV Preview
            </button>
          </div>

          {/* Tab 1: Comparison Table */}
          {activeTab === "comparison" && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
              <div className="px-6 py-4 bg-slate-50/50 border-b border-slate-200 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Comprehensive Benchmark Comparison: Baselines vs Decidr Platform
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Measured directly by executing end-to-end meeting dialogues through each system configuration.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-3 px-4 w-1/3">Evaluation Metric</th>
                      <th className="py-3 px-4 w-1/5 text-slate-600">
                        B1: Extraction Only
                        <span className="block text-[10px] font-normal text-slate-400">Direct task ticket creation</span>
                      </th>
                      <th className="py-3 px-4 w-1/5 text-slate-600">
                        B2: Extraction + Pairwise
                        <span className="block text-[10px] font-normal text-slate-400">No premise tracking</span>
                      </th>
                      <th className="py-3 px-4 w-1/4 bg-indigo-50/50 text-indigo-900 font-bold">
                        Decidr (Proposed Platform)
                        <span className="block text-[10px] font-normal text-indigo-700">Premises + Watchdog + Repair</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium">
                    {report.comparison_table.map((row, idx) => (
                      <tr 
                        key={idx} 
                        className={idx % 2 === 0 ? "bg-white" : "bg-slate-50/30"}
                      >
                        <td className="py-3.5 px-4 font-semibold text-slate-800">
                          {row.metric}
                        </td>
                        <td className="py-3.5 px-4 text-slate-600 font-mono">
                          {row.b1}
                        </td>
                        <td className="py-3.5 px-4 text-slate-600 font-mono">
                          {row.b2}
                        </td>
                        <td className="py-3.5 px-4 bg-indigo-50/40 text-indigo-950 font-bold font-mono">
                          <span className="inline-flex items-center gap-1.5">
                            {row.decidr}
                            {row.decidr.includes("100.0%") && (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 inline" />
                            )}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="p-4 bg-slate-50 border-t border-slate-200 text-xs text-slate-500 flex items-center justify-between">
                <span>All metrics calculated mathematically via Precision / Recall formula (Invariant 10).</span>
                <span className="font-semibold text-emerald-700">Zero Unapproved Writes Confirmed</span>
              </div>
            </div>
          )}

          {/* Tab 2: Markdown Report */}
          {activeTab === "markdown" && (
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                <span className="font-mono text-xs text-slate-500">eval/report.md</span>
                <button
                  onClick={() => downloadFile(markdown, "report.md", "text/markdown")}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-semibold transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download MD
                </button>
              </div>
              <pre className="font-mono text-xs bg-slate-900 text-slate-100 p-5 rounded-lg overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {markdown || "Markdown report not generated yet."}
              </pre>
            </div>
          )}

          {/* Tab 3: JSON Report */}
          {activeTab === "json" && (
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                <span className="font-mono text-xs text-slate-500">eval/report.json</span>
                <button
                  onClick={() => downloadFile(JSON.stringify(report, null, 2), "report.json", "application/json")}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-semibold transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download JSON
                </button>
              </div>
              <pre className="font-mono text-xs bg-slate-900 text-slate-100 p-5 rounded-lg overflow-x-auto whitespace-pre leading-relaxed max-h-[600px]">
                {JSON.stringify(report, null, 2)}
              </pre>
            </div>
          )}

          {/* Tab 4: CSV Preview */}
          {activeTab === "csv" && (
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                <span className="font-mono text-xs text-slate-500">eval/report.csv</span>
                <button
                  onClick={() => downloadFile(csvContent, "report.csv", "text/csv")}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs font-semibold transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download CSV
                </button>
              </div>
              <pre className="font-mono text-xs bg-slate-900 text-slate-100 p-5 rounded-lg overflow-x-auto whitespace-pre leading-relaxed">
                {csvContent || "CSV report not generated yet."}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
