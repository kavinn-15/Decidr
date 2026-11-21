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
  proposal_id?: number | null;
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

export interface ConfirmAlertResponse {
  status: string;
  alert_id: number;
  proposal_id?: number | null;
  verdict?: string;
}

export async function confirmAlert(alertId: number, actor: string = "reviewer"): Promise<ConfirmAlertResponse> {
  return apiRequest<ConfirmAlertResponse>(`/review/alerts/${alertId}/confirm`, {
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

export async function deleteMeeting(meetingId: number): Promise<{ status: string; meeting_id: number; message: string }> {
  return apiRequest<{ status: string; meeting_id: number; message: string }>(`/meetings/${meetingId}`, {
    method: "DELETE",
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

export interface DecisionPremiseItem {
  id: number;
  text: string;
  evidence_quote?: string;
  utterance_id?: number | null;
  utterance_idx?: number | null;
  speaker_name?: string | null;
  utterance_text?: string | null;
  meeting_id?: number | null;
  meeting_title?: string | null;
  meeting_date?: string | null;
  scope_project?: string;
  scope_region?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  state: "proposed" | "confirmed" | "rejected";
  status: "holding" | "shaky" | "broken" | "expired";
  confirmed_by?: string | null;
}

export interface DecisionSummary {
  id: number;
  item_id: number;
  text: string;
  scope_project: string;
  scope_region?: string | null;
  scope_release?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  status: "active" | "superseded" | "at_risk";
  version: number;
  supersedes_id?: number | null;
  score: number;
  premises_count: number;
  premises: DecisionPremiseItem[];
}

export interface DecisionLinkedTask {
  id: number;
  item_id: number;
  title: string;
  description?: string | null;
  owner_id?: number | null;
  owner_name?: string | null;
  due_date?: string | null;
  estimate_hours?: number | null;
  provisional: boolean;
  status: "open" | "at_risk" | "done" | "cancelled";
  tracker_ref?: string | null;
  tracker_url?: string | null;
  link_confirmed?: boolean;
}

export interface DecisionVersionItem {
  id: number;
  version: number;
  text: string;
  changed_at?: string | null;
  changed_by: string;
}

export interface DecisionTimelineItem {
  id: number;
  created_at?: string | null;
  actor: string;
  action: string;
  entity_type?: string;
  entity_id?: number;
  status?: string | null;
  cause?: string | null;
  before?: Record<string, any> | null;
  after?: Record<string, any> | null;
}

export interface DecisionDetailResponse {
  decision: {
    id: number;
    item_id: number;
    meeting_id?: number | null;
    meeting_title?: string | null;
    meeting_date?: string | null;
    text: string;
    scope_project: string;
    scope_region?: string | null;
    scope_release?: string | null;
    effective_from?: string | null;
    effective_to?: string | null;
    status: "active" | "superseded" | "at_risk";
    version: number;
    supersedes_id?: number | null;
    embedding?: string | null;
  };
  premises: DecisionPremiseItem[];
  linked_tasks: DecisionLinkedTask[];
  version_history: DecisionVersionItem[];
  status_timeline: DecisionTimelineItem[];
}

export async function fetchDecisions(params?: {
  project?: string;
  status?: string;
  text?: string;
  region?: string;
  limit?: number;
}): Promise<DecisionSummary[]> {
  const q = new URLSearchParams();
  if (params?.project) q.set("project", params.project);
  if (params?.status) q.set("status", params.status);
  if (params?.text) q.set("text", params.text);
  if (params?.region) q.set("region", params.region);
  if (params?.limit) q.set("limit", String(params.limit));
  return apiRequest<DecisionSummary[]>(`/decisions?${q.toString()}`);
}

export async function fetchDecisionDetail(id: number): Promise<DecisionDetailResponse> {
  return apiRequest<DecisionDetailResponse>(`/decisions/${id}`);
}

export interface BlastRadiusChainNode {
  type: string;
  id: number;
  label: string;
}

export interface BlastRadiusChainEdge {
  from_type: string;
  from_id: string;
  to_type: string;
  to_id: string;
  relation: string;
}

export interface BlastRadiusAffectedTask {
  id: number;
  title: string;
  status: string;
  owner: string;
  due_date?: string | null;
  estimate_hours?: number | null;
  provisional?: boolean;
  depth: number;
  decision_id: number;
  chain_nodes: BlastRadiusChainNode[];
  chain_edges: BlastRadiusChainEdge[];
  reason: string;
}

export interface BlastRadiusUnaffectedTask {
  id: number;
  title: string;
  status: string;
  owner: string;
  due_date?: string | null;
  estimate_hours?: number | null;
  region?: string | null;
  reason: string;
}

export interface BlastRadiusNeedsConfirmationTask {
  id: number;
  title: string;
  status: string;
  owner: string;
  due_date?: string | null;
  estimate_hours?: number | null;
  reason: string;
  status_badge: string;
}

export interface BlastRadiusResponse {
  alert_id?: number | null;
  alert_kind: string;
  verdict: string;
  project: string;
  trigger_evidence: {
    speaker: string;
    meeting_title: string;
    meeting_date: string;
    old_quote: string;
    new_quote: string;
    explanation: string;
  };
  root_cause: {
    type: string;
    id: number;
    text: string;
    region?: string | null;
  };
  metrics: {
    hours_at_risk: number;
    unestimated_count: number;
    total_affected: number;
    direct_affected: number;
    indirect_affected: number;
    unaffected_count: number;
    needs_confirmation_count: number;
  };
  affected: BlastRadiusAffectedTask[];
  unaffected: BlastRadiusUnaffectedTask[];
  needs_confirmation: BlastRadiusNeedsConfirmationTask[];
}

export interface AlertSummaryItem {
  id: number;
  kind: string;
  verdict: string;
  state: string;
  meeting_id?: number | null;
  decision_id?: number | null;
  premise_id?: number | null;
  old_quote?: string | null;
  new_quote?: string | null;
  explanation?: string | null;
}

export async function fetchAlerts(state: string = "open"): Promise<AlertSummaryItem[]> {
  return apiRequest<AlertSummaryItem[]>(`/alerts?state=${state}`);
}

export async function fetchAlertBlastRadius(alertId: number): Promise<BlastRadiusResponse> {
  return apiRequest<BlastRadiusResponse>(`/alerts/${alertId}/blast-radius`);
}

export interface ProposalAction {
  id: number;
  proposal_id: number;
  action_type: string;
  target_type: string;
  target_id: number;
  target_name?: string | null;
  payload: Record<string, any>;
  planned_payload: Record<string, any>;
  idempotency_key: string;
  state: "draft" | "approved" | "rejected" | "executed" | "failed";
  executed_at?: string | null;
  result?: Record<string, any> | null;
}

export interface Proposal {
  id: number;
  trigger_type: string;
  trigger_id: number;
  summary: string;
  state: "draft" | "approved" | "rejected" | "executed";
  created_at?: string | null;
  decided_by?: string | null;
  decided_at?: string | null;
  actions: ProposalAction[];
}

export interface PlannedProposalAction {
  action_id: number;
  action_type: string;
  target_type: string;
  target_id: number;
  idempotency_key: string;
  payload: Record<string, any>;
}

export interface PreviewProposalResponse {
  dry_run: boolean;
  proposal_id: number;
  planned_actions: PlannedProposalAction[];
}

export async function fetchProposal(proposalId: number): Promise<Proposal> {
  return apiRequest<Proposal>(`/proposals/${proposalId}`);
}

export async function approveProposal(
  proposalId: number,
  data?: {
    actor?: string;
    action_ids?: number[];
    edited_payloads?: Record<number, any>;
  }
): Promise<any> {
  return apiRequest(`/proposals/${proposalId}/approve`, {
    method: "POST",
    body: JSON.stringify(data || {}),
  });
}

export async function rejectProposal(
  proposalId: number,
  actor: string = "reviewer"
): Promise<any> {
  return apiRequest(`/proposals/${proposalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export async function previewProposal(
  proposalId: number,
  data?: {
    action_ids?: number[];
    edited_payloads?: Record<number, any>;
  }
): Promise<PreviewProposalResponse> {
  if (data) {
    return apiRequest<PreviewProposalResponse>(`/proposals/${proposalId}/preview`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
  return apiRequest<PreviewProposalResponse>(`/proposals/${proposalId}/preview`);
}

export async function generateRepairPlanForAlert(alertId: number): Promise<Proposal> {
  return apiRequest<Proposal>(`/alerts/${alertId}/repair-plan`, {
    method: "POST",
  });
}

export async function fetchAlertRepairPlan(alertId: number): Promise<Proposal> {
  return apiRequest<Proposal>(`/alerts/${alertId}/repair-plan`);
}

export interface PersonSummary {
  id: number;
  name: string;
  email: string;
  tracker_id: string;
  slack_id?: string | null;
}

export interface MyWeekTask {
  id: number;
  title: string;
  due_date?: string | null;
  status: string;
  estimate_hours?: number | null;
  provisional: boolean;
  at_risk: boolean;
  needs_owner: boolean;
  tracker_ref?: string | null;
  tracker_url?: string | null;
}

export interface MyWeekDay {
  day_name: string;
  date: string;
  is_today: boolean;
  tasks: MyWeekTask[];
}

export interface ShakyBrokenWorkItem {
  task_id: number;
  task_title: string;
  owner_name: string;
  owner_id: number;
  status: string;
  due_date?: string | null;
  estimate_hours?: number | null;
  provisional: boolean;
  decision_id: number;
  decision_text: string;
  premise_id: number;
  premise_text: string;
  premise_status: string;
  reason: string;
}

export interface DigestResponse {
  person_id: number;
  person_name: string;
  person_email: string;
  as_of: string;
  sections: {
    due_this_week: MyWeekTask[];
    overdue: MyWeekTask[];
    decisions_affecting_you: Array<{
      id: number;
      text: string;
      status: string;
      scope_project: string;
      scope_region?: string | null;
    }>;
    alerts_needing_input: Array<{
      id: number;
      kind: string;
      verdict: string;
      explanation?: string | null;
      decision_id?: number | null;
    }>;
    work_resting_on_broken_or_shaky_premises: ShakyBrokenWorkItem[];
  };
  html: string;
  text: string;
}

export interface MyWeekResponse {
  person: PersonSummary;
  as_of: string;
  start_of_week: string;
  end_of_week: string;
  days: MyWeekDay[];
  overdue: MyWeekTask[];
  shaky_broken: ShakyBrokenWorkItem[];
  digest_preview: DigestResponse;
}

export interface OutboxItem {
  id: number;
  channel: string;
  to_addr: string;
  subject?: string | null;
  body: string;
  created_at?: string | null;
  sent: boolean;
}

export async function fetchPeople(): Promise<PersonSummary[]> {
  return apiRequest<PersonSummary[]>("/people");
}

export async function fetchMyWeek(personId: number, asOf?: string): Promise<MyWeekResponse> {
  const url = asOf ? `/my-week/${personId}?as_of=${asOf}` : `/my-week/${personId}`;
  return apiRequest<MyWeekResponse>(url);
}

export async function fetchDigest(personId: number, asOf?: string): Promise<DigestResponse> {
  const url = asOf ? `/digest/${personId}?as_of=${asOf}` : `/digest/${personId}`;
  return apiRequest<DigestResponse>(url);
}

export async function fetchOutbox(channel?: string, limit: number = 50): Promise<OutboxItem[]> {
  const q = new URLSearchParams();
  if (channel) q.append("channel", channel);
  q.append("limit", limit.toString());
  return apiRequest<OutboxItem[]>(`/outbox?${q.toString()}`);
}

export async function triggerRunReminders(now?: string): Promise<any> {
  const q = now ? `?now=${encodeURIComponent(now)}` : "";
  return apiRequest(`/admin/run-reminders${q}`, { method: "POST" });
}

export async function triggerRunDigest(asOf?: string): Promise<any> {
  const q = asOf ? `?as_of=${asOf}` : "";
  return apiRequest(`/admin/run-digest${q}`, { method: "POST" });
}

// --- Evaluation Interfaces & Endpoints (Task 16 - Invariant 10) ---

export interface EvalMetadata {
  date: string;
  model: string;
  llm_mode: string;
  git_commit: string;
  dataset: string;
  dataset_is_heldout: boolean;
}

export interface PrecisionRecallMetrics {
  tp: number;
  fp: number;
  fn: number;
  precision: number;
  recall: number;
  f1: number;
  total_extracted?: number;
  total_gold?: number;
  detected?: number;
  gold?: number;
  detected_affected?: number;
  gold_affected?: number;
}

export interface RepairCorrectnessMetrics {
  correctness: number;
  matched: number;
  total_gold: number;
  total_generated: number;
}

export interface EvalSystemMetrics {
  name: string;
  description: string;
  decisions_pr: PrecisionRecallMetrics;
  actions_pr: PrecisionRecallMetrics;
  premises_pr: PrecisionRecallMetrics;
  premise_breaks_pr: PrecisionRecallMetrics;
  conflicts_pr: PrecisionRecallMetrics;
  impact_pr: PrecisionRecallMetrics;
  repair_correctness: RepairCorrectnessMetrics;
  writes_without_approval: number;
}

export interface ComparisonTableRow {
  metric: string;
  b1: string;
  b2: string;
  decidr: string;
}

export interface EvalReport {
  metadata: EvalMetadata;
  decidr: EvalSystemMetrics;
  b1_baseline: EvalSystemMetrics;
  b2_baseline: EvalSystemMetrics;
  comparison_table: ComparisonTableRow[];
}

export async function fetchEvalReport(heldout: boolean = false): Promise<EvalReport> {
  return apiRequest<EvalReport>(`/eval/report?heldout=${heldout}`);
}

export async function fetchEvalMarkdown(): Promise<string> {
  const res = await fetch(`${API_BASE}/eval/report/markdown`);
  if (!res.ok) throw new Error("Failed to fetch evaluation markdown report");
  return res.text();
}

export async function fetchEvalCsv(): Promise<string> {
  const res = await fetch(`${API_BASE}/eval/report/csv`);
  if (!res.ok) throw new Error("Failed to fetch evaluation CSV report");
  return res.text();
}

export async function triggerRunEval(heldout: boolean = false): Promise<EvalReport> {
  return apiRequest<EvalReport>(`/eval/run?heldout=${heldout}`, { method: "POST" });
}



