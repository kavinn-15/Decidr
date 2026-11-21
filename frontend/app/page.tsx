"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Upload,
  Play,
  RotateCcw,
  Users,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Calendar,
  Layers,
  ChevronRight,
  RefreshCw,
  FileText,
  AlertCircle,
  X,
  Check,
  Sparkles,
} from "lucide-react";
import {
  fetchMeetings,
  uploadMeeting,
  processMeeting,
  fetchUnmappedSpeakers,
  patchSpeaker,
  fetchRoster,
  fetchConfig,
  resetDemoData,
  MeetingSummary,
  UnmappedSpeakerItem,
  PersonItem,
} from "@/lib/api";

interface Toast {
  id: string;
  type: "success" | "error" | "info";
  message: string;
}

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [demoMode, setDemoMode] = useState<boolean>(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Upload Modal State
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [title, setTitle] = useState<string>("");
  const [dateVal, setDateVal] = useState<string>("2026-11-21");
  const [project, setProject] = useState<string>("Payments Revamp");
  const [region, setRegion] = useState<string>("");
  const [release, setRelease] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Unmapped Speaker Modal State
  const [speakerModalMeeting, setSpeakerModalMeeting] = useState<MeetingSummary | null>(null);
  const [unmappedSpeakers, setUnmappedSpeakers] = useState<UnmappedSpeakerItem[]>([]);
  const [roster, setRoster] = useState<PersonItem[]>([]);
  const [speakerSelections, setSpeakerSelections] = useState<Record<string, number>>({});
  const [isSavingSpeaker, setIsSavingSpeaker] = useState<boolean>(false);

  const addToast = (message: string, type: "success" | "error" | "info" = "info") => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const loadData = async () => {
    try {
      const [meetingsData, configData] = await Promise.all([
        fetchMeetings(),
        fetchConfig().catch(() => ({ demo_mode: false, llm_provider: "gemini", tracker: "mock" })),
      ]);
      setMeetings(meetingsData);
      setDemoMode(configData.demo_mode);
    } catch (err: any) {
      addToast(err.message || "Failed to load meetings", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Polling for processing status
  useEffect(() => {
    const hasProcessing = meetings.some((m) => m.status === "processing");
    if (!hasProcessing) return;

    const interval = setInterval(async () => {
      try {
        const freshMeetings = await fetchMeetings();
        setMeetings(freshMeetings);
      } catch {
        // Silently continue polling
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [meetings]);

  // Upload handler
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      addToast("Please select a transcript file (.vtt, .srt, .txt, .json)", "error");
      return;
    }

    try {
      setIsUploading(true);
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("title", title);
      formData.append("date", dateVal);
      formData.append("project", project);
      if (region.trim()) formData.append("region", region.trim());
      if (release.trim()) formData.append("release", release.trim());

      const created = await uploadMeeting(formData);
      addToast(`Meeting "${created.title}" uploaded successfully!`, "success");
      setIsUploadOpen(false);
      setUploadFile(null);
      setTitle("");
      setRegion("");
      setRelease("");
      loadData();
    } catch (err: any) {
      addToast(err.message || "Failed to upload meeting", "error");
    } finally {
      setIsUploading(false);
    }
  };

  // Trigger Background Extraction
  const handleProcess = async (meetingId: number) => {
    try {
      await processMeeting(meetingId);
      addToast("Extraction started in background. Polling status...", "info");
      // Instantly mark as processing in local state
      setMeetings((prev) =>
        prev.map((m) => (m.id === meetingId ? { ...m, status: "processing" } : m))
      );
    } catch (err: any) {
      addToast(err.message || "Failed to trigger processing", "error");
    }
  };

  // Open speaker mapping modal
  const handleOpenSpeakerModal = async (meeting: MeetingSummary) => {
    setSpeakerModalMeeting(meeting);
    try {
      const [unmappedList, rosterList] = await Promise.all([
        fetchUnmappedSpeakers(meeting.id),
        fetchRoster().catch(() => []),
      ]);
      setUnmappedSpeakers(unmappedList);
      setRoster(rosterList);
      const initialMap: Record<string, number> = {};
      unmappedList.forEach((s) => {
        // Try auto-matching if name matches roster
        const match = rosterList.find((r) => r.name.toLowerCase() === s.speaker_raw.toLowerCase());
        if (match) initialMap[s.speaker_raw] = match.id;
      });
      setSpeakerSelections(initialMap);
    } catch (err: any) {
      addToast(err.message || "Failed to load speaker mapping details", "error");
    }
  };

  // Save speaker mapping
  const handleSaveSpeakerMapping = async (speakerRaw: string) => {
    if (!speakerModalMeeting) return;
    const personId = speakerSelections[speakerRaw];
    if (!personId) {
      addToast("Please select a person from the roster to map", "error");
      return;
    }

    try {
      setIsSavingSpeaker(true);
      await patchSpeaker(speakerModalMeeting.id, speakerRaw, personId);
      addToast(`Speaker "${speakerRaw}" mapped successfully across meeting!`, "success");
      // Remove from unmapped list
      setUnmappedSpeakers((prev) => prev.filter((s) => s.speaker_raw !== speakerRaw));
      loadData();
    } catch (err: any) {
      addToast(err.message || "Failed to map speaker", "error");
    } finally {
      setIsSavingSpeaker(false);
    }
  };

  // Reset Demo Data
  const handleResetDemo = async () => {
    if (!confirm("Are you sure you want to reset all demo data? This will reseed the database.")) {
      return;
    }
    try {
      setLoading(true);
      await resetDemoData();
      addToast("Demo data reseeded cleanly!", "success");
      loadData();
    } catch (err: any) {
      addToast(err.message || "Failed to reset demo data", "error");
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Meetings Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Ingest transcripts, monitor background extraction, and verify decisions before execution.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {demoMode && (
            <button
              onClick={handleResetDemo}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-300 hover:bg-amber-100 transition-colors shadow-2xs"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Demo Data
            </button>
          )}
          <button
            onClick={() => setIsUploadOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-700 transition-colors shadow-sm"
          >
            <Upload className="w-4 h-4" />
            Upload Meeting
          </button>
        </div>
      </div>

      {/* Meetings Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 bg-slate-50/60 flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-sm text-slate-800">
            <Layers className="w-4 h-4 text-indigo-600" />
            Transcripts Repository ({meetings.length})
          </div>
          <button
            onClick={loadData}
            title="Refresh"
            className="text-slate-500 hover:text-slate-800 p-1 rounded hover:bg-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {loading ? (
          <div className="p-8 space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse flex items-center justify-between py-3 border-b border-slate-100">
                <div className="space-y-2 w-1/3">
                  <div className="h-4 bg-slate-200 rounded w-3/4"></div>
                  <div className="h-3 bg-slate-100 rounded w-1/2"></div>
                </div>
                <div className="h-6 bg-slate-200 rounded w-20"></div>
                <div className="h-8 bg-slate-100 rounded w-24"></div>
              </div>
            ))}
          </div>
        ) : meetings.length === 0 ? (
          <div className="text-center py-16 px-4">
            <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-900">No Meetings Uploaded</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto mb-4">
              Upload your first meeting transcript (.vtt, .srt, .txt, or .json) to begin extracting decisions and tasks.
            </p>
            <button
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm"
            >
              <Upload className="w-3.5 h-3.5" /> Upload Meeting Transcript
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm divide-y divide-slate-200">
              <thead className="bg-slate-50/50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-5 py-3">Meeting</th>
                  <th className="px-5 py-3">Date</th>
                  <th className="px-5 py-3">Project / Scope</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Pending Review</th>
                  <th className="px-5 py-3">Speakers</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {meetings.map((m) => {
                  return (
                    <tr key={m.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-semibold text-slate-900">{m.title}</div>
                        <div className="text-xs text-slate-400 font-mono">
                          {m.transcript_ref?.split("/").pop()}
                        </div>
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap text-xs text-slate-600">
                        {m.date}
                      </td>
                      <td className="px-5 py-4">
                        <div className="font-medium text-slate-800">{m.project}</div>
                        {(m.region || m.release) && (
                          <div className="text-xs text-slate-500">
                            {[m.region && `Region: ${m.region}`, m.release && `Release: ${m.release}`]
                              .filter(Boolean)
                              .join(" • ")}
                          </div>
                        )}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap">
                        <StatusBadge status={m.status} error={m.error} />
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap">
                        {m.pending_review_count && m.pending_review_count > 0 ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-900">
                            <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                            {m.pending_review_count} cards pending
                          </span>
                        ) : m.status === "review" || m.status === "done" ? (
                          <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                            <CheckCircle2 className="w-3.5 h-3.5" /> All reviewed
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap">
                        {m.unmapped_speakers_count && m.unmapped_speakers_count > 0 ? (
                          <button
                            onClick={() => handleOpenSpeakerModal(m)}
                            className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded bg-amber-50 text-amber-800 border border-amber-300 hover:bg-amber-100 transition-colors"
                          >
                            <Users className="w-3.5 h-3.5 text-amber-600" />
                            {m.unmapped_speakers_count} unmapped
                          </button>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                            <Users className="w-3.5 h-3.5 text-slate-400" />
                            Mapped
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap text-right space-x-2">
                        {m.status === "uploaded" && (
                          <button
                            onClick={() => handleProcess(m.id)}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-2xs"
                          >
                            <Play className="w-3 h-3" /> Process
                          </button>
                        )}
                        {m.status === "processing" && (
                          <span className="inline-flex items-center gap-1.5 text-xs text-indigo-700 font-medium px-2 py-1 bg-indigo-50 rounded">
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Processing...
                          </span>
                        )}
                        {m.status === "failed" && (
                          <button
                            onClick={() => handleProcess(m.id)}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 shadow-2xs"
                          >
                            <RotateCcw className="w-3 h-3" /> Retry
                          </button>
                        )}
                        {(m.status === "review" || m.status === "done") && (
                          <Link
                            href="/review"
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 shadow-2xs"
                          >
                            Review Queue <ChevronRight className="w-3.5 h-3.5" />
                          </Link>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL 1: Upload Meeting Dialog */}
      {isUploadOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-lg w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 text-slate-900 font-bold text-lg">
                <Upload className="w-5 h-5 text-indigo-600" />
                Upload Meeting Transcript
              </div>
              <button
                onClick={() => setIsUploadOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4 text-sm">
              {/* File picker */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Transcript File (.vtt, .srt, .txt, .json) *
                </label>
                <input
                  type="file"
                  accept=".vtt,.srt,.txt,.json"
                  required
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setUploadFile(f);
                      if (!title) {
                        setTitle(f.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " "));
                      }
                    }
                  }}
                  className="w-full text-xs text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer border border-slate-200 rounded-lg p-2"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Meeting Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Payments Kickoff Sync"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Meeting Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={dateVal}
                    onChange={(e) => setDateVal(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Project *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Payments Revamp"
                    value={project}
                    onChange={(e) => setProject(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Region (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. India, Europe"
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Release (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. v1.0, Q4"
                    value={release}
                    onChange={(e) => setRelease(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsUploadOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm disabled:opacity-50"
                >
                  {isUploading ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" /> Upload & Parse
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Unmapped Speakers Dialog */}
      {speakerModalMeeting && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-lg w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 text-slate-900 font-bold text-lg">
                <Users className="w-5 h-5 text-amber-600" />
                Map Unmapped Speakers
              </div>
              <button
                onClick={() => setSpeakerModalMeeting(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-500 mb-4">
              Meeting: <strong>{speakerModalMeeting.title}</strong>. Map raw transcript names to team members in the roster. Mapping updates all utterances across the meeting and writes an audit log.
            </p>

            {unmappedSpeakers.length === 0 ? (
              <div className="text-center py-6 text-emerald-700 bg-emerald-50 rounded-lg border border-emerald-200">
                <CheckCircle2 className="w-8 h-8 mx-auto mb-1 text-emerald-600" />
                <p className="font-semibold text-xs">All speakers mapped successfully!</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {unmappedSpeakers.map((s) => (
                  <div
                    key={s.speaker_raw}
                    className="p-3 rounded-lg border border-slate-200 bg-slate-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div>
                      <span className="font-bold text-slate-800 text-sm">{s.speaker_raw}</span>
                      <span className="text-slate-400 ml-2">({s.count} utterances)</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <select
                        className="border border-slate-300 rounded p-1.5 text-xs bg-white focus:ring-1 focus:ring-indigo-500"
                        value={speakerSelections[s.speaker_raw] || ""}
                        onChange={(e) =>
                          setSpeakerSelections({
                            ...speakerSelections,
                            [s.speaker_raw]: Number(e.target.value),
                          })
                        }
                      >
                        <option value="">-- Choose Person --</option>
                        {roster.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} ({p.email})
                          </option>
                        ))}
                      </select>

                      <button
                        onClick={() => handleSaveSpeakerMapping(s.speaker_raw)}
                        disabled={isSavingSpeaker || !speakerSelections[s.speaker_raw]}
                        className="px-2.5 py-1.5 rounded font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 transition-colors"
                      >
                        Map
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end pt-4 mt-4 border-t border-slate-100">
              <button
                onClick={() => setSpeakerModalMeeting(null)}
                className="px-4 py-2 text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOAST SYSTEM */}
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
            {toast.type === "info" && <Check className="w-4 h-4 text-indigo-400 shrink-0" />}
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

function StatusBadge({ status, error }: { status: string; error?: string | null }) {
  switch (status) {
    case "uploaded":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">
          Uploaded
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-800">
          <RefreshCw className="w-3 h-3 animate-spin" /> Processing
        </span>
      );
    case "review":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">
          Review Ready
        </span>
      );
    case "done":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
          Done
        </span>
      );
    case "failed":
      return (
        <span
          title={error || "Processing failed"}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 cursor-help"
        >
          <AlertCircle className="w-3 h-3 text-rose-600" />
          Failed {error ? `(${error.slice(0, 20)}...)` : ""}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">
          {status}
        </span>
      );
  }
}
