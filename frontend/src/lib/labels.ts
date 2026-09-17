import type { RequestStatus, SubmissionStatus } from "@/lib/api-types";
import type { ProcessingPhase } from "@/lib/processing-state";

export const FIELD_LABELS: Record<string, string> = {
  employee_identifier: "Työntekijätunnus",
  employment_type: "Työsuhde",
  job_role: "Työrooli",
  unit: "Yksikkö",
  target_system: "Kohdejärjestelmä",
  requested_access_role: "Pyydetty käyttöoikeus",
  start_date: "Alkupäivä",
  end_date: "Loppupäivä",
  original_text: "Alkuperäinen teksti",
};

export const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = {
  submitted: "Lähetetty",
  preparing: "Valmistellaan",
  needs_clarification: "Odottaa täsmennystä",
  ready_for_review: "Odottaa tarkastusta",
  in_review: "Tarkastuksessa",
  approved: "Hyväksytty",
  rejected: "Hylätty",
  forwarding: "Lähetetään eteenpäin",
  forwarded: "Välitetty",
  forward_failed: "Välitys epäonnistui",
};

export const SUBMISSION_STATUS_LABELS: Record<SubmissionStatus, string> = {
  pending: "Odottaa lähetystä",
  in_flight: "Lähetys käynnissä",
  unknown: "Tuntematon tulos",
  accepted: "Vastaanotettu",
  failed: "Epäonnistui",
  exhausted: "Yritykset loppu",
  conflict: "Ristiriita",
};

export const PROCESSING_PHASE_LABELS: Record<ProcessingPhase, string> = {
  preparing: "Valmistellaan taustalla",
  needs_clarification: "Odottaa täsmennystä",
  waiting_review: "Odottaa tarkastusta",
  in_review: "Tarkastuksessa",
  approved_not_sent: "Hyväksytty, ei vielä lähetetty",
  submitting: "Lähetetään mock-integraatioon",
  unknown_outcome: "Alasvirran tulos tuntematon — vaatii tarkistuksen",
  submitted: "Mock-integraatio vastaanotti pyynnön",
  failed_intervention: "Vaatii toimenpiteen",
  rejected: "Hylätty",
};

export const AUDIT_EVENT_LABELS: Record<string, string> = {
  request_created: "Pyyntö luotu",
  request_updated: "Pyyntö päivitetty",
  proposal_prepared: "Ehdotus valmisteltu",
  proposal_invalidated: "Edellinen ehdotus mitätöity",
  preparation_failed: "Valmistelu epäonnistui",
  preparation_interrupted: "Valmistelu keskeytyi",
  instructions_retrieved: "Ohjeita noudettu",
  review_started: "Tarkastus aloitettu",
  review_approved: "Hyväksytty",
  review_rejected: "Hylätty",
  submission_scheduled: "Lähetys ajoitettu",
  submission_attempt: "Lähetysyritys",
  submission_accepted: "Mock vastaanotti pyynnön",
  submission_failed: "Lähetys epäonnistui",
  submission_unknown: "Lähetyksen tulos tuntematon",
  submission_exhausted: "Lähetysyrt. loppuivat",
};

export const VIOLATION_LABELS: Record<string, string> = {
  unknown_system: "Tuntematon järjestelmä",
  unknown_access_role: "Tuntematon käyttöoikeus",
  prohibited_role: "Kielletty käyttöoikeus",
  disallowed_combination: "Sallittu yhdistelmä puuttuu",
  temporary_requires_end_date: "Määräaikainen vaatii loppupäivän",
  start_after_end: "Alkupäivä myöhäisempi kuin loppupäivä",
};

export const ROLE_LABELS: Record<string, string> = {
  requester: "Pyytäjä",
  reviewer: "Tarkastaja",
  operator: "Operaattori",
};

export function formatFieldName(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

export function formatRole(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

export function requestStatusLabel(status: RequestStatus): string {
  return REQUEST_STATUS_LABELS[status] ?? status;
}
