import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../lib/auth";
import { ToastProvider } from "../components/ui/Feedback";
import type { Me, Role } from "../lib/api";

export const me = (role: Role = "analyst"): Me => ({
  actor: "ana", role, is_service: false,
  user: { id: "u1", username: "ana", email: "ana@test.local", role, is_active: true, created_at: null, last_login_at: null, locked_until: null },
});

/** Render a page inside the real providers at a given URL. */
export function renderAt(ui: ReactNode, { path = "/", route = "*" }: { path?: string; route?: string } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path={route} element={ui} />
            <Route path="/login" element={<p>login-page</p>} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}
