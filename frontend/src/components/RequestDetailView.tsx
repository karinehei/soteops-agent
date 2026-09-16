"use client";

import Link from "next/link";
import { useState } from "react";

import { AuditTimeline } from "@/components/AuditTimeline";
import { ErrorState, LoadingState } from "@/components/FeedbackStates";
import { ProposalPanel } from "@/components/ProposalPanel";
import { RequestForm } from "@/components/RequestForm";
import { ReviewActions } from "@/components/ReviewActions";
import { StatusBadge } from "@/components/StatusBadge";
import { SubmissionPanel } from "@/components/SubmissionPanel";
import { ApiError, api } from "@/lib/api";
import { useRequest } from "@/hooks/useRequest";
import type { MeResponse, RequestOut, RequestWrite } from "@/lib/api-types";

interface RequestDetailViewProps {
  requestId: string;
  user: MeResponse;
  mode: "requester" | "reviewer";
}

function nextStepFor(
  request: RequestOut,
  role: MeResponse["role"],
  canEdit: boolean,
): { title: string; body: string } | null {
  if (request.status === "preparing" || request.status === "submitted") {
    return {
      title: "Käynnissä",
      body: "Valmistelu poimii kentät ja ajaa säännöt. Tämä ei ole hyväksyntä.",
    };
  }
  if (request.status === "needs_clarification") {
    return {
      title: "Seuraava askel",
      body: canEdit
        ? "Täsmennä puuttuvat tiedot ja lähetä uudelleen valmisteltavaksi."
        : "Pyytäjän on täsmennettävä puuttuvat tiedot. Hyväksyntä on estetty.",
    };
  }
  if (request.status === "ready_for_review" || request.status === "in_review") {
    if (role === "reviewer") {
      return {
        title: "Seuraava askel",
        body:
          request.status === "ready_for_review"
            ? "Aloita tarkastus. Hyväksy vain, jos deterministiset säännöt sallivat."
            : "Tarkasta kentät, ohjeet ja säännöt. Hyväksyntä sitoo tarkan tiivisteen.",
      };
    }
    return {
      title: "Odottaa tarkastajaa",
      body: "Pyyntö on tarkastajan jonossa. Malli ei päätä lopputulosta.",
    };
  }
  if (
    request.status === "approved" ||
    request.current_submission?.status === "pending"
  ) {
    if (role === "reviewer" || role === "operator") {
      return {
        title: "Seuraava askel",
        body: "Lähetä hyväksytty snapshot mock-integraatioon. Tiliä ei luoda.",
      };
    }
  }
  if (request.current_submission?.status === "unknown") {
    return {
      title: "Tarkista tulos",
      body: "Alasvirran vastaus katosi. Yritä uudelleen samalla idempotenssiavaimella.",
    };
  }
  return null;
}

