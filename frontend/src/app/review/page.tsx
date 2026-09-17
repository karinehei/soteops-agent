"use client";

import { useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/FeedbackStates";
import { RequestListCard } from "@/components/RequestListCard";
import type { RequestOut } from "@/lib/api-types";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";

export default function ReviewQueuePage() {
  const { loading: authLoading } = useRequireAuth(["reviewer"]);
  const [items, setItems] = useState<RequestOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    void api
      .reviewQueue()
      .then(setItems)
      .catch((err: Error) => {
        if (err instanceof ApiError && err.status === 401) {
          return;
        }
        setError(err instanceof ApiError ? err.message : "Jono epäonnistui");
      });
  }, [authLoading]);

  if (authLoading) {
    return <LoadingState />;
  }

  return (
    <main className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Tarkastaja</p>
          <h1>Tarkastusjono</h1>
          <p className="help">
            Näytetään pyynnöt, jotka odottavat tarkastusta tai ovat tarkastuksessa. Hyväksyntä
            sitoo tarkan ehdotustiivitteen.
          </p>
        </div>
      </div>
      {error ? <ErrorState message={error} /> : null}
      {error ? null : !items ? (
        <LoadingState label="Ladataan jonoa…" />
      ) : items.length === 0 ? (
        <EmptyState title="Jono tyhjä" message="Ei tarkastusta odottavia pyyntöjä." />
      ) : (
        <ul className="request-list" data-testid="review-queue">
          {items.map((item) => (
            <li key={item.id}>
              <RequestListCard
                href={`/review/${item.id}`}
                request={item}
                extra={`rev ${item.revision}`}
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
