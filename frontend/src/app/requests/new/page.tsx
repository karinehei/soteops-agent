import { Suspense } from "react";

import { LoadingState } from "@/components/FeedbackStates";
import { NewRequestClient } from "@/app/requests/new/NewRequestClient";

export default function NewRequestPage() {
  return (
    <main className="page page--narrow">
      <h1>Uusi käyttöoikeuspyyntö</h1>
      <Suspense fallback={<LoadingState label="Valmistellaan lomaketta…" />}>
        <NewRequestClient />
      </Suspense>
    </main>
  );
}
