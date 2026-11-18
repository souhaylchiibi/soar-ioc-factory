import { useState, type ReactNode } from "react";
import { Play } from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDuration } from "../../lib/format";
import { ConfirmDialog, useToast } from "../ui/Feedback";

/**
 * Triggers an existing pipeline endpoint after explicit confirmation.
 * Visible only to analysts/admins (the API enforces it too). The toast
 * reports what the API actually returned — success is never assumed.
 */
export function OperationButton({ path, label, description, onDone, variant = "secondary", danger = false }: {
  path: string;
  label: string;
  description: ReactNode;
  onDone?: () => void;
  variant?: "primary" | "secondary";
  danger?: boolean;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!can("analyst")) return null;

  const run = async () => {
    setBusy(true);
    try {
      const res = await api.runOperation(path);
      const failed = Number((res as any)?.failed ?? (res as any)?.totals?.failed ?? 0);
      const summary = Object.entries(res)
        .filter(([, v]) => typeof v === "number")
        .map(([k, v]) => `${k}: ${v}`)
        .slice(0, 5)
        .join(" · ");
      toast({
        kind: failed > 0 ? "error" : "success",
        title: failed > 0 ? `${label} terminé avec ${failed} échec(s)` : `${label} terminé`,
        message: [summary, (res as any)?.duration_ms !== undefined ? `durée ${fmtDuration((res as any).duration_ms)}` : ""].filter(Boolean).join(" · "),
      });
      onDone?.();
    } catch (e) {
      toast({ kind: "error", title: `${label} : échec`, message: (e as Error).message });
    } finally {
      setBusy(false);
      setOpen(false);
    }
  };

  return (
    <>
      <button type="button" className={variant === "primary" ? "btn-primary h-8" : "btn-secondary h-8"} onClick={() => setOpen(true)}>
        <Play size={13} aria-hidden /> {label}
      </button>
      <ConfirmDialog open={open} title={`Lancer : ${label}`} confirmLabel="Lancer" danger={danger} busy={busy}
        onConfirm={run} onCancel={() => setOpen(false)}>
        {description}
        <p className="mt-2 text-[12px] text-fg-subtle">L'opération est exécutée par l'API sous votre identité et inscrite au journal d'audit.</p>
      </ConfirmDialog>
    </>
  );
}
