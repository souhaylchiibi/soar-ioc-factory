import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Node ≥ 25 ships its own `localStorage` global (undefined without
// --localstorage-file) that shadows jsdom's: provide an in-memory Storage.
class MemoryStorage implements Storage {
  private m = new Map<string, string>();
  get length() { return this.m.size; }
  clear() { this.m.clear(); }
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  key(i: number) { return [...this.m.keys()][i] ?? null; }
  removeItem(k: string) { this.m.delete(k); }
  setItem(k: string, v: string) { this.m.set(k, String(v)); }
}
for (const name of ["localStorage", "sessionStorage"] as const) {
  let ok = false;
  try { ok = typeof (globalThis as any)[name]?.getItem === "function"; } catch { ok = false; }
  if (!ok) Object.defineProperty(globalThis, name, { value: new MemoryStorage(), configurable: true, writable: true });
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
});

// jsdom gaps used by Recharts and the native <dialog>.
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as any).ResizeObserver ??= RO;

if (typeof HTMLDialogElement !== "undefined") {
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) { this.removeAttribute("open"); };
}
