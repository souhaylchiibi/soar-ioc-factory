import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { AlertTriangle, Eye, EyeOff, Lock } from "lucide-react";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { BrandMark } from "../components/layout/Sidebar";

export default function Login() {
  const { status, login } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === "authenticated") {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      const s = err instanceof ApiError ? err.status : undefined;
      setError(
        s === 423 ? "Compte temporairement verrouillé après plusieurs échecs. Réessayez plus tard."
          : s === 429 ? "Trop de tentatives depuis ce poste. Patientez une minute."
          : s === 401 ? "Identifiant ou mot de passe incorrect."
          : (err as Error).message,
      );
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-[1fr_minmax(420px,520px)]">
      <section className="relative hidden overflow-hidden border-r border-line bg-surface lg:flex lg:flex-col lg:justify-between lg:p-12" aria-hidden>
        <BrandMark />
        <div className="max-w-md">
          <p className="eyebrow mb-3">Cyber Threat Intelligence</p>
          <h1 className="text-[28px] font-semibold leading-tight tracking-tight">
            Chaque indicateur, de la collecte au retrait vérifié.
          </h1>
          <p className="mt-4 text-[14px] text-fg-muted">
            Collecte, normalisation, enrichissement, score explicable, publication relue et expiration
            contrôlée — chaque étape laisse une preuve dans le journal d'audit.
          </p>
          <ol className="mt-8 grid grid-cols-5 gap-1.5">
            {["Collecte", "Score", "Décision", "Publication", "Retrait"].map((s, i) => (
              <li key={s}>
                <div className="h-1 rounded-full" style={{ background: i < 4 ? "var(--color-accent)" : "var(--color-line-strong)", opacity: 1 - i * 0.12 }} />
                <div className="mt-2 text-[11px] text-fg-subtle">{s}</div>
              </li>
            ))}
          </ol>
        </div>
        <p className="text-[11.5px] text-fg-subtle">Accès réservé aux analystes SOC autorisés. Toutes les connexions sont journalisées.</p>
      </section>

      <main className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-[360px]" aria-labelledby="login-title" noValidate>
          <div className="mb-8 lg:hidden"><BrandMark /></div>
          <h2 id="login-title" className="text-[20px] font-semibold tracking-tight">Connexion</h2>
          <p className="mt-1 text-[13px] text-fg-muted">Identifiez-vous pour accéder à la console SOC.</p>

          {error && (
            <div role="alert" className="mt-5 flex items-start gap-2.5 rounded-md border border-danger/30 bg-danger/8 p-3 text-[12.5px]">
              <AlertTriangle size={15} className="mt-0.5 shrink-0 text-danger" aria-hidden />
              <span>{error}</span>
            </div>
          )}

          <div className="mt-6 space-y-4">
            <div>
              <label htmlFor="username" className="mb-1.5 block text-[12.5px] font-medium">Identifiant</label>
              <input id="username" className="input h-10" autoComplete="username" required autoFocus
                value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-[12.5px] font-medium">Mot de passe</label>
              <div className="relative">
                <input id="password" className="input h-10 pr-10" type={show ? "text" : "password"} autoComplete="current-password" required
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" onClick={() => setShow((s) => !s)} className="icon-btn absolute right-0.5 top-0.5 h-9 w-9"
                  aria-label={show ? "Masquer le mot de passe" : "Afficher le mot de passe"}>
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          </div>

          <button type="submit" className="btn-primary mt-6 h-10 w-full" disabled={busy || !username || !password}>
            <Lock size={15} aria-hidden /> {busy ? "Vérification…" : "Se connecter"}
          </button>
          <p className="mt-4 text-[11.5px] text-fg-subtle">
            Après 5 échecs consécutifs, le compte est verrouillé 15 minutes.
          </p>
        </form>
      </main>
    </div>
  );
}
