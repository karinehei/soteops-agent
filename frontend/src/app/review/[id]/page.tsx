"use client";

import { use } from "react";

import { RequestDetailView } from "@/components/RequestDetailView";
import { LoadingState } from "@/components/FeedbackStates";
import { useRequireAuth } from "@/lib/auth-context";

export default function ReviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, loading } = useRequireAuth(["reviewer"]);

  if (loading) {
    return <LoadingState />;
  }

  return <RequestDetailView key={id} requestId={id} user={user} mode="reviewer" />;
}
