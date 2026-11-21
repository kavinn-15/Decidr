"use client";

import React, { useState, useEffect } from "react";
import {
  Calendar,
  User,
  Clock,
  AlertTriangle,
  ShieldAlert,
  Mail,
  Send,
  CheckCircle2,
  AlertCircle,
  FileText,
  Inbox,
  ExternalLink,
  ChevronRight,
  RefreshCw,
  Eye,
  Info,
} from "lucide-react";
import {
  fetchPeople,
  fetchMyWeek,
  fetchDigest,
  fetchOutbox,
  triggerRunReminders,
  triggerRunDigest,
  PersonSummary,
  MyWeekResponse,
  DigestResponse,
  OutboxItem,
} from "@/lib/api";
import { getUser } from "@/lib/auth";

export default function MyWeekPage() {
  const [people, setPeople] = useState<PersonSummary[]>([]);
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null);
  const [simulatedDate, setSimulatedDate] = useState<string>(() => new Date().toISOString().split("T")[0]);
  const [activeTab, setActiveTab] = useState<"week" | "digest" | "outbox">("week");
  const [digestViewMode, setDigestViewMode] = useState<"html" | "text">("html");

  const [weekData, setWeekData] = useState<MyWeekResponse | null>(null);
  const [outboxItems, setOutboxItems] = useState<OutboxItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [expandedOutboxId, setExpandedOutboxId] = useState<number | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // 1. Load People on Mount
  useEffect(() => {
    async function loadRoster() {
      try {
        const roster = await fetchPeople();
        setPeople(roster);
        if (roster.length > 0) {
          const currentUser = getUser();
          const matched = currentUser
            ? roster.find(
                (p) =>
                  (p.email && currentUser.email && p.email.toLowerCase() === currentUser.email.toLowerCase()) ||
                  (p.name && currentUser.full_name && p.name.toLowerCase() === currentUser.full_name.toLowerCase())
              )
            : null;
          setSelectedPersonId(matched ? matched.id : roster[0].id);
        }
      } catch (err: any) {
        showToast(err.message || "Failed to load people roster");
      }
    }
    loadRoster();
  }, []);

  // 2. Load My Week Data when person or simulated date changes
  useEffect(() => {
    if (!selectedPersonId) return;
    loadPersonData(selectedPersonId, simulatedDate);
  }, [selectedPersonId, simulatedDate]);

  // 3. Load Outbox when tab switched to outbox
  useEffect(() => {
    if (activeTab === "outbox") {
      loadOutboxData();
    }
  }, [activeTab]);

  const loadPersonData = async (personId: number, asOf: string) => {
    try {
      setLoading(true);
      const data = await fetchMyWeek(personId, asOf);
      setWeekData(data);
    } catch (err: any) {
      showToast(err.message || "Failed to load weekly data");
    } finally {
      setLoading(false);
    }
  };

  const loadOutboxData = async () => {
    try {
      const items = await fetchOutbox(undefined, 50);
      setOutboxItems(items);
    } catch (err: any) {
      showToast(err.message || "Failed to load outbox items");
    }
  };

  const handleSimulateReminders = async () => {
    try {
      const nowIso = `${simulatedDate}T08:30:00Z`;
      const res = await triggerRunReminders(nowIso);
      showToast(`Reminders simulated: ${res.sent_count} sent, ${res.skipped_count} skipped.`);
      loadOutboxData();
    } catch (err: any) {
      showToast(err.message || "Reminders simulation failed");
    }
  };

  const handleQueueDigest = async () => {
    try {
      const res = await triggerRunDigest(simulatedDate);
      showToast(`Weekly digest queued to Outbox for ${res.digests_created} members.`);
      loadOutboxData();
    } catch (err: any) {
      showToast(err.message || "Failed to queue digest");
    }
  };

  const selectedPerson = people.find((p) => p.id === selectedPersonId);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header & Person Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
            <Calendar className="w-6 h-6 text-indigo-600" />
            My Week
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Personal commitments, upcoming deadlines, decision impacts, and execution safety digest.
          </p>
        </div>

        {/* Controls: Person Picker & Reference Date */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-2xs">
            <User className="w-4 h-4 text-slate-400" />
            <select
              value={selectedPersonId || ""}
              onChange={(e) => setSelectedPersonId(Number(e.target.value))}
              className="text-xs font-semibold text-slate-800 bg-transparent focus:outline-none cursor-pointer"
            >
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.email})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-2xs">
            <Clock className="w-4 h-4 text-slate-400" />
            <span className="text-[11px] font-medium text-slate-500">As of:</span>
            <input
              type="date"
              value={simulatedDate}
              onChange={(e) => setSimulatedDate(e.target.value)}
              className="text-xs font-semibold text-slate-800 focus:outline-none cursor-pointer"
            />
          </div>

          <button
            onClick={() => selectedPersonId && loadPersonData(selectedPersonId, simulatedDate)}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex items-center justify-between border-b border-slate-200">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("week")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-all ${
              activeTab === "week"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Calendar className="w-4 h-4" />
            Weekly Overview
          </button>

          <button
            onClick={() => setActiveTab("digest")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-all ${
              activeTab === "digest"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Mail className="w-4 h-4" />
            Digest Preview
          </button>

          <button
            onClick={() => setActiveTab("outbox")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-all ${
              activeTab === "outbox"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Inbox className="w-4 h-4" />
            Outbox Viewer
          </button>
        </div>

        {/* Quick Simulation Trigger Buttons */}
        <div className="flex items-center gap-2 mb-2">
          <button
            onClick={handleSimulateReminders}
            className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg shadow-2xs flex items-center gap-1.5 transition-colors"
          >
            <Clock className="w-3.5 h-3.5 text-indigo-600" />
            Run Reminders (08:30)
          </button>
          <button
            onClick={handleQueueDigest}
            className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg shadow-2xs flex items-center gap-1.5 transition-colors"
          >
            <Send className="w-3.5 h-3.5 text-emerald-600" />
            Queue Weekly Digest
          </button>
        </div>
      </div>

      {/* TAB 1: WEEKLY OVERVIEW */}
      {activeTab === "week" && (
        <div className="space-y-6">
          {/* 1. HIGHLIGHTED SECTION: WORK RESTING ON BROKEN OR SHAKY PREMISES */}
          {weekData && weekData.shaky_broken && weekData.shaky_broken.length > 0 && (
            <div className="rounded-2xl border-2 border-rose-300 bg-rose-50/60 p-5 shadow-xs transition-all">
              <div className="flex items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2.5">
                  <span className="p-2 rounded-lg bg-rose-600 text-white shadow-2xs">
                    <ShieldAlert className="w-5 h-5" />
                  </span>
                  <div>
                    <h2 className="text-base font-bold text-rose-950">
                      Work Resting on Broken or Shaky Premises
                    </h2>
                    <p className="text-xs text-rose-800">
                      These tasks belong to your commitments, but foundational premises under their decisions have been compromised.
                    </p>
                  </div>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-rose-200/80 text-rose-900">
                  {weekData.shaky_broken.length} Compromised {weekData.shaky_broken.length === 1 ? "Task" : "Tasks"}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                {weekData.shaky_broken.map((item) => (
                  <div
                    key={item.task_id}
                    className="p-4 bg-white rounded-xl border border-rose-200 shadow-2xs flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="text-xs font-bold text-slate-900">
                          Task #{item.task_id}: {item.task_title}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                            item.premise_status === "broken"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {item.premise_status}
                        </span>
                      </div>

                      <div className="text-xs text-slate-600 space-y-1 mb-2">
                        <div>
                          <span className="font-semibold text-slate-700">Linked Decision: </span>
                          <span>D{item.decision_id} ("{item.decision_text}")</span>
                        </div>
                        <div>
                          <span className="font-semibold text-slate-700">Premise P{item.premise_id}: </span>
                          <span className="italic text-slate-800">"{item.premise_text}"</span>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-rose-100 flex items-center justify-between text-[11px] text-rose-900 font-medium">
                      <span>Due: {item.due_date || "No deadline"}</span>
                      <span className="bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                        {item.reason}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 2. OVERDUE TASKS & TASKS BY DAY */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Left Column: Overdue List */}
            <div className="lg:col-span-1 space-y-4">
              <div className="rounded-2xl border border-rose-200 bg-white p-4 shadow-2xs">
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-rose-100">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-rose-900 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-rose-600" />
                    Overdue Tasks ({weekData?.overdue.length || 0})
                  </h3>
                </div>

                {weekData && weekData.overdue.length > 0 ? (
                  <div className="space-y-2.5">
                    {weekData.overdue.map((t) => (
                      <div
                        key={t.id}
                        className="p-3 rounded-xl border border-rose-200 bg-rose-50/40 text-xs space-y-1.5"
                      >
                        <div className="font-semibold text-slate-900">{t.title}</div>
                        <div className="flex items-center justify-between text-[11px] text-rose-800 font-medium">
                          <span>Due: {t.due_date}</span>
                          <span className="px-1.5 py-0.5 rounded bg-rose-200/60 font-bold uppercase text-[10px]">
                            Overdue
                          </span>
                        </div>
                        {t.tracker_ref && (
                          <div className="text-[10px] text-slate-500 font-mono">
                            Ticket: {t.tracker_ref}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic py-2">No overdue tasks.</p>
                )}
              </div>
            </div>

            {/* Right Columns: Tasks by Day */}
            <div className="lg:col-span-3 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-slate-900">
                  Tasks by Day (Week of {weekData?.start_of_week} to {weekData?.end_of_week})
                </h3>
                <span className="text-xs text-slate-500 font-medium">
                  {selectedPerson?.name}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
                {weekData?.days.slice(0, 5).map((day) => (
                  <div
                    key={day.date}
                    className={`rounded-2xl border p-3 flex flex-col min-h-[220px] transition-all ${
                      day.is_today
                        ? "border-indigo-400 bg-indigo-50/20 shadow-xs ring-1 ring-indigo-200"
                        : "border-slate-200 bg-white shadow-2xs"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-slate-100">
                      <span className="text-xs font-bold text-slate-900">{day.day_name}</span>
                      <span
                        className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                          day.is_today
                            ? "bg-indigo-600 text-white"
                            : "text-slate-500 bg-slate-100"
                        }`}
                      >
                        {day.date.slice(5)}
                      </span>
                    </div>

                    <div className="space-y-2 flex-1 overflow-y-auto">
                      {day.tasks.length > 0 ? (
                        day.tasks.map((task) => (
                          <div
                            key={task.id}
                            className="p-2.5 rounded-xl border border-slate-200 bg-white hover:border-slate-300 text-xs space-y-1.5 shadow-2xs transition-all"
                          >
                            <div className="font-semibold text-slate-800 leading-snug">
                              {task.title}
                            </div>

                            {/* Invariant Badges: Provisional, At Risk, Needs Owner */}
                            <div className="flex flex-wrap items-center gap-1 pt-1">
                              {task.provisional && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-200 uppercase tracking-wider">
                                  Provisional
                                </span>
                              )}
                              {task.at_risk && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200 uppercase tracking-wider">
                                  At Risk
                                </span>
                              )}
                              {task.needs_owner && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200 uppercase tracking-wider">
                                  Needs Owner
                                </span>
                              )}
                            </div>

                            {task.tracker_ref && (
                              <div className="text-[10px] text-slate-400 font-mono pt-1">
                                Ref: {task.tracker_ref}
                              </div>
                            )}
                          </div>
                        ))
                      ) : (
                        <div className="h-full flex items-center justify-center text-slate-400 text-xs italic">
                          No tasks
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: DIGEST PREVIEW */}
      {activeTab === "digest" && weekData && (
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="font-bold text-sm">Weekly Digest Preview: {selectedPerson?.name}</h3>
                <p className="text-xs text-slate-400">
                  Scheduled for dispatch every Monday at 09:00 to {selectedPerson?.email}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 bg-slate-800 p-1 rounded-lg border border-slate-700 text-xs">
              <button
                onClick={() => setDigestViewMode("html")}
                className={`px-3 py-1 rounded-md font-medium transition-all ${
                  digestViewMode === "html"
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                HTML Rendered
              </button>
              <button
                onClick={() => setDigestViewMode("text")}
                className={`px-3 py-1 rounded-md font-medium transition-all ${
                  digestViewMode === "text"
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Plain Text
              </button>
            </div>
          </div>

          <div className="p-6 bg-slate-50 min-h-[500px]">
            {digestViewMode === "html" ? (
              <div className="bg-white rounded-xl border border-slate-200 p-2 shadow-2xs overflow-hidden">
                <iframe
                  title="Digest Preview"
                  srcDoc={weekData.digest_preview.html}
                  className="w-full min-h-[550px] border-0 rounded-lg"
                />
              </div>
            ) : (
              <pre className="bg-slate-900 text-emerald-300 p-5 rounded-xl text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed shadow-inner">
                {weekData.digest_preview.text}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: OUTBOX VIEWER */}
      {activeTab === "outbox" && (
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Inbox className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="font-bold text-sm">Outbound Message Outbox</h3>
                <p className="text-xs text-slate-400">
                  All dispatched and queued reminders, alerts, and digest deliveries
                </p>
              </div>
            </div>
            <button
              onClick={loadOutboxData}
              className="px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 text-slate-500 uppercase font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Channel</th>
                  <th className="px-4 py-3">Recipient</th>
                  <th className="px-4 py-3">Subject</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {outboxItems.length > 0 ? (
                  outboxItems.map((item) => (
                    <React.Fragment key={item.id}>
                      <tr className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-4 py-3 font-mono text-slate-400">#{item.id}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 rounded bg-slate-100 font-semibold text-slate-700 uppercase text-[10px]">
                            {item.channel}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-semibold text-slate-800">{item.to_addr}</td>
                        <td className="px-4 py-3 text-slate-700 max-w-xs truncate font-medium">
                          {item.subject || "(No subject)"}
                        </td>
                        <td className="px-4 py-3 text-slate-500">
                          {item.created_at ? new Date(item.created_at).toLocaleString() : "N/A"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              item.sent
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {item.sent ? "Sent" : "Queued"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() =>
                              setExpandedOutboxId(expandedOutboxId === item.id ? null : item.id)
                            }
                            className="text-indigo-600 hover:text-indigo-800 font-semibold text-xs inline-flex items-center gap-1"
                          >
                            {expandedOutboxId === item.id ? "Hide" : "View"}
                          </button>
                        </td>
                      </tr>

                      {expandedOutboxId === item.id && (
                        <tr className="bg-slate-50/50">
                          <td colSpan={7} className="px-6 py-4">
                            <div className="p-4 bg-slate-900 text-slate-200 rounded-xl font-mono text-xs whitespace-pre-wrap max-h-64 overflow-y-auto border border-slate-800 shadow-inner">
                              {item.body}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-400 italic">
                      No outbound messages recorded in outbox yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TOAST NOTIFICATION */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-slate-900 text-white text-xs font-medium px-4 py-3 rounded-xl shadow-xl border border-slate-800 flex items-center gap-2 animate-fade-in">
          <Info className="w-4 h-4 text-indigo-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
