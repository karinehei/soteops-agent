import type { RequestOut, RequestStatus, SubmissionStatus } from "@/lib/api-types";

export type ProcessingPhase =
  | "preparing"
  | "needs_clarification"
  | "waiting_review"
  | "in_review"
  | "approved_not_sent"
  | "submitting"
  | "unknown_outcome"
  | "submitted"
  | "failed_intervention"
  | "rejected";

export interface ProcessingState {
  phase: ProcessingPhase;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
  detail?: string;
}

export function deriveProcessingState(request: RequestOut): ProcessingState {
  const submission = request.current_submission;
  const status = request.status as RequestStatus;
  const subStatus = submission?.status as SubmissionStatus | undefined;

  if (status === "preparing" || status === "submitted") {
    return { phase: "preparing", tone: "info", detail: "Taustaprosessi käsittelee pyyntöä." };
  }
  if (status === "needs_clarification") {
    return {
      phase: "needs_clarification",
      tone: "warning",
      detail: "Pyytäjän on täsmennettävä puuttuvat tiedot ennen tarkastusta.",
    };
  }
  if (status === "ready_for_review") {
    return { phase: "waiting_review", tone: "info" };
  }
  if (status === "in_review") {
    return { phase: "in_review", tone: "info" };
  }
  if (status === "rejected") {
    return { phase: "rejected", tone: "neutral" };
  }

  if (subStatus === "unknown" || (status === "forwarding" && subStatus === "in_flight")) {
    return {
      phase: subStatus === "unknown" ? "unknown_outcome" : "submitting",
      tone: "warning",
      detail:
        "Timeout ei todista epäonnistumista. Tulos varmistetaan idempotenssiavaimella ennen päätöstä.",
    };
  }

  if (
    status === "forwarding" ||
    subStatus === "in_flight" ||
    subStatus === "pending"
  ) {
    if (status === "approved" && subStatus === "pending") {
      return {
        phase: "approved_not_sent",
        tone: "info",
        detail: "Hyväksyntä on voimassa. Lähetys tapahtuu erillisellä toimenpiteellä.",
      };
    }
    return { phase: "submitting", tone: "info" };
  }

  if (status === "forwarded" || subStatus === "accepted") {
    return {
      phase: "submitted",
      tone: "success",
      detail: submission?.downstream_reference
        ? `Mock-tietue: ${submission.downstream_reference}`
        : undefined,
    };
  }

  if (
    status === "forward_failed" ||
    subStatus === "failed" ||
    subStatus === "exhausted" ||
    subStatus === "conflict"
  ) {
    return {
      phase: "failed_intervention",
      tone: "danger",
      detail: submission?.error_category ?? "Tarkista audit-loki ja yritä uudelleen tarvittaessa.",
    };
  }

  if (status === "approved") {
    return { phase: "approved_not_sent", tone: "info" };
  }

  return { phase: "waiting_review", tone: "neutral" };
}

export function isApprovable(proposal: RequestOut["current_proposal"]): boolean {
  if (!proposal) {
    return false;
  }
  return proposal.missing_fields.length === 0 && proposal.rule_violations.length === 0;
}
