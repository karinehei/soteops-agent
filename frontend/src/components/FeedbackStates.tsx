export function LoadingState({ label = "Ladataan…" }: { label?: string }) {
  return (
    <div className="feedback feedback--loading" role="status" aria-live="polite" data-testid="loading">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({
  title = "Virhe",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="feedback feedback--error" role="alert" data-testid="error-state">
      <h2>{title}</h2>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          Yritä uudelleen
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="feedback feedback--empty" data-testid="empty-state">
      <h2>{title}</h2>
      <p>{message}</p>
    </div>
  );
}
