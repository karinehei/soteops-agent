export default function HomePage() {
  return (
    <main>
      <h1>SoteOps Agent</h1>
      <p className="lede">
        Suomenkielinen portfolio-prototyyppi, joka valmistelee synteettisiä
        käyttöoikeuspyyntöjä ihmisen tarkistettavaksi ja välittää hyväksytyt pyynnöt
        simuloituun kohdejärjestelmään.
      </p>
      <section className="card">
        <h2>Työhypoteesi</h2>
        <p>
          Puuttuvien tietojen ja ristiriitaisten pyyntöjen havaitseminen ennen automaatiota
          voisi vähentää manuaalista uudelleenkäsittelyä. Tätä hyötyä ei ole validoitu.
        </p>
      </section>
      <section className="card">
        <h2>Demopolku (tulossa)</h2>
        <ol>
          <li>Pyytäjä lähettää synteettisen vapaatekstipyynnön.</li>
          <li>Malli poimii jäsennellyt kentät ja säilyttää tekstiotteet.</li>
          <li>Säännöt tunnistavat puutteet ja kielletyt yhdistelmät.</li>
          <li>Haku palauttaa versioidut synteettiset ohjeet.</li>
          <li>Malli selittää havainnot ja luonnostelee täsmennyspyynnön.</li>
          <li>Tarkistaja käsittelee tarkan jäsennellyn ehdotuksen.</li>
          <li>Hyväksynnän jälkeen sovellus lähettää sen mock-integraatioon.</li>
          <li>Virheet käsitellään ilman kaksoislähetyksiä.</li>
        </ol>
      </section>
      <p className="note">
        Kieli- ja käyttöliittymärunko on paikallisilla järjestelmäfonteilla. Ulkoisia
        fonttipalveluita ei ladata.
      </p>
    </main>
  );
}
