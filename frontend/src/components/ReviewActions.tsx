"use client";

import { useState } from "react";

import type { ApprovalAction, ProposalOut, RequestOut } from "@/lib/api-types";
import { ApiError, api } from "@/lib/api";
import { isApprovable } from "@/lib/processing-state";

interface ReviewActionsProps {
  request: RequestOut;
  proposal: ProposalOut;
  onUpdated: (request: RequestOut) => void;
}

function buildAction(proposal: ProposalOut, request: RequestOut, comment: string): ApprovalAction {
  return {
    proposal_id: proposal.id,
    revision: request.revision,
    payload_hash: proposal.payload_hash,
    policy_version: proposal.policy_version,
    comment: comment.trim() || null,
  };
}

export function ReviewActions({ request, proposal, onUpdated }: ReviewActionsProps) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | "review" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eligible = isApprovable(proposal);

  async function run(action: "approve" | "reject" | "review") {
    setBusy(action);
    setError(null);
    try {
      let updated: RequestOut;
      if (action === "review") {
        updated = await api.startReview(request.id);
      } else if (action === "approve") {
        updated = await api.approveRequest(request.id, buildAction(proposal, request, comment));
      } else {
        updated = await api.rejectRequest(request.id, buildAction(proposal, request, comment));
      }
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Toimenpide epäonnistui");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card" aria-labelledby="review-actions-heading" data-testid="review-actions">
      <h2 id="review-actions-heading">Tarkastajan toimet</h2>
      <div className="field">
        <label htmlFor="review-comment">Kommentti (valinnainen)</label>
        <textarea
          id="review-comment"
          rows={3}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
      </div>
      {error ? (
        <p className="form-error" role="alert" data-testid="review-error">
          {error}
        </p>
      ) : null}
      <div className="btn-row">
        {request.status === "ready_for_review" ? (
          <button
            type="button"
            className="btn"
            disabled={busy !== null}
            onClick={() => void run("review")}
          >
            {busy === "review" ? "Aloitetaan…" : "Aloita tarkastus"}
          </button>
        ) : null}
        <button
          type="button"
          className="btn btn--primary"
          disabled={!eligible || busy !== null || !["ready_for_review", "in_review"].includes(request.status)}
          onClick={() => void run("approve")}
          data-testid="approve-button"
        >
          {busy === "approve" ? "Hyväksytään…" : "Hyväksy tarkka ehdotus"}
        </button>
        <button
          type="button"
          className="btn btn--danger"
          disabled={busy !== null || !["ready_for_review", "in_review"].includes(request.status)}
          onClick={() => void run("reject")}
          data-testid="reject-button"
        >
          {busy === "reject" ? "Hylätään…" : "Hylkää"}
        </button>
      </div>
      {!eligible ? (
        <p className="help">
          Hylkää tai pyydä pyytäjää täsmentämään. Erillistä &quot;pyydä muutoksia&quot; -päätöstä ei
          ole — muokkaus tapahtuu pyytäjän puolella.
        </p>
      ) : null}
    </section>
  );
}
