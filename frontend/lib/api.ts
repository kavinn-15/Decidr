const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface HealthResponse {
  status: string;
}

export interface MeetingSummary {
  id: number;
  title: string;
  date: string;
  project: string;
  region?: string | null;
  release?: string | null;
  status: string;
  transcript_ref?: string | null;
  error?: string | null;
  utterance_count?: number;
  unmapped_speakers_count?: number;
  pending_review_count?: number;
  decisions_count?: number;
  actions_count?: number;
}

export interface UtteranceItem {
  id: number;
  meeting_id: number;
  idx: number;
  speaker_raw: string;
  person_id?: number | null;
  text: string;
  start_ts?: number | null;
  speaker_name?: string | null;
  is_unmapped?: boolean;
}

export interface AlertCard {
  id: number;
  kind: "conflict" | "premise_break" | "expiry";
  verdict: string;
  old_quote?: string | null;
  new_quote?: string | null;
  explanation?: string | null;
  state: "open" | "confirmed" | "dismissed";
  decision_id?: number | null;
  premise_id?: number | null;
  utterance_id?: number | null;
  utterance_idx?: number | null;
}

export interface PremiseCard {
  id: number;
  decision_id: number;
  text: string;
  evidence_quote: string;
  utterance_id?: number | null;
  utterance_idx?: number | null;
  speaker?: string | null;
  valid_until?: string | null;
  state: "proposed" | "confirmed" | "rejected";
  status: "holding" | "shaky" | "broken" | "expired";
  confirmed_by?: string | null;
}

export interface DecisionCard {
  item_id: number;
  decision_id?: number | null;
  text: string;
  confidence: number;
  evidence_quote: string;
  utterance_id?: number | null;
  utterance_idx?: number | null;
  speaker?: string | null;
  scope_project: string;
  scope_region?: string | null;
  scope_release?: string | null;
  version: number;
  status: string;
  review_state: "proposed" | "approved" | "edited" | "rejected";
  premises: PremiseCard[];
}

export interface ActionCard {
  item_id: number;
  task_id?: number | null;
  text: string;
  confidence: number;
  evidence_quote: string;
  utterance_id?: number | null;
  utterance_idx?: number | null;
  speaker?: string | null;
  owner_id?: number | null;
  owner_name?: string | null;
  deadline?: string | null;
  needs_owner: boolean;
  needs_deadline: boolean;
  estimate_hours?: number | null;
  provisional: boolean;
  review_state: "proposed" | "approved" | "edited" | "rejected";
  tracker_ref?: string | null;
  tracker_url?: string | null;
  linked_decision?: { id: number; text: string; scope_region?: string | null } | null;
}

export interface LinkCard {
  id: number;
  source_type: string;
  source_id: number;
  source_title: string;
  target_type: string;
  target_id: number;
  target_title: string;
  relation: string;
  confidence: number;
  confirmed: boolean;
  rationale?: string | null;
}

export interface PersonItem {
  id: number;
  name: string;
  email: string;
  tracker_id?: string | null;
}

