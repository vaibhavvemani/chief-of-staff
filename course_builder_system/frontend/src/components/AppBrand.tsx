import { Link } from "react-router-dom";

export function AppBrand({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/courses" className={`app-brand ${compact ? "brand-compact" : ""}`} aria-label="Course Builder Studio home">
      <span className="brand-glyph" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>
        <strong>Course Builder</strong>
        {!compact ? <small>Studio</small> : null}
      </span>
    </Link>
  );
}

