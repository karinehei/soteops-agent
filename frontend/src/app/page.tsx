"use client";

import Link from "next/link";

import { DemoScenarioList } from "@/components/DemoScenarioList";
import { useAuth } from "@/lib/auth-context";

export default function HomePage() {
  const { user } = useAuth();
  const workspaceHref = user?.role === "reviewer" ? "/review" : "/requests";

  return (
    <main className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">Riippumaton portfolio-prototyyppi</p>
          <h1>Synteettiset käyttöoikeuspyynnöt ihmisen tarkistettavaksi</h1>
          <p className="lede">
            Valmistelee pyynnön, näyttää puuttuvat tiedot ja ohjeet, ja välittää vain
            hyväksytyn tarkan ehdotuksen mock-integraatioon. Mock tallentaa tietueen — se ei
            luo tilejä.
          </p>
        </div>
        <ol className="steps">
          <li>
            <span className="steps__n">1</span>
            <h2>Pyytäjä kuvaa pyynnön</h2>
            <p>Vapaateksti ja kentät. Malli ei myönnä oikeuksia.</p>
          </li>
          <li>
            <span className="steps__n">2</span>
            <h2>Säännöt tarkistavat</h2>
            <p>Deterministiset puutteet ja kiellot ennen tarkastusta.</p>
          </li>
          <li>
            <span className="steps__n">3</span>
            <h2>Ihminen hyväksyy</h2>
            <p>Hyväksyntä sitoo tarkan ehdotustiivisteen. Sitten mock-tietue.</p>
          </li>
        </ol>
        <div className="hero__actions">
          {user ? (
            <Link className="btn btn--primary" href={workspaceHref}>
              Jatka työtilaan
            </Link>
          ) : (
            <Link className="btn btn--primary" href="/login">
              Kirjaudu demotunnuksilla
            </Link>
          )}
          {!user || user.role === "requester" ? (
            <Link className="btn" href="/requests/new">
              Uusi pyyntö
            </Link>
          ) : null}
        </div>
      </section>
      <section className="card notice">
        <h2>Huomio</h2>
        <p>
          Työhypoteesi: puuttuvien tietojen havaitseminen ennen automaatiota voisi vähentää
          uudelleenkäsittelyä. Hyötyä <strong>ei ole validoitu</strong>. Prototyyppi ei edusta
          mitään oikeaa hyvinvointialuetta.
        </p>
      </section>
      <DemoScenarioList />
      <p className="note">
        Käyttöliittymä käyttää paikallisia järjestelmäfontteja. Ulkoisia fonttipalveluita ei
        ladata.
      </p>
    </main>
  );
}
