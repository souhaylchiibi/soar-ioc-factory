import { useState, type FormEvent } from "react";
import { UserPlus } from "lucide-react";
import { api, type Role, type UserInfo } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, fmtRelative } from "../lib/format";
import { useApi } from "../lib/useApi";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { AsyncBlock, ErrorState } from "../components/ui/States";
import { Badge } from "../components/ui/Badge";
import { Row, Table } from "../components/ui/Table";
import { ConfirmDialog, useToast } from "../components/ui/Feedback";

const ROLES: { value: Role; label: string; describe: string }[] = [
  { value: "viewer", label: "Lecteur", describe: "Consultation uniquement" },
  { value: "analyst", label: "Analyste", describe: "Lance les opérations, qualifie, décide" },
  { value: "admin", label: "Administrateur", describe: "Analyste + gestion des comptes" },
];

export default function Users() {
  const { can, me } = useAuth();
  const toast = useToast();
  const users = useApi(api.users, [], { enabled: can("admin") });
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "analyst" as Role });
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ user: UserInfo; change: { role?: Role; is_active?: boolean } } | null>(null);
  const [busy, setBusy] = useState(false);

  if (!can("admin")) return <ErrorState error={new Error("Cette page est réservée aux administrateurs.")} />;

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setFormError(null);
    try {
      const u = await api.createUser(form);
      toast({ kind: "success", title: `Compte « ${u.username} » créé`, message: `Rôle : ${ROLES.find((r) => r.value === u.role)?.label}` });
      setForm({ username: "", email: "", password: "", role: "analyst" });
      users.refresh();
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const apply = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      await api.updateUser(pending.user.id, pending.change);
      toast({ kind: "success", title: `Compte « ${pending.user.username} » modifié` });
      users.refresh();
    } catch (err) {
      toast({ kind: "error", title: "Modification refusée", message: (err as Error).message });
    } finally {
      setBusy(false);
      setPending(null);
    }
  };

  return (
    <>
      <PageHeader title="Utilisateurs" description="Comptes et rôles. Chaque création, changement de rôle ou désactivation est inscrit au journal d'audit." onRefresh={users.refresh} updatedAt={users.updatedAt} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card bodyClass="" title="Comptes">
          <AsyncBlock state={users} rows={6}>
            {(list) => (
              <Table minWidth={760} columns={[{ key: "u", label: "Utilisateur" }, { key: "r", label: "Rôle" }, { key: "s", label: "État" }, { key: "l", label: "Dernière connexion" }, { key: "a", label: "Actions", align: "right" }]}>
                {list.map((u) => {
                  const self = u.id === me?.user?.id;
                  const locked = u.locked_until && new Date(u.locked_until) > new Date();
                  return (
                    <Row key={u.id}>
                      <td className="td"><div className="font-medium">{u.username}{self && <span className="ml-2 text-[11.5px] text-fg-subtle">(vous)</span>}</div><div className="text-[11.5px] text-fg-subtle">{u.email}</div></td>
                      <td className="td">
                        <select aria-label={`Rôle de ${u.username}`} className="input h-8 w-40 cursor-pointer" value={u.role} disabled={self}
                          onChange={(e) => setPending({ user: u, change: { role: e.target.value as Role } })}>
                          {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                        </select>
                      </td>
                      <td className="td">{!u.is_active ? <Badge tone="neutral">désactivé</Badge> : locked ? <Badge tone="warn" title={`jusqu'au ${fmtDate(u.locked_until)}`}>verrouillé</Badge> : <Badge tone="ok" dot>actif</Badge>}</td>
                      <td className="td text-[12px] text-fg-muted" title={fmtDate(u.last_login_at)}>{fmtRelative(u.last_login_at)}</td>
                      <td className="td text-right">
                        {!self && (
                          <button type="button" className="btn-ghost h-8" onClick={() => setPending({ user: u, change: { is_active: !u.is_active } })}>
                            {u.is_active ? "Désactiver" : "Réactiver"}
                          </button>
                        )}
                      </td>
                    </Row>
                  );
                })}
              </Table>
            )}
          </AsyncBlock>
        </Card>

        <Card title="Nouveau compte">
          <form onSubmit={create} className="space-y-3" noValidate>
            {formError && <ErrorState error={new Error(formError)} compact />}
            {([["username", "Identifiant", "text", "username"], ["email", "E-mail", "email", "email"], ["password", "Mot de passe initial", "password", "new-password"]] as const).map(([k, label, type, ac]) => (
              <div key={k}>
                <label htmlFor={`nu-${k}`} className="mb-1 block text-[12px] font-medium">{label}</label>
                <input id={`nu-${k}`} type={type} autoComplete={ac} className="input" value={form[k]} required
                  onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </div>
            ))}
            <p className="text-[11.5px] text-fg-subtle">12 caractères minimum, au moins 3 types parmi minuscules, majuscules, chiffres et symboles.</p>
            <fieldset>
              <legend className="mb-1.5 text-[12px] font-medium">Rôle</legend>
              <div className="space-y-1.5">
                {ROLES.map((r) => (
                  <label key={r.value} className="flex cursor-pointer items-start gap-2.5 rounded-md border border-line px-3 py-2 has-[:checked]:border-accent/60 has-[:checked]:bg-accent/5">
                    <input type="radio" name="role" value={r.value} checked={form.role === r.value} onChange={() => setForm({ ...form, role: r.value })} className="mt-1 accent-[var(--color-accent)]" />
                    <span className="text-[12.5px]"><span className="font-medium">{r.label}</span><span className="block text-fg-subtle">{r.describe}</span></span>
                  </label>
                ))}
              </div>
            </fieldset>
            <button type="submit" className="btn-primary w-full" disabled={creating || !form.username || !form.email || form.password.length < 12}>
              <UserPlus size={15} aria-hidden /> {creating ? "Création…" : "Créer le compte"}
            </button>
          </form>
        </Card>
      </div>

      <ConfirmDialog open={!!pending} busy={busy} danger={pending?.change.is_active === false}
        title={pending ? `Modifier « ${pending.user.username} »` : ""} onCancel={() => setPending(null)} onConfirm={apply}>
        {pending?.change.role && <p>Nouveau rôle : <b>{ROLES.find((r) => r.value === pending.change.role)?.label}</b>. L'effet est immédiat, y compris pour les sessions ouvertes.</p>}
        {pending?.change.is_active === false && <p>Le compte ne pourra plus se connecter et ses jetons en cours seront refusés immédiatement.</p>}
        {pending?.change.is_active === true && <p>Le compte pourra de nouveau se connecter.</p>}
      </ConfirmDialog>
    </>
  );
}
