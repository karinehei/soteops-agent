"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/FeedbackStates";
import { RequestListCard } from "@/components/RequestListCard";
import type { RequestOut } from "@/lib/api-types";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";

export default function RequestsPage() {
  const { user, loading: authLoading } = useRequireAuth(["requester", "operator"]);
  const [items, setItems] = useState<RequestOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isRequester = user?.role === "requester";

  useEffect(() => {
    if (authLoading) {
      return;
    }
    void api
      .listRequests()
      .then(setItems)
      .catch((err: Error) => setError(err instanceof ApiError ? err.message : "Lista epäonnistui"));
  }, [authLoading]);

  if (authLoading) {
    return <LoadingState />;
  }

  return (
    <main className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">{isRequester ? "Pyytäjä" : "Operaattori"}</p>
          <h1>{isRequester ? "Omat pyynnöt" : "Pyynnöt"}</h1>
        </div>
        {isRequester ? (
          <Link className="btn btn--primary" href="/requests/new" data-testid="new-request-link">
            Uusi pyyntö
          </Link>
        ) : null}
      </div>
      {error ? <ErrorState message={error} /> : null}
      {!items ? (
        <LoadingState label="Ladataan pyyntöjä…" />
      ) : items.length === 0 ? (
        <EmptyState
          title="Ei pyyntöjä"
          message={
            isRequester
              ? "Luo ensimmäinen synteettinen käyttöoikeuspyyntö."
              : "Ei näytettäviä pyyntöjä."
          }
        >
          {isRequester ? (
            <Link className="btn btn--primary" href="/requests/new">
              Luo pyyntö
            </Link>
          ) : null}
        </EmptyState>
      ) : (
        <ul className="request-list" data-testid="request-list">
          {items.map((item) => (
            <li key={item.id}>
              <RequestListCard href={`/requests/${item.id}`} request={item} />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
