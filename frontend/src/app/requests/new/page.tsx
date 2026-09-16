import { Suspense } from "react";

import { LoadingState } from "@/components/FeedbackStates";
import { NewRequestClient } from "@/app/requests/new/NewRequestClient";

export default function NewRequestPage() {
  return (
    <main className="page page--narrow">
      <p className="eyebrow">Pyytäjä</p>
      <h1>Uusi käyttöoikeuspyyntö</h1>
      <Suspense fallback={<LoadingState label="Valmistellaan lomaketta…" />}>
        <NewRequestClient />
      </Suspense>
    </main>
  );
}
