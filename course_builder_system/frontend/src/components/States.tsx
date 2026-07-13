export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div className="state-page" role="status" aria-live="polite">
      <div className="loading-orbit" aria-hidden="true"><span /></div>
      <h2>{label}</h2>
      <p>Reading the latest course artifacts and review state.</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-page state-error" role="alert">
      <div className="state-symbol" aria-hidden="true">!</div>
      <h2>We couldn’t open this workspace</h2>
      <p>{message}</p>
      {onRetry ? <button className="button button-primary" onClick={onRetry}>Try again</button> : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-lines" aria-hidden="true"><span /><span /><span /></div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}

