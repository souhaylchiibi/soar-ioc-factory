import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";

export interface Column {
  key: string;
  label: string;
  className?: string;
  sortable?: boolean;
  align?: "left" | "right" | "center";
}

/** Data table with sticky header, optional server-side sort indicators. */
export function Table({ columns, children, sort, onSort, caption, minWidth = 720 }: {
  columns: Column[];
  children: ReactNode;
  sort?: { key: string; dir: "asc" | "desc" };
  onSort?: (key: string) => void;
  caption?: string;
  minWidth?: number;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse" style={{ minWidth }}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              const align = c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left";
              return (
                <th
                  key={c.key}
                  scope="col"
                  className={`th ${align} ${c.className ?? ""}`}
                  aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                >
                  {c.sortable && onSort ? (
                    <button type="button" onClick={() => onSort(c.key)}
                      className={`inline-flex cursor-pointer items-center gap-1 uppercase hover:text-fg ${active ? "text-fg" : ""}`}>
                      {c.label}
                      {active ? (sort!.dir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : null}
                    </button>
                  ) : (
                    c.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Row({ children, onClick, selected = false }: { children: ReactNode; onClick?: () => void; selected?: boolean }) {
  return (
    <tr
      onClick={onClick}
      className={`transition-colors ${onClick ? "cursor-pointer" : ""} ${selected ? "bg-accent/8" : "hover:bg-surface-2"}`}
    >
      {children}
    </tr>
  );
}

export function Pagination({ total, offset, limit, onChange }: {
  total: number; offset: number; limit: number; onChange: (offset: number) => void;
}) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-[12.5px] text-fg-muted">
      <span className="num">
        {total === 0 ? "0 résultat" : `${offset + 1}–${Math.min(offset + limit, total)} sur ${total}`}
      </span>
      <div className="flex items-center gap-1">
        <button type="button" className="icon-btn h-8 w-8 disabled:opacity-40" disabled={page <= 1}
          onClick={() => onChange(Math.max(0, offset - limit))} aria-label="Page précédente">
          <ChevronLeft size={16} />
        </button>
        <span className="num px-2">{page} / {pages}</span>
        <button type="button" className="icon-btn h-8 w-8 disabled:opacity-40" disabled={page >= pages}
          onClick={() => onChange(offset + limit)} aria-label="Page suivante">
          <ChevronRight size={16} />
        </button>
      </div>
    </nav>
  );
}
