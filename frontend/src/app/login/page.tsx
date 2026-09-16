"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ErrorState } from "@/components/FeedbackStates";
import { DEMO_USERS } from "@/lib/demo-scenarios";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const ROLE_COPY: Record<
  keyof typeof DEMO_USERS,
  { title: string; blurb: string }
> = {
  requester: {
    title: "Pyytäjä",
    blurb: "Luo ja täsmentää synteettisen käyttöoikeuspyynnön.",
  },
  reviewer: {
    title: "Tarkastaja",
    blurb: "Hyväksyy, hylkää tai odottaa täsmennystä. Ei mallin päätös.",
  },
  operator: {
    title: "Operaattori",
    blurb: "Näkee pyyntöjä ja voi yrittää mock-lähetystä. Ei hyväksy.",
  },
};

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState<string>(DEMO_USERS.requester.email);
  const [password, setPassword] = useState("");
  const [selected, setSelected] = useState<keyof typeof DEMO_USERS>("requester");
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
    setSelected(role);
    setEmail(DEMO_USERS[role].email);
    setPassword(DEMO_USERS[role].password);
  }

  return (
    <main className="page page--narrow">
      <Link className="brand login-brand" href="/">
        <span className="brand__mark" aria-hidden="true" />
        SoteOps Agent
      </Link>
      <h1>Demokirjautuminen</h1>
      <p className="help">
        Paikallinen istunto HttpOnly-evästeellä. Ei Entra ID:tä eikä tuotantotunnistusta.
      </p>
      <div className="role-grid" role="group" aria-label="Demoroolit">
        {(Object.keys(ROLE_COPY) as Array<keyof typeof DEMO_USERS>).map((role) => (
          <button
            key={role}
            type="button"
            className="role-card"
            aria-pressed={selected === role}
            disabled={busy}
            onClick={() => fillDemo(role)}
          >
            <strong>{ROLE_COPY[role].title}</strong>
            <span>{ROLE_COPY[role].blurb}</span>
          </button>
        ))}
      </div>
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
      <p className="muted small">
        Salasanat ovat synteettisiä demo-tunnuksia — eivät oikeita tunnuksia. Valitse rooli
        täyttääksesi tunnukset, sitten Kirjaudu.
      </p>
    </main>
  );
}
