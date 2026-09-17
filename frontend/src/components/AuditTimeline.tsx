"use client";

import { useEffect, useState } from "react";

import type { AuditOut } from "@/lib/api-types";
import { api } from "@/lib/api";
import { AUDIT_EVENT_LABELS } from "@/lib/labels";
import { ErrorState, LoadingState } from "@/components/FeedbackStates";

const SAFE_METADATA_KEYS = new Set([
  "status",
  "revision",
  "proposal_id",
  "decision",
  "policy_version",
  "missing_fields",
  "violation_codes",
  "node",
  "provider",
  "run_status",
  "source_ids",
  "attempt_count",
  "error_category",
  "submission_status",
  "downstream_reference",
]);

function sanitizeMetadata(metadata: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(metadata).filter(([key]) => SAFE_METADATA_KEYS.has(key)));
}

export function AuditTimeline({
  requestId,
  refreshKey,
}: {
  requestId: string;
  refreshKey?: string;
}) {
  const [events, setEvents] = useState<AuditOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .auditTrail(requestId)
      .then((items) => {
        if (!cancelled) {
          setEvents(items);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [requestId, refreshKey]);

  if (error) {
    return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  }
  if (!events) {
    return <LoadingState label="Ladataan audit-lokia…" />;
  }
  if (events.length === 0) {
    return <p>Ei audit-tapahtumia.</p>;
  }

  return (
    <section className="card" aria-labelledby="audit-heading" data-testid="audit-timeline">
      <h2 id="audit-heading">Audit-aikajana (sanitized)</h2>
      <ol className="timeline">
        {events.map((event) => (
          <li key={event.id}>
            <time dateTime={event.created_at}>
              {new Date(event.created_at).toLocaleString("fi-FI")}
            </time>
            <strong>{AUDIT_EVENT_LABELS[event.event_type] ?? event.event_type}</strong>
            {Object.keys(sanitizeMetadata(event.metadata)).length > 0 ? (
              <dl className="field-list compact">
                {Object.entries(sanitizeMetadata(event.metadata)).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd className="mono">{Array.isArray(value) ? value.join(", ") : String(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
