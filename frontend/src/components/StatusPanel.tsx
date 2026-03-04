interface StatusPanelProps {
  loading: boolean;
  error: string | null;
  hasData: boolean;
  emptyMessage: string;
}

export function StatusPanel({ loading, error, hasData, emptyMessage }: StatusPanelProps) {
  if (loading) {
    return (
      <div className="loading-panel">
        <div className="spinner" aria-label="Loading" role="status" />
      </div>
    );
  }

  if (error) {
    return <div className="panel error">{error}</div>;
  }

  if (!hasData) {
    return <div className="panel">{emptyMessage}</div>;
  }

  return null;
}
