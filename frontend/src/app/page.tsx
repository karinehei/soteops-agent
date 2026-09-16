import Link from "next/link";

import { DemoScenarioList } from "@/components/DemoScenarioList";

export default function HomePage() {
  return (
    <main className="page">
      <h1>SoteOps Agent</h1>
      <p className="lede">
        Riippumaton suomenkielinen portfolio-prototyyppi. Valmistelee synteettisiä
        käyttöoikeuspyyntöjä ihmisen tarkistettavaksi ja välittää hyväksytyt ehdotukset
        mock-integraatioon. Mock tallentaa pyyntötietueen — se ei luo tilejä.
      </p>
      <section className="card notice">
        <h2>Huomio</h2>
        <p>
          Työhypoteesi: puuttuvien tietojen havaitseminen ennen automaatiota voisi vähentää
          uudelleenkäsittelyä. Hyötyä <strong>ei ole validoitu</strong>. Prototyyppi ei edusta
          mitään oikeaa hyvinvointialuetta.
        </p>
      </section>
      <section className="card">
        <h2>Aloita</h2>
        <div className="btn-row">
          <Link className="btn btn--primary" href="/login">
            Kirjaudu demotunnuksilla
          </Link>
          <Link className="btn" href="/requests">
            Pyytäjän näkymä
          </Link>
          <Link className="btn" href="/review">
            Tarkastajan jono
          </Link>
        </div>
      </section>
      <DemoScenarioList />
      <p className="note">
        Käyttöliittymä käyttää paikallisia järjestelmäfontteja. Ulkoisia fonttipalveluita ei
        ladata.
      </p>
    </main>
  );
}