export interface ReviewQueueResponse {
  meeting_id: number;
  title: string;
  date: string;
  project: string;
  region?: string | null;
  release?: string | null;
  status: string;
  alerts: AlertCard[];
  decisions: DecisionCard[];
  actions: ActionCard[];
  links: LinkCard[];
  people: PersonItem[];
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch health status: ${res.statusText}`);
  }
  return res.json();
}

export async function apiRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const err = await res.json();
      errorDetail = err.detail || JSON.stringify(err);
    } catch {
      // Keep statusText if not json
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export async function fetchMeetings(): Promise<MeetingSummary[]> {
  return apiRequest<MeetingSummary[]>("/meetings");
}

export async function fetchUtterances(meetingId: number): Promise<UtteranceItem[]> {
  return apiRequest<UtteranceItem[]>(`/meetings/${meetingId}/utterances`);
}

export async function fetchReviewQueue(meetingId: number): Promise<ReviewQueueResponse> {
  return apiRequest<ReviewQueueResponse>(`/meetings/${meetingId}/review`);
}

export async function approveDecision(itemId: number, actor: string = "reviewer") {
  return apiRequest(`/review/decisions/${itemId}/approve`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function rejectDecision(itemId: number, actor: string = "reviewer") {
  return apiRequest(`/review/decisions/${itemId}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function editDecision(
  itemId: number,
  data: {
    actor?: string;
    text?: string;
    scope_project?: string;
    scope_region?: string;
    scope_release?: string;
  }
) {
  return apiRequest(`/review/decisions/${itemId}/edit`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function approvePremise(premiseId: number, actor: string = "reviewer") {
  return apiRequest(`/review/premises/${premiseId}/approve`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function rejectPremise(premiseId: number, actor: string = "reviewer") {
  return apiRequest(`/review/premises/${premiseId}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function editPremise(
  premiseId: number,
  data: { actor?: string; text?: string; valid_until?: string }
) {
  return apiRequest(`/review/premises/${premiseId}/edit`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface ApproveActionResponse {
  status: string;
  item_id: number;
  task_id: number;
  provisional: boolean;
  tracker_ref?: string | null;
  tracker_url?: string | null;
  executor_result?: any;
}

export async function approveAction(
  itemId: number,
  data: {
    actor?: string;
    owner_id?: number | null;
    deadline?: string | null;
    estimate_hours?: number | null;
    approve_unassigned?: boolean;
  }
): Promise<ApproveActionResponse> {
  return apiRequest<ApproveActionResponse>(`/review/actions/${itemId}/approve`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function rejectAction(itemId: number, actor: string = "reviewer") {
  return apiRequest(`/review/actions/${itemId}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function editAction(
  itemId: number,
  data: {
    actor?: string;
    text?: string;
    owner_id?: number | null;
    deadline?: string | null;
    estimate_hours?: number | null;
  }
) {
  return apiRequest(`/review/actions/${itemId}/edit`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function confirmLink(linkId: number, actor: string = "reviewer") {
  return apiRequest(`/review/links/${linkId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function rejectLink(linkId: number, actor: string = "reviewer") {
  return apiRequest(`/review/links/${linkId}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function confirmAlert(alertId: number, actor: string = "reviewer") {
  return apiRequest(`/review/alerts/${alertId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function dismissAlert(alertId: number, actor: string = "reviewer") {
  return apiRequest(`/review/alerts/${alertId}/dismiss`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export interface AuditLogItem {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: number;
  before?: Record<string, any> | null;
  after?: Record<string, any> | null;
  created_at: string;
}

export interface AuditListResponse {
  total: number;
  items: AuditLogItem[];
}

export interface AuditFilters {
  actors: string[];
  actions: string[];
  entity_types: string[];
}

export interface ConfigResponse {
  demo_mode: boolean;
  llm_provider: string;
  tracker: string;
}

export interface UnmappedSpeakerItem {
  speaker_raw: string;
  count: number;
}

export async function uploadMeeting(formData: FormData): Promise<MeetingSummary> {
  const res = await fetch(`${API_BASE}/meetings`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    let err = res.statusText;
    try {
      const j = await res.json();
      err = j.detail || JSON.stringify(j);
    } catch {}
    throw new Error(err);
  }
  return res.json();
}

export async function processMeeting(meetingId: number) {
  return apiRequest(`/meetings/${meetingId}/process`, {
    method: "POST",
  });
}

export async function fetchUnmappedSpeakers(meetingId: number): Promise<UnmappedSpeakerItem[]> {
  return apiRequest<UnmappedSpeakerItem[]>(`/meetings/${meetingId}/unmapped-speakers`);
}

export async function patchSpeaker(meetingId: number, speaker_raw: string, person_id: number) {
  return apiRequest(`/meetings/${meetingId}/speakers`, {
    method: "PATCH",
    body: JSON.stringify({ speaker_raw, person_id }),
  });
}

export async function fetchRoster(): Promise<PersonItem[]> {
  return apiRequest<PersonItem[]>("/meetings/roster/people");
}

export async function fetchConfig(): Promise<ConfigResponse> {
  return apiRequest<ConfigResponse>("/config");
}

export async function resetDemoData() {
  return apiRequest("/demo/reset", {
    method: "POST",
  });
}

export async function fetchAuditLogs(params?: {
  actor?: string;
  action?: string;
  entity_type?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditListResponse> {
  const q = new URLSearchParams();
  if (params?.actor) q.set("actor", params.actor);
  if (params?.action) q.set("action", params.action);
  if (params?.entity_type) q.set("entity_type", params.entity_type);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  return apiRequest<AuditListResponse>(`/audit?${q.toString()}`);
}

export async function fetchAuditFilters(): Promise<AuditFilters> {
  return apiRequest<AuditFilters>("/audit/filters");
}

export function getAuditExportUrl(params?: {
  actor?: string;
  action?: string;
  entity_type?: string;
}): string {
  const q = new URLSearchParams();
  if (params?.actor) q.set("actor", params.actor);
  if (params?.action) q.set("action", params.action);
  if (params?.entity_type) q.set("entity_type", params.entity_type);
  return `${API_BASE}/audit/export?${q.toString()}`;
}
