/**
 * Centrally maintained API types mirroring backend/app/api/requests.py and auth routes.
 * Regenerate hint: GET /openapi.json when the API is running.
 */

export type UserRole = "requester" | "reviewer" | "operator";

export type RequestStatus =
  | "submitted"
  | "preparing"
  | "needs_clarification"
  | "ready_for_review"
  | "in_review"
  | "approved"
  | "rejected"
  | "forwarding"
  | "forwarded"
  | "forward_failed";

export type SubmissionStatus =
  | "pending"
  | "in_flight"
  | "unknown"
  | "accepted"
  | "failed"
  | "exhausted"
  | "conflict";

export type DemoFaultMode = "success" | "fail-before" | "lost-response" | "unavailable";

export interface MeResponse {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  demo_authentication: boolean;
  identity_provider: string;
  note: string;
}

export interface RequestWrite {
  original_text: string;
  employee_identifier?: string | null;
  employment_type?: string | null;
  job_role?: string | null;
  unit?: string | null;
  target_system?: string | null;
  requested_access_role?: string | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface RuleViolation {
  code: string;
  message?: string;
  field?: string;
  [key: string]: unknown;
}

export interface ProposalOut {
  id: string;
  revision: number;
  extracted_fields: Record<string, unknown>;
  excerpts: Record<string, string>;
  missing_fields: string[];
  rule_violations: RuleViolation[];
  explanation_text: string;
  clarification_draft: string;
  source_references: Record<string, unknown>[];
  provider_metadata: Record<string, unknown>;
  downstream_payload: Record<string, unknown>;
  policy_version: string;
  payload_hash: string;
  invalidated_at: string | null;
}

export interface SubmissionOut {
  idempotency_key: string;
  status: SubmissionStatus;
  attempt_count: number;
  downstream_reference: string | null;
  error_category: string | null;
  payload_hash: string;
  revision: number;
}

export interface RequestOut {
  id: string;
  owner_id: string;
  employee_identifier: string | null;
  employment_type: string | null;
  job_role: string | null;
  unit: string | null;
  target_system: string | null;
  requested_access_role: string | null;
  start_date: string | null;
  end_date: string | null;
  original_text: string;
  revision: number;
  status: RequestStatus;
  current_proposal: ProposalOut | null;
  current_submission: SubmissionOut | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalAction {
  proposal_id: string;
  revision: number;
  payload_hash: string;
  policy_version: string;
  comment?: string | null;
}

export interface ForwardAction {
  demo_fault?: DemoFaultMode | null;
}

export interface AuditOut {
  id: string;
  event_type: string;
  actor_id: string | null;
  request_id: string | null;
  correlation_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ApiErrorBody {
  detail?: string | { msg: string }[];
}