export function RequestDetailView({ requestId, user }: RequestDetailViewProps) {
  const { request, loading, error, reload, setRequest } = useRequest(requestId);
  const [editError, setEditError] = useState<string | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [invalidationNotice, setInvalidationNotice] = useState<string | null>(null);

  if (loading && !request) {
    return <LoadingState label="Ladataan pyyntöä…" />;
  }
  if (error && !request) {
    return <ErrorState message={error} onRetry={() => void reload()} />;
  }
  if (!request) {
    return <ErrorState message="Pyyntöä ei löytynyt" />;
  }

  const proposal = request.current_proposal;
  const blockingSubmission = ["pending", "in_flight", "unknown"].includes(
    request.current_submission?.status ?? "",
  );
  const canEdit =
    user.role === "requester" &&
    user.id === request.owner_id &&
    ["needs_clarification", "ready_for_review", "in_review", "forward_failed"].includes(
      request.status,
    ) &&
    !["forwarding", "forwarded"].includes(request.status) &&
    !blockingSubmission;

  const canForward = user.role === "reviewer" || user.role === "operator";
  const isReviewer = user.role === "reviewer";
  const listHref = user.role === "reviewer" ? "/review" : "/requests";
  const nextStep = nextStepFor(request, user.role, canEdit);

  async function handleEdit(payload: RequestWrite) {
    setEditBusy(true);
    setEditError(null);
    try {
      const previousProposalId = request?.current_proposal?.id;
      const updated = await api.updateRequest(requestId, payload);
      setRequest(updated);
      setShowEdit(false);
      if (previousProposalId && updated.current_proposal?.id !== previousProposalId) {
        setInvalidationNotice(
          "Pyyntöä muokattiin. Edellinen hyväksyntä ei ole enää voimassa — tarvitaan uusi tarkastus.",
        );
      }
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Muokkaus epäonnistui");
    } finally {
      setEditBusy(false);
    }
  }

  async function handleResubmit() {
    setEditBusy(true);
    setEditError(null);
    try {
      const updated = await api.resubmitRequest(requestId);
      setRequest(updated);
      setInvalidationNotice("Pyyntö lähetettiin uudelleen valmisteltavaksi.");
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Uudelleenlähetys epäonnistui");
    } finally {
      setEditBusy(false);
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Pyyntö {request.id.slice(0, 8)}…</p>
          <h1>Käyttöoikeuspyyntö</h1>
        </div>
        <StatusBadge request={request} />
      </div>

      {invalidationNotice ? (
        <div className="notice notice--warning" role="status" data-testid="invalidation-notice">
          {invalidationNotice}
        </div>
      ) : null}

      {nextStep ? (
        <div className="next-step" role="status">
          <strong>{nextStep.title}</strong>
          <p>{nextStep.body}</p>
        </div>
      ) : null}

      <div className={isReviewer || canForward ? "review-layout" : undefined}>
        <div>
          <section className="card" aria-labelledby="original-heading">
            <h2 id="original-heading">Alkuperäinen synteettinen teksti</h2>
            <p className="pre-wrap">{request.original_text}</p>
            <p className="mono small">Revisio {request.revision}</p>
          </section>

          {canEdit ? (
            <section className="card" data-testid="requester-edit-panel">
              <div className="btn-row">
                <button
                  type="button"
                  className={request.status === "needs_clarification" ? "btn btn--primary" : "btn"}
                  onClick={() => setShowEdit((value) => !value)}
                >
                  {showEdit ? "Piilota muokkaus" : "Muokkaa ja täsmennä"}
                </button>
                {request.status === "needs_clarification" ? (
                  <button
                    type="button"
                    className="btn btn--ghost"
                    disabled={editBusy}
                    onClick={() => void handleResubmit()}
                  >
                    Lähetä uudelleen valmisteltavaksi
                  </button>
                ) : null}
              </div>
              {showEdit ? (
                <RequestForm
                  initial={{
                    original_text: request.original_text,
                    employee_identifier: request.employee_identifier,
                    employment_type: request.employment_type,
                    job_role: request.job_role,
                    unit: request.unit,
                    target_system: request.target_system,
                    requested_access_role: request.requested_access_role,
                    start_date: request.start_date,
                    end_date: request.end_date,
                  }}
                  submitLabel="Tallenna muutokset"
                  busy={editBusy}
                  error={editError}
                  onSubmit={handleEdit}
                />
              ) : null}
            </section>
          ) : null}

          {proposal ? (
            <ProposalPanel proposal={proposal} showApprovalEligibility={isReviewer} />
          ) : (
            <LoadingState label="Odotetaan ehdotusta…" />
          )}
        </div>

        {isReviewer || canForward ? (
          <aside className="review-layout__aside">
            {isReviewer && proposal ? (
              <ReviewActions
                request={request}
                proposal={proposal}
                onUpdated={(updated) => {
                  setRequest(updated);
                  setInvalidationNotice(null);
                }}
              />
            ) : null}
            <SubmissionPanel
              request={request}
              canForward={canForward}
              onUpdated={(updated) => setRequest(updated)}
            />
          </aside>
        ) : (
          <SubmissionPanel
            request={request}
            canForward={canForward}
            onUpdated={(updated) => setRequest(updated)}
          />
        )}
      </div>

      <AuditTimeline
        requestId={requestId}
        refreshKey={`${request.status}:${request.current_submission?.status ?? ""}:${request.updated_at}`}
      />

      <Link className="back-link" href={listHref}>
        ← Takaisin listaan
      </Link>
    </main>
  );
}
