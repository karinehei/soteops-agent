"use client";

import { useState, type FormEvent } from "react";

import { ErrorState } from "@/components/FeedbackStates";
import { DEMO_USERS } from "@/lib/demo-scenarios";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState<string>(DEMO_USERS.requester.email);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kirjautuminen epäonnistui");
    } finally {
      setBusy(false);
    }
  }

  function fillDemo(role: keyof typeof DEMO_USERS) {
    setEmail(DEMO_USERS[role].email);
    setPassword(DEMO_USERS[role].password);
  }

  return (
    <main className="page page--narrow">
      <h1>Demokirjautuminen</h1>
      <p className="help">
        Paikallinen istunto HttpOnly-evästeellä. Ei Entra ID:tä eikä tuotantotunnistusta.
      </p>
      <form className="card stack" onSubmit={(event) => void handleSubmit(event)} data-testid="login-form">
        <div className="field">
          <label htmlFor="email">Sähköposti</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Salasana</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        {error ? <ErrorState message={error} /> : null}
        <button type="submit" className="btn btn--primary" disabled={busy} data-testid="login-submit">
          {busy ? "Kirjaudutaan…" : "Kirjaudu"}
        </button>
      </form>
      <section className="card">
        <h2>Demotunnukset</h2>
        <div className="btn-row">
          <button type="button" className="btn btn--ghost" onClick={() => fillDemo("requester")}>
            Pyytäjä
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => fillDemo("reviewer")}>
            Tarkastaja
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => fillDemo("operator")}>
            Operaattori
          </button>
        </div>
        <p className="muted small">Salasanat ovat synteettisiä demo-tunnuksia — eivät oikeita tunnuksia.</p>
      </section>
    </main>
  );
}
