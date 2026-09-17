import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import type { RequestOut } from "@/lib/api-types";

export function RequestListCard({
  href,
  request,
  extra,
}: {
  href: string;
  request: RequestOut;
  extra?: string;
}) {
  return (
    <Link href={href} className="request-card">
      <div className="request-card__top">
        <div>
          <strong>{request.target_system ?? "Kohdejärjestelmä puuttuu"}</strong>
          {extra ? <span className="muted small"> · {extra}</span> : null}
        </div>
        <StatusBadge request={request} compact />
      </div>
      <p className="request-card__meta">
        {request.employee_identifier ?? "Työntekijätunnus puuttuu"}
        {" · "}
        {request.requested_access_role ?? "Oikeus puuttuu"}
        {" · "}
        {request.job_role ?? "Rooli puuttuu"}
      </p>
    </Link>
  );
}
