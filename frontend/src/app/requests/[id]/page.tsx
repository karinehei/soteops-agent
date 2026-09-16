"use client";

import { use } from "react";

import { RequestDetailView } from "@/components/RequestDetailView";
import { LoadingState } from "@/components/FeedbackStates";
import { useRequireAuth } from "@/lib/auth-context";

export default function RequestDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, loading } = useRequireAuth(["requester", "reviewer", "operator"]);

  if (loading) {
    return <LoadingState />;
  }

  const mode = user.role === "requester" ? "requester" : "reviewer";
  return <RequestDetailView key={id} requestId={id} user={user} mode={mode} />;
}
