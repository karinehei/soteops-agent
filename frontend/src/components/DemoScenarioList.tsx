"use client";

import Link from "next/link";

import { DEMO_SCENARIOS } from "@/lib/demo-scenarios";

export function DemoScenarioList() {
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
            <Link
              className="btn btn--ghost"
              href={`/requests/new?scenario=${scenario.id}`}
              data-testid={`scenario-${scenario.id}`}
            >
              Käytä skenaariota
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
