"use client";

import { useState } from "react";

import type { DemoFaultMode, RequestOut } from "@/lib/api-types";
import { ApiError, api } from "@/lib/api";
import { SUBMISSION_STATUS_LABELS } from "@/lib/labels";

interface SubmissionPanelProps {
  request: RequestOut;
  canForward: boolean;
  onUpdated: (request: RequestOut) => void;
}

export function SubmissionPanel({ request, canForward, onUpdated }: SubmissionPanelProps) {
  const submission = request.current_submission;
  const [demoFault, setDemoFault] = useState<DemoFaultMode | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!submission) {
    return null;
  }

  async function forward() {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.forwardRequest(
        request.id,
        demoFault ? { demo_fault: demoFault } : undefined,
      );
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Lähetys epäonnistui");
    } finally {
      setBusy(false);
    }
  }

  const canRetry =
    canForward &&
    ["approved", "forward_failed", "forwarding"].includes(request.status) &&
    !["exhausted", "accepted"].includes(submission.status);

  const alreadyAccepted = submission.status === "accepted";

  return (
    <section className="card" aria-labelledby="submission-heading" data-testid="submission-panel">
      <h2 id="submission-heading">Lähetyksen tila (mock-integraatio)</h2>
      <dl className="field-list compact">
        <div>
          <dt>Tila</dt>
          <dd>{SUBMISSION_STATUS_LABELS[submission.status] ?? submission.status}</dd>
        </div>
        <div>
          <dt>Yritykset</dt>
          <dd>{submission.attempt_count}</dd>
        </div>
        <div>
          <dt>Mock-tietue</dt>
          <dd>{submission.downstream_reference ?? "—"}</dd>
        </div>
        <div>
          <dt>Idempotenssiavain</dt>
          <dd className="mono">{submission.idempotency_key}</dd>
        </div>
        {submission.error_category ? (
          <div>
            <dt>Virheluokka</dt>
            <dd>{submission.error_category}</dd>
          </div>
        ) : null}
      </dl>
      <p className="help">
        Mock-integraatio tallentaa pyyntötietueen. Se ei luo tilejä eikä myönnä oikeuksia.
      </p>
      {canRetry ? (
        <div className="stack">
          <div className="field">
            <label htmlFor="demo-fault">Demo-vikatila (vain paikallinen)</label>
            <select
              id="demo-fault"
              value={demoFault}
              onChange={(event) => setDemoFault(event.target.value as DemoFaultMode | "")}
            >
              <option value="">Onnistuminen</option>
              <option value="lost-response">Kadonnut vastaus onnistuneen käsittelyn jälkeen</option>
              <option value="fail-before">Epäonnistuminen ennen käsittelyä</option>
              <option value="unavailable">Tilapäinen poissaolo</option>
            </select>
          </div>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || alreadyAccepted}
            onClick={() => void forward()}
            data-testid="forward-button"
          >
            {busy ? "Lähetetään…" : alreadyAccepted ? "Lähetetty mock-integraatioon" : "Lähetä / yritä uudelleen"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
