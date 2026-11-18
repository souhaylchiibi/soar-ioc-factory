import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

/* ------------------------------------------------------------------ toasts */
type ToastKind = "success" | "error" | "info";
interface Toast { id: number; kind: ToastKind; title: string; message?: string }

const ToastCtx = createContext<(t: Omit<Toast, "id">) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all.slice(-3), { ...t, id }]);
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), t.kind === "error" ? 9000 : 5000);
  }, []);
  const icons = { success: CheckCircle2, error: XCircle, info: Info };
  const tones = { success: "text-ok", error: "text-danger", info: "text-info" };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => {
          const Icon = icons[t.kind];
          return (
            <div key={t.id} role={t.kind === "error" ? "alert" : "status"}
              className="pointer-events-auto flex animate-fade-in items-start gap-3 rounded-lg border border-line-strong bg-surface-2 p-3.5 shadow-lg shadow-black/40">
              <Icon size={18} className={`mt-0.5 shrink-0 ${tones[t.kind]}`} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold">{t.title}</p>
                {t.message && <p className="mt-0.5 break-words text-[12.5px] text-fg-muted">{t.message}</p>}
              </div>
              <button type="button" className="icon-btn -m-1 h-7 w-7" aria-label="Fermer"
                onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}>
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

/* ---------------------------------------------------------- confirm dialog */
/**
 * Confirmation before any sensitive action. Uses the native <dialog> element
 * (focus trap, Escape, inert background handled by the browser).
 */
export function ConfirmDialog({ open, title, children, confirmLabel = "Confirmer", danger = false, busy = false, onConfirm, onCancel }: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal?.();
    if (!open && d.open) d.close?.();
  }, [open]);
  return (
    <dialog ref={ref} onCancel={(e) => { e.preventDefault(); if (!busy) onCancel(); }}
      aria-labelledby="confirm-title"
      className="m-auto w-[min(460px,calc(100vw-2rem))] rounded-xl border border-line-strong bg-surface p-0 text-fg backdrop:bg-black/60">
      {open && (
        <div className="p-5">
          <div className="flex items-start gap-3">
            <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${danger ? "bg-danger/15 text-danger" : "bg-accent/15 text-accent-strong"}`}>
              <AlertTriangle size={18} aria-hidden />
            </div>
            <div className="min-w-0">
              <h2 id="confirm-title" className="text-[15px] font-semibold">{title}</h2>
              <div className="mt-1.5 text-[13px] text-fg-muted">{children}</div>
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={onCancel} disabled={busy}>Annuler</button>
            <button type="button" className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm} disabled={busy} autoFocus>
              {busy ? "Exécution…" : confirmLabel}
            </button>
          </div>
        </div>
      )}
    </dialog>
  );
}
