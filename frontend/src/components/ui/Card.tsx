import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

export function Card({ title, subtitle, actions, children, className = "", bodyClass = "card-pad", id }: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`card min-w-0 animate-fade-in ${className}`} aria-labelledby={id && title ? `${id}-title` : undefined}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3 md:px-5">
          <div className="min-w-0">
            {title && <h2 id={id ? `${id}-title` : undefined} className="text-[13.5px] font-semibold text-fg">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[12px] text-fg-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function CardLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-0.5 text-[12px] font-medium text-fg-muted hover:text-accent-strong">
      {children}
      <ChevronRight size={14} aria-hidden />
    </Link>
  );
}

/** Label/value list for detail panels. */
export function DefList({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="divide-y divide-line/70 text-[13px]">
      {items.map(([k, v], i) => (
        <div key={i} className="flex items-start justify-between gap-4 py-2">
          <dt className="shrink-0 text-fg-muted">{k}</dt>
          <dd className="min-w-0 text-right break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
