import { PROCESSING_PHASE_LABELS, requestStatusLabel } from "@/lib/labels";
import { deriveProcessingState } from "@/lib/processing-state";
import type { RequestOut } from "@/lib/api-types";

const TONE_CLASS: Record<string, string> = {
  neutral: "badge--neutral",
  info: "badge--info",
  success: "badge--success",
  warning: "badge--warning",
  danger: "badge--danger",
};

export function StatusBadge({ request }: { request: RequestOut }) {
  const state = deriveProcessingState(request);
  return (
    <div className="status-stack" data-testid="processing-status">
      <span className={`badge ${TONE_CLASS[state.tone]}`}>
        {PROCESSING_PHASE_LABELS[state.phase]}
      </span>
      <span className="muted small">{requestStatusLabel(request.status)}</span>
      {state.detail ? <p className="status-detail">{state.detail}</p> : null}
    </div>
  );
}
