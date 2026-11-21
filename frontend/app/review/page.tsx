"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Edit3,
  Calendar,
  User,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  HelpCircle,
  Sparkles,
  Link2,
  Clock,
  ArrowRight,
  AlertCircle,
  FileText,
  UserCheck,
  Send,
  X,
  Info,
} from "lucide-react";
import {
  fetchMeetings,
  fetchUtterances,
  fetchReviewQueue,
  approveDecision,
  rejectDecision,
  editDecision,
  approvePremise,
  rejectPremise,
  editPremise,
  approveAction,
  rejectAction,
  editAction,
  confirmLink,
  rejectLink,
  confirmAlert,
  dismissAlert,
  MeetingSummary,
  UtteranceItem,
  ReviewQueueResponse,
  AlertCard,
  DecisionCard,
  PremiseCard,
  ActionCard,
  LinkCard,
  PersonItem,
} from "@/lib/api";

interface Toast {
  id: string;
  type: "success" | "error" | "info";
  message: string;
}

type CardType = "alert" | "decision" | "premise" | "action" | "link";

interface FocusedCardRef {
  type: CardType;
  id: number;
  evidence_quote?: string;
  utterance_id?: number | null;
}

export default function ReviewPage() {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [selectedMeetingId, setSelectedMeetingId] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [utterances, setUtterances] = useState<UtteranceItem[]>([]);
  const [queueData, setQueueData] = useState<ReviewQueueResponse | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Selection & Focus
  const [focusedCard, setFocusedCard] = useState<FocusedCardRef | null>(null);
  const [activeQuote, setActiveQuote] = useState<string | null>(null);

  // Modals & Dialogs
  const [missingFieldAction, setMissingFieldAction] = useState<ActionCard | null>(null);
  const [assigneeId, setAssigneeId] = useState<number | null>(null);
  const [assignDeadline, setAssignDeadline] = useState<string>("");

  const [editItem, setEditItem] = useState<{
    type: CardType;
    id: number;
    text: string;
    owner_id?: number | null;
    deadline?: string;
    estimate_hours?: number;
    scope_region?: string;
    scope_project?: string;
  } | null>(null);

  const transcriptContainerRef = useRef<HTMLDivElement>(null);
  const cardsContainerRef = useRef<HTMLDivElement>(null);

  const addToast = (message: string, type: "success" | "error" | "info" = "info") => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  // Load Meetings
  useEffect(() => {
    async function loadMeetings() {
      try {
        setLoading(true);
        const data = await fetchMeetings();
        setMeetings(data);
        if (data.length > 0) {
          // Select meeting in review state, or first meeting
          const reviewMeeting = data.find((m) => m.status === "review") || data[0];
          setSelectedMeetingId(reviewMeeting.id);
        }
      } catch (err: any) {
        addToast(err.message || "Failed to load meetings", "error");
      } finally {
        setLoading(false);
      }
    }
    loadMeetings();
  }, []);

  // Load meeting review data
  const loadMeetingData = useCallback(async (meetingId: number) => {
    try {
      setLoading(true);
      const [utts, reviewQueue] = await Promise.all([
        fetchUtterances(meetingId),
        fetchReviewQueue(meetingId),
      ]);
      setUtterances(utts);
      setQueueData(reviewQueue);

      // Auto-focus first card
      if (reviewQueue.alerts.length > 0) {
        setFocusedCard({
          type: "alert",
          id: reviewQueue.alerts[0].id,
          evidence_quote: reviewQueue.alerts[0].old_quote || undefined,
          utterance_id: reviewQueue.alerts[0].utterance_id,
        });
      } else if (reviewQueue.decisions.length > 0) {
        setFocusedCard({
          type: "decision",
          id: reviewQueue.decisions[0].item_id,
          evidence_quote: reviewQueue.decisions[0].evidence_quote,
          utterance_id: reviewQueue.decisions[0].utterance_id,
        });
      } else if (reviewQueue.actions.length > 0) {
        setFocusedCard({
          type: "action",
          id: reviewQueue.actions[0].item_id,
          evidence_quote: reviewQueue.actions[0].evidence_quote,
          utterance_id: reviewQueue.actions[0].utterance_id,
        });
      }
    } catch (err: any) {
      addToast(err.message || "Failed to load review items", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedMeetingId !== null) {
      loadMeetingData(selectedMeetingId);
    }
  }, [selectedMeetingId, loadMeetingData]);

  // Scroll to utterance when card selected
  const handleSelectCard = (
    type: CardType,
    id: number,
    quote?: string,
    uttId?: number | null
  ) => {
    setFocusedCard({ type, id, evidence_quote: quote, utterance_id: uttId });
    if (quote) {
      setActiveQuote(quote);
    }
    if (uttId && transcriptContainerRef.current) {
      const el = document.getElementById(`utterance-${uttId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  };

  // Scroll to card when quote clicked in transcript
  const handleQuoteClick = (quote: string, cardType: CardType, cardId: number) => {
    setActiveQuote(quote);
    setFocusedCard({ type: cardType, id: cardId, evidence_quote: quote });
    const cardEl = document.getElementById(`card-${cardType}-${cardId}`);
    if (cardEl) {
      cardEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  // --- Card Action Handlers ---

  const handleApproveDecision = async (itemId: number) => {
    try {
      await approveDecision(itemId);
      addToast("Decision approved and versioned.", "success");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleRejectDecision = async (itemId: number) => {
    try {
      await rejectDecision(itemId);
      addToast("Decision rejected.", "info");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleApprovePremise = async (premiseId: number) => {
    try {
      await approvePremise(premiseId);
      addToast("Premise confirmed and status set to holding.", "success");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleRejectPremise = async (premiseId: number) => {
    try {
      await rejectPremise(premiseId);
      addToast("Premise rejected (will never be used).", "info");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleApproveActionClick = (action: ActionCard) => {
    if (action.needs_owner || action.needs_deadline) {
      setMissingFieldAction(action);
      setAssigneeId(action.owner_id || null);
      setAssignDeadline(action.deadline || "");
    } else {
      executeApproveAction(action.item_id, { approve_unassigned: false });
    }
  };

  const executeApproveAction = async (
    itemId: number,
    opts: { owner_id?: number | null; deadline?: string | null; approve_unassigned?: boolean }
  ) => {
    try {
      const res = await approveAction(itemId, opts);
      const ticketRef = res.tracker_ref || "Issue";
      const provNotice = res.provisional ? " (Provisional ticket created)" : "";
      addToast(`Action approved! Ticket ${ticketRef} created${provNotice}.`, "success");
      setMissingFieldAction(null);
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleRejectAction = async (itemId: number) => {
    try {
      await rejectAction(itemId);
      addToast("Action rejected (0 external tracker calls).", "info");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleConfirmLink = async (linkId: number) => {
    try {
      await confirmLink(linkId);
      addToast("Link confirmed.", "success");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleRejectLink = async (linkId: number) => {
    try {
      await rejectLink(linkId);
      addToast("Link unconfirmed.", "info");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleConfirmAlert = async (alertId: number) => {
    try {
      await confirmAlert(alertId);
      addToast("Alert confirmed.", "success");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  const handleDismissAlert = async (alertId: number) => {
    try {
      await dismissAlert(alertId);
      addToast("Alert dismissed.", "info");
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  // --- Keyboard Shortcuts (A, E, R, Arrows) ---
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts if user is typing in form inputs
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        missingFieldAction !== null ||
        editItem !== null
      ) {
        return;
      }

      if (!focusedCard || !queueData) return;

      const key = e.key.toUpperCase();

      if (key === "A") {
        e.preventDefault();
        if (focusedCard.type === "decision") {
          handleApproveDecision(focusedCard.id);
        } else if (focusedCard.type === "premise") {
          handleApprovePremise(focusedCard.id);
        } else if (focusedCard.type === "action") {
          const act = queueData.actions.find((a) => a.item_id === focusedCard.id);
          if (act) handleApproveActionClick(act);
        } else if (focusedCard.type === "alert") {
          handleConfirmAlert(focusedCard.id);
        } else if (focusedCard.type === "link") {
          handleConfirmLink(focusedCard.id);
        }
      } else if (key === "R") {
        e.preventDefault();
        if (focusedCard.type === "decision") {
          handleRejectDecision(focusedCard.id);
        } else if (focusedCard.type === "premise") {
          handleRejectPremise(focusedCard.id);
        } else if (focusedCard.type === "action") {
          handleRejectAction(focusedCard.id);
        } else if (focusedCard.type === "alert") {
          handleDismissAlert(focusedCard.id);
        } else if (focusedCard.type === "link") {
          handleRejectLink(focusedCard.id);
        }
      } else if (key === "E") {
        e.preventDefault();
        if (focusedCard.type === "decision") {
          const dec = queueData.decisions.find((d) => d.item_id === focusedCard.id);
          if (dec) {
            setEditItem({
              type: "decision",
              id: dec.item_id,
              text: dec.text,
              scope_project: dec.scope_project,
              scope_region: dec.scope_region || "",
            });
          }
        } else if (focusedCard.type === "action") {
          const act = queueData.actions.find((a) => a.item_id === focusedCard.id);
          if (act) {
            setEditItem({
              type: "action",
              id: act.item_id,
              text: act.text,
              owner_id: act.owner_id,
              deadline: act.deadline || "",
            });
          }
        } else if (focusedCard.type === "premise") {
          let foundP: PremiseCard | undefined;
          for (const d of queueData.decisions) {
            foundP = d.premises.find((p) => p.id === focusedCard.id);
            if (foundP) break;
          }
          if (foundP) {
            setEditItem({
              type: "premise",
              id: foundP.id,
              text: foundP.text,
            });
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [focusedCard, queueData, missingFieldAction, editItem]);

  // Submit Edit
  const handleSaveEdit = async () => {
    if (!editItem) return;
    try {
      if (editItem.type === "decision") {
        await editDecision(editItem.id, {
          text: editItem.text,
          scope_project: editItem.scope_project,
          scope_region: editItem.scope_region,
        });
        addToast("Decision updated.", "success");
      } else if (editItem.type === "action") {
        await editAction(editItem.id, {
          text: editItem.text,
          owner_id: editItem.owner_id,
          deadline: editItem.deadline || null,
        });
        addToast("Action updated.", "success");
      } else if (editItem.type === "premise") {
        await editPremise(editItem.id, { text: editItem.text });
        addToast("Premise updated.", "success");
      }
      setEditItem(null);
      if (selectedMeetingId) loadMeetingData(selectedMeetingId);
    } catch (err: any) {
      addToast(err.message, "error");
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Top Bar: Meeting Selector & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Review Queue</h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800">
              Interactive Hero Screen
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-0.5">
            Two-pane human verification. Decisions, premises, and actions apply only after approval.
          </p>
        </div>

        {/* Meeting Dropdown Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
            Meeting:
          </label>
          <select
            className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={selectedMeetingId || ""}
            onChange={(e) => setSelectedMeetingId(Number(e.target.value))}
          >
            {meetings.map((m) => (
              <option key={m.id} value={m.id}>
                {m.title} ({m.date}) - [{m.status.toUpperCase()}]
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Two-Pane Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0 pt-4">
        {/* LEFT PANE: Transcript with Highlighted Evidence Quotes */}
        <div className="lg:col-span-5 flex flex-col bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="bg-slate-50/80 px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-semibold text-slate-700">Verbatim Transcript</span>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              {utterances.length} utterances
            </span>
          </div>

          <div
            ref={transcriptContainerRef}
            className="flex-1 overflow-y-auto p-4 space-y-4 text-sm divide-y divide-slate-100"
          >
            {loading ? (
              <div className="space-y-4 py-8">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="animate-pulse space-y-2">
                    <div className="h-4 bg-slate-200 rounded w-1/4"></div>
                    <div className="h-4 bg-slate-100 rounded w-full"></div>
                    <div className="h-4 bg-slate-100 rounded w-5/6"></div>
                  </div>
                ))}
              </div>
            ) : utterances.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                <p>No utterances found for this meeting.</p>
              </div>
            ) : (
              utterances.map((u) => {
                // Determine if this utterance contains any quote from review cards
                const matchingAlert = queueData?.alerts.find(
                  (a) => (a.old_quote && u.text.includes(a.old_quote)) || (a.new_quote && u.text.includes(a.new_quote))
                );
                const matchingDecision = queueData?.decisions.find(
                  (d) => d.evidence_quote && u.text.includes(d.evidence_quote)
                );
                let matchingPremise: PremiseCard | undefined;
                queueData?.decisions.forEach((d) => {
                  const p = d.premises.find((pr) => pr.evidence_quote && u.text.includes(pr.evidence_quote));
                  if (p) matchingPremise = p;
                });
                const matchingAction = queueData?.actions.find(
                  (a) => a.evidence_quote && u.text.includes(a.evidence_quote)
                );

                const hasHighlight =
                  matchingAlert || matchingDecision || matchingPremise || matchingAction;

                return (
                  <div
                    key={u.id}
                    id={`utterance-${u.id}`}
                    className={`pt-3 transition-colors rounded-lg p-2 ${
                      focusedCard?.utterance_id === u.id
                        ? "bg-indigo-50/70 border-l-4 border-indigo-600 pl-3"
                        : ""
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-xs text-slate-800">
                        {u.speaker_name || u.speaker_raw}
                      </span>
                      {u.start_ts != null && (
                        <span className="text-[11px] font-mono text-slate-400">
                          {Math.floor(u.start_ts / 60)}:
                          {String(Math.floor(u.start_ts % 60)).padStart(2, "0")}
                        </span>
                      )}
                    </div>
                    <p className="text-slate-700 leading-relaxed text-xs sm:text-sm">
                      {/* Check and highlight matching evidence quotes */}
                      {renderHighlightedText(
                        u.text,
                        activeQuote,
                        matchingAlert,
                        matchingDecision,
                        matchingPremise,
                        matchingAction,
                        handleQuoteClick
                      )}
                    </p>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT PANE: Review Queue Cards */}
        <div className="lg:col-span-7 flex flex-col bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {/* Header with Keyboard Shortcuts */}
          <div className="bg-slate-50/80 px-4 py-3 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <span className="text-sm font-semibold text-slate-800">Verification Cards</span>
            </div>
            <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500 bg-white px-2.5 py-1 rounded border border-slate-200">
              <span className="font-bold text-slate-700">[A]</span> Approve
              <span className="mx-1">•</span>
              <span className="font-bold text-slate-700">[E]</span> Edit
              <span className="mx-1">•</span>
              <span className="font-bold text-slate-700">[R]</span> Reject
            </div>
          </div>

          <div
            ref={cardsContainerRef}
            className="flex-1 overflow-y-auto p-4 space-y-5"
          >
            {loading ? (
              <div className="space-y-4 py-8">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                    <div className="h-5 bg-slate-200 rounded w-1/3"></div>
                    <div className="h-4 bg-slate-100 rounded w-full"></div>
                    <div className="h-8 bg-slate-200 rounded w-1/2"></div>
                  </div>
                ))}
              </div>
            ) : queueData &&
              queueData.alerts.length === 0 &&
              queueData.decisions.length === 0 &&
              queueData.actions.length === 0 &&
              queueData.links.length === 0 ? (
              <div className="text-center py-16 px-4">
                <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
                <h3 className="text-base font-semibold text-slate-900">All Items Verified</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  The review queue for this meeting is clear. All decisions and actions have been processed.
                </p>
              </div>
            ) : (
              <>
                {/* 1. ALERTS (Premise Break & Conflict First) */}
                {queueData?.alerts.map((alert) => {
                  const isFocused = focusedCard?.type === "alert" && focusedCard.id === alert.id;
                  return (
                    <div
                      key={alert.id}
                      id={`card-alert-${alert.id}`}
                      onClick={() =>
                        handleSelectCard("alert", alert.id, alert.old_quote || undefined, alert.utterance_id)
                      }
                      className={`rounded-xl border-2 p-4 transition-all cursor-pointer ${
                        alert.kind === "premise_break"
                          ? "border-rose-300 bg-rose-50/30 hover:border-rose-400"
                          : "border-amber-300 bg-amber-50/30 hover:border-amber-400"
                      } ${isFocused ? "ring-2 ring-indigo-500 shadow-md" : ""}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider bg-rose-100 text-rose-800">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          {alert.kind.replace("_", " ")}
                        </span>
                        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-white border border-rose-200 text-rose-700">
                          State: {alert.state}
                        </span>
                      </div>

                      <h4 className="font-semibold text-sm text-slate-900 mb-1">{alert.verdict}</h4>
                      <p className="text-xs text-slate-600 mb-3">{alert.explanation}</p>

                      {/* Side-by-side Then vs Now */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3 text-xs">
                        <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                          <div className="font-semibold text-slate-500 text-[11px] uppercase mb-1">
                            Then (Earlier Confirmed Premise)
                          </div>
                          <div className="text-slate-800 italic">
                            "{alert.old_quote || "N/A"}"
                          </div>
                        </div>
                        <div className="p-2.5 bg-rose-50 rounded-lg border border-rose-200 shadow-2xs">
                          <div className="font-semibold text-rose-700 text-[11px] uppercase mb-1">
                            Now (Contradictory Statement)
                          </div>
                          <div className="text-rose-950 italic">
                            "{alert.new_quote || "N/A"}"
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center justify-end gap-2 pt-2 border-t border-rose-200/60">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDismissAlert(alert.id);
                          }}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 border border-slate-300"
                        >
                          Dismiss
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleConfirmAlert(alert.id);
                          }}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-700 text-white shadow-sm"
                        >
                          Confirm Break
                        </button>
                      </div>
                    </div>
                  );
                })}

                {/* 2. DECISIONS (With Nested Premise Cards) */}
                {queueData?.decisions.map((dec) => {
                  const isFocused =
                    focusedCard?.type === "decision" && focusedCard.id === dec.item_id;
                  return (
                    <div
                      key={dec.item_id}
                      id={`card-decision-${dec.item_id}`}
                      onClick={() =>
                        handleSelectCard(
                          "decision",
                          dec.item_id,
                          dec.evidence_quote,
                          dec.utterance_id
                        )
                      }
                      className={`rounded-xl border border-slate-200 bg-white p-4 transition-all cursor-pointer shadow-sm ${
                        isFocused ? "ring-2 ring-indigo-500 shadow-md" : "hover:border-slate-300"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="px-2.5 py-0.5 rounded-md text-xs font-bold uppercase tracking-wider bg-blue-100 text-blue-800">
                            Decision
                          </span>
                          <span className="text-xs font-medium text-slate-500">
                            Confidence: {Math.round(dec.confidence * 100)}%
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {dec.scope_region && (
                            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                              Region: {dec.scope_region}
                            </span>
                          )}
                          <span
                            className={`text-[11px] font-semibold px-2 py-0.5 rounded uppercase ${
                              dec.review_state === "approved"
                                ? "bg-emerald-100 text-emerald-800"
                                : dec.review_state === "rejected"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {dec.review_state}
                          </span>
                        </div>
                      </div>

                      <h3 className="text-base font-bold text-slate-900 mb-1.5">{dec.text}</h3>

                      <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-200 mb-3 italic">
                        "{dec.evidence_quote}"
                      </div>

                      {/* Decision Buttons */}
                      <div className="flex items-center justify-end gap-2 pb-3 border-b border-slate-100">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditItem({
                              type: "decision",
                              id: dec.item_id,
                              text: dec.text,
                              scope_project: dec.scope_project,
                              scope_region: dec.scope_region || "",
                            });
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-300 text-slate-700 hover:bg-slate-50"
                        >
                          <Edit3 className="w-3.5 h-3.5" /> Edit
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRejectDecision(dec.item_id);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-rose-200 text-rose-700 hover:bg-rose-50"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Reject
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleApproveDecision(dec.item_id);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" /> Approve
                        </button>
                      </div>

                      {/* NESTED PREMISES */}
                      <div className="mt-3 pl-3 border-l-2 border-indigo-200 space-y-2">
                        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                          <Link2 className="w-3.5 h-3.5 text-indigo-500" />
                          Underlying Premises ({dec.premises.length})
                        </div>

                        {dec.premises.map((p) => {
                          const isPremiseFocused =
                            focusedCard?.type === "premise" && focusedCard.id === p.id;
                          return (
                            <div
                              key={p.id}
                              id={`card-premise-${p.id}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelectCard(
                                  "premise",
                                  p.id,
                                  p.evidence_quote,
                                  p.utterance_id
                                );
                              }}
                              className={`p-3 bg-slate-50 rounded-lg border border-slate-200 transition-all ${
                                isPremiseFocused
                                  ? "ring-2 ring-indigo-500 bg-indigo-50/40"
                                  : "hover:bg-slate-100/60"
                              }`}
                            >
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <span className="font-semibold text-xs text-slate-800">
                                  {p.text}
                                </span>
                                <span
                                  className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                                    p.state === "confirmed"
                                      ? "bg-emerald-100 text-emerald-800"
                                      : p.state === "rejected"
                                      ? "bg-rose-100 text-rose-800"
                                      : "bg-amber-100 text-amber-800"
                                  }`}
                                >
                                  {p.state}
                                </span>
                              </div>
                              <p className="text-[11px] text-slate-600 italic mb-2">
                                "{p.evidence_quote}"
                              </p>

                              <div className="flex items-center justify-between pt-1">
                                <span className="text-[11px] text-slate-400">
                                  {p.valid_until ? `Valid until: ${p.valid_until}` : "Indefinite"}
                                </span>
                                <div className="flex items-center gap-1.5">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleRejectPremise(p.id);
                                    }}
                                    className="px-2 py-1 text-[11px] rounded font-medium border border-rose-200 text-rose-700 hover:bg-rose-50"
                                  >
                                    Reject
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleApprovePremise(p.id);
                                    }}
                                    className="px-2 py-1 text-[11px] rounded font-medium bg-emerald-600 text-white hover:bg-emerald-700 shadow-2xs"
                                  >
                                    Confirm
                                  </button>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}

                {/* 3. ACTIONS */}
                {queueData?.actions.map((act) => {
                  const isFocused =
                    focusedCard?.type === "action" && focusedCard.id === act.item_id;
                  return (
                    <div
                      key={act.item_id}
                      id={`card-action-${act.item_id}`}
                      onClick={() =>
                        handleSelectCard(
                          "action",
                          act.item_id,
                          act.evidence_quote,
                          act.utterance_id
                        )
                      }
                      className={`rounded-xl border border-slate-200 bg-white p-4 transition-all cursor-pointer shadow-sm ${
                        isFocused ? "ring-2 ring-indigo-500 shadow-md" : "hover:border-slate-300"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="px-2.5 py-0.5 rounded-md text-xs font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800">
                            Action Item
                          </span>
                          <span className="text-xs font-medium text-slate-500">
                            Confidence: {Math.round(act.confidence * 100)}%
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {act.needs_owner && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                              <AlertCircle className="w-3 h-3" /> Needs Owner
                            </span>
                          )}
                          {act.needs_deadline && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                              <Calendar className="w-3 h-3" /> Needs Deadline
                            </span>
                          )}
                          {act.provisional && (
                            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-800">
                              Provisional
                            </span>
                          )}
                          <span
                            className={`text-[11px] font-semibold px-2 py-0.5 rounded uppercase ${
                              act.review_state === "approved"
                                ? "bg-emerald-100 text-emerald-800"
                                : act.review_state === "rejected"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {act.review_state}
                          </span>
                        </div>
                      </div>

                      <h3 className="text-base font-bold text-slate-900 mb-1">{act.text}</h3>

                      <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-200 mb-3 italic">
                        "{act.evidence_quote}"
                      </div>

                      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 mb-3">
                        <div className="flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-slate-400" />
                          <span>Owner:</span>
                          <span className="font-semibold text-slate-800">
                            {act.owner_name || "Unassigned"}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>Deadline:</span>
                          <span className="font-semibold text-slate-800">
                            {act.deadline || "No deadline"}
                          </span>
                        </div>
                        {act.linked_decision && (
                          <div className="flex items-center gap-1 text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded text-[11px]">
                            <span>Linked to: {act.linked_decision.text}</span>
                          </div>
                        )}
                        {act.tracker_ref && (
                          <span className="text-[11px] font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                            Ticket: {act.tracker_ref}
                          </span>
                        )}
                      </div>

                      {/* Action Item Buttons */}
                      <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditItem({
                              type: "action",
                              id: act.item_id,
                              text: act.text,
                              owner_id: act.owner_id,
                              deadline: act.deadline || "",
                            });
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-300 text-slate-700 hover:bg-slate-50"
                        >
                          <Edit3 className="w-3.5 h-3.5" /> Edit
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRejectAction(act.item_id);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-rose-200 text-rose-700 hover:bg-rose-50"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Reject
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleApproveActionClick(act);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" /> Approve
                        </button>
                      </div>
                    </div>
                  );
                })}

                {/* 4. LINK CONFIRMATION CARDS */}
                {queueData?.links.map((lnk) => {
                  return (
                    <div
                      key={lnk.id}
                      className="rounded-xl border border-dashed border-indigo-300 bg-indigo-50/20 p-4"
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="inline-flex items-center gap-1 text-xs font-bold uppercase text-indigo-700">
                          <Link2 className="w-3.5 h-3.5" /> Candidate Link ({Math.round(lnk.confidence * 100)}%)
                        </span>
                        <span className="text-[11px] font-semibold text-slate-500">
                          {lnk.confirmed ? "Confirmed" : "Needs Confirmation"}
                        </span>
                      </div>
                      <div className="text-xs text-slate-800 font-medium mb-1 flex items-center gap-2">
                        <span>{lnk.source_title}</span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                        <span>{lnk.target_title}</span>
                      </div>
                      {lnk.rationale && (
                        <p className="text-[11px] text-slate-500 mb-3">{lnk.rationale}</p>
                      )}
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleRejectLink(lnk.id)}
                          className="px-2.5 py-1 text-xs font-medium border border-slate-300 rounded hover:bg-slate-50"
                        >
                          Reject
                        </button>
                        <button
                          onClick={() => handleConfirmLink(lnk.id)}
                          className="px-2.5 py-1 text-xs font-medium bg-indigo-600 text-white rounded hover:bg-indigo-700 shadow-2xs"
                        >
                          Confirm Link
                        </button>
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </div>
      </div>

      {/* MODAL 1: Missing Owner / Deadline Assignment */}
      {missingFieldAction && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 text-amber-600 font-bold text-base">
                <AlertCircle className="w-5 h-5" />
                Missing Fields Required
              </div>
              <button
                onClick={() => setMissingFieldAction(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-600 mb-4">
              Action "<strong>{missingFieldAction.text}</strong>" has missing fields. Per Invariant 1, owners and deadlines are never guessed.
            </p>

            <div className="space-y-3 mb-6 text-sm">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Assign Owner:
                </label>
                <select
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm bg-white"
                  value={assigneeId || ""}
                  onChange={(e) => setAssigneeId(Number(e.target.value) || null)}
                >
                  <option value="">-- Choose Owner --</option>
                  {queueData?.people.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.email})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Set Deadline:
                </label>
                <input
                  type="date"
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                  value={assignDeadline}
                  onChange={(e) => setAssignDeadline(e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-2 justify-end">
              <button
                onClick={() =>
                  executeApproveAction(missingFieldAction.item_id, {
                    approve_unassigned: true,
                  })
                }
                className="px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg border border-slate-300"
              >
                Approve Unassigned
              </button>
              <button
                onClick={() =>
                  executeApproveAction(missingFieldAction.item_id, {
                    owner_id: assigneeId,
                    deadline: assignDeadline || null,
                    approve_unassigned: false,
                  })
                }
                className="px-4 py-2 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm"
              >
                Save & Approve
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Edit Card Dialog */}
      {editItem && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-base text-slate-900">
                Edit {editItem.type.toUpperCase()} Card
              </h3>
              <button onClick={() => setEditItem(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 mb-6 text-sm">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Text:</label>
                <textarea
                  rows={3}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                  value={editItem.text}
                  onChange={(e) => setEditItem({ ...editItem, text: e.target.value })}
                />
              </div>

              {editItem.type === "action" && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Assignee:
                    </label>
                    <select
                      className="w-full border border-slate-300 rounded-lg p-2 text-sm bg-white"
                      value={editItem.owner_id || ""}
                      onChange={(e) =>
                        setEditItem({ ...editItem, owner_id: Number(e.target.value) || null })
                      }
                    >
                      <option value="">-- Unassigned --</option>
                      {queueData?.people.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Deadline:
                    </label>
                    <input
                      type="date"
                      className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                      value={editItem.deadline || ""}
                      onChange={(e) => setEditItem({ ...editItem, deadline: e.target.value })}
                    />
                  </div>
                </>
              )}

              {editItem.type === "decision" && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Region:</label>
                  <input
                    type="text"
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                    value={editItem.scope_region || ""}
                    onChange={(e) => setEditItem({ ...editItem, scope_region: e.target.value })}
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setEditItem(null)}
                className="px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-4 py-2 text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOAST NOTIFICATIONS */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-lg shadow-lg border text-xs font-medium flex items-center gap-2.5 transition-all ${
              toast.type === "success"
                ? "bg-emerald-950 text-emerald-100 border-emerald-800"
                : toast.type === "error"
                ? "bg-rose-950 text-rose-100 border-rose-800"
                : "bg-slate-900 text-slate-100 border-slate-800"
            }`}
          >
            {toast.type === "success" && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
            {toast.type === "error" && <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />}
            {toast.type === "info" && <Info className="w-4 h-4 text-indigo-400 shrink-0" />}
            <span className="flex-1">{toast.message}</span>
            <button
              onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// Helper: Highlight matching evidence quotes in utterance text
function renderHighlightedText(
  text: string,
  activeQuote: string | null,
  alert?: AlertCard,
  decision?: DecisionCard,
  premise?: PremiseCard,
  action?: ActionCard,
  onQuoteClick?: (quote: string, type: CardType, id: number) => void
) {
  // Candidate quotes
  const candidates: { quote: string; type: CardType; id: number }[] = [];
  if (alert?.old_quote && text.includes(alert.old_quote)) {
    candidates.push({ quote: alert.old_quote, type: "alert", id: alert.id });
  }
  if (alert?.new_quote && text.includes(alert.new_quote)) {
    candidates.push({ quote: alert.new_quote, type: "alert", id: alert.id });
  }
  if (decision?.evidence_quote && text.includes(decision.evidence_quote)) {
    candidates.push({ quote: decision.evidence_quote, type: "decision", id: decision.item_id });
  }
  if (premise?.evidence_quote && text.includes(premise.evidence_quote)) {
    candidates.push({ quote: premise.evidence_quote, type: "premise", id: premise.id });
  }
  if (action?.evidence_quote && text.includes(action.evidence_quote)) {
    candidates.push({ quote: action.evidence_quote, type: "action", id: action.item_id });
  }

  if (candidates.length === 0) {
    return text;
  }

  // Pick first matching candidate quote
  const match = candidates[0];
  const idx = text.indexOf(match.quote);
  if (idx === -1) return text;

  const before = text.slice(0, idx);
  const matched = text.slice(idx, idx + match.quote.length);
  const after = text.slice(idx + match.quote.length);

  const isCurrentActive = activeQuote === match.quote;

  return (
    <>
      {before}
      <button
        type="button"
        onClick={() => onQuoteClick?.(match.quote, match.type, match.id)}
        className={`inline text-left cursor-pointer rounded px-1.5 py-0.5 font-medium transition-all ${
          match.type === "alert"
            ? "bg-rose-100 text-rose-900 border-b-2 border-rose-400 hover:bg-rose-200"
            : match.type === "decision"
            ? "bg-blue-100 text-blue-900 border-b-2 border-blue-400 hover:bg-blue-200"
            : match.type === "premise"
            ? "bg-indigo-100 text-indigo-900 border-b-2 border-indigo-400 hover:bg-indigo-200"
            : "bg-emerald-100 text-emerald-900 border-b-2 border-emerald-400 hover:bg-emerald-200"
        } ${isCurrentActive ? "ring-2 ring-indigo-600 animate-pulse bg-amber-200 font-bold" : ""}`}
        title={`Click to focus ${match.type} card`}
      >
        {matched}
      </button>
      {after}
    </>
  );
}
