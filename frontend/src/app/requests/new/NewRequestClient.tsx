"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { LoadingState } from "@/components/FeedbackStates";
import { RequestForm } from "@/components/RequestForm";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-context";
import { DEMO_SCENARIOS } from "@/lib/demo-scenarios";

export function NewRequestClient() {
  const router = useRouter();
  const params = useSearchParams();
  const { loading: authLoading } = useRequireAuth(["requester"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initial = useMemo(() => {
    const scenarioId = params.get("scenario");
    return DEMO_SCENARIOS.find((item) => item.id === scenarioId)?.payload;
  }, [params]);

  if (authLoading) {
    return <LoadingState />;
  }

  async function handleSubmit(payload: Parameters<typeof api.createRequest>[0]) {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createRequest(payload);
      router.push(`/requests/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Luonti epäonnistui");
      setBusy(false);
    }
  }

  return (
    <>
      {initial ? (
        <p className="notice" role="status">
          Esitäytetty demoskenaario: {params.get("scenario")}
        </p>
      ) : null}
      <section className="card">
        <RequestForm
          initial={initial}
          submitLabel="Lähetä valmisteltavaksi"
          busy={busy}
          error={error}
          onSubmit={handleSubmit}
        />
      </section>
    </>
  );
}
