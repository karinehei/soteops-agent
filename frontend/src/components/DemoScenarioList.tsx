"use client";

import Link from "next/link";

import { DEMO_SCENARIOS } from "@/lib/demo-scenarios";
import { useAuth } from "@/lib/auth-context";

export function DemoScenarioList() {
  const { user } = useAuth();
  const canStart = !user || user.role === "requester";

  return (
    <section className="card" aria-labelledby="demo-scenarios-heading">
      <h2 id="demo-scenarios-heading">Merkittyjä demoskenaarioita</h2>
      <p className="help">
        Kaikki henkilöt, järjestelmät ja ohjeet ovat fiktiivisiä. Prototyyppi on riippumaton eikä
        kopioi hyvinvointialueen brändiä.
      </p>
      <ul className="scenario-list">
        {DEMO_SCENARIOS.map((scenario) => (
          <li key={scenario.id} className="scenario-item">
            <h3>{scenario.label}</h3>
            <p>{scenario.description}</p>
            <p className="muted small">{scenario.hint}</p>
            {canStart ? (
              <Link
                className="btn btn--ghost"
                href={`/requests/new?scenario=${scenario.id}`}
                data-testid={`scenario-${scenario.id}`}
              >
                Käytä skenaariota
              </Link>
            ) : (
              <p className="muted small">Kirjaudu pyytäjänä käyttääksesi skenaariota.</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
