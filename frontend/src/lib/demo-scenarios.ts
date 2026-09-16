import type { RequestWrite } from "@/lib/api-types";

export interface DemoScenario {
  id: string;
  label: string;
  description: string;
  hint: string;
  payload: RequestWrite;
  expectedPhase?: string;
}

/** Fictional systems and identities only — not real wellbeing-area data. */
export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: "complete-permanent",
    label: "Täydellinen vakituinen pyyntö",
    description: "Kaikki pakolliset kentät ja sallittu yhdistelmä demo-hr-testi + lukuoikeus.",
    hint: "Odottaa tarkastusta ilman puutteita.",
    payload: {
      original_text:
        "Pyydän lukuoikeutta demo-hr-testi -järjestelmään synteettiselle työntekijälle EMP-1001. " +
        "Rooli sairaanhoitaja, työsuhde vakituinen, yksikkö demo-osasto, alkaen 2026-10-01.",
      employee_identifier: "EMP-1001",
      employment_type: "vakituinen",
      job_role: "sairaanhoitaja",
      unit: "demo-osasto",
      target_system: "demo-hr-testi",
      requested_access_role: "lukuoikeus",
      start_date: "2026-10-01",
      end_date: null,
    },
    expectedPhase: "waiting_review",
  },
  {
    id: "temporary-missing-end",
    label: "Määräaikainen ilman loppupäivää",
    description: "Kirjaaja-oikeus ilman loppupäivää — deterministinen sääntö estää hyväksynnän.",
    hint: "Odottaa täsmennystä: loppupäivä puuttuu.",
    payload: {
      original_text:
        "Pyydän kirjaaja-oikeutta demo-hr-testi -järjestelmään EMP-2002 määräaikaisena. " +
        "Rooli sairaanhoitaja, yksikkö demo-osasto, alkaen 2026-11-01. Loppupäivää ei vielä tiedossa.",
      employee_identifier: "EMP-2002",
      employment_type: "maaraaikainen",
      job_role: "sairaanhoitaja",
      unit: "demo-osasto",
      target_system: "demo-hr-testi",
      requested_access_role: "kirjaaja",
      start_date: "2026-11-01",
      end_date: null,
    },
    expectedPhase: "needs_clarification",
  },
  {
    id: "prohibited-role",
    label: "Kielletty käyttöoikeus",
    description: "tuotanto-superadmin on eksplisiittisesti kielletty policy-v1 -säännöissä.",
    hint: "Ei kelpaa hyväksyntään ennen korjausta.",
    payload: {
      original_text:
        "Pyydän tuotanto-superadmin -oikeutta demo-hr-testi -järjestelmään EMP-3003. " +
        "Rooli sairaanhoitaja, vakituinen, yksikkö demo-osasto, alkaen 2026-10-01.",
      employee_identifier: "EMP-3003",
      employment_type: "vakituinen",
      job_role: "sairaanhoitaja",
      unit: "demo-osasto",
      target_system: "demo-hr-testi",
      requested_access_role: "tuotanto-superadmin",
      start_date: "2026-10-01",
      end_date: null,
    },
    expectedPhase: "needs_clarification",
  },
  {
    id: "conflicting-instructions",
    label: "Ristiriitaiset ohjeet",
    description:
      "Nouto voi palauttaa ristiriitaiset SYNTHETIC-ohjeet A ja B. Säännöt eivät muutu noudon takia.",
    hint: "Tarkastaja näkee molemmat ohjeversiot; deterministiset säännöt ratkaisevat kelpoisuuden.",
    payload: {
      original_text:
        "Pyydän kirjaaja-oikeutta demo-hr-testi -järjestelmään EMP-4004 määräaikaisena ilman loppupäivää. " +
        "Ristiriitaiset ohjeet voivat tulla näkyviin. Yksikkö demo-osasto, alkaen 2026-12-01.",
      employee_identifier: "EMP-4004",
      employment_type: "maaraaikainen",
      job_role: "sairaanhoitaja",
      unit: "demo-osasto",
      target_system: "demo-hr-testi",
      requested_access_role: "kirjaaja",
      start_date: "2026-12-01",
      end_date: null,
    },
    expectedPhase: "needs_clarification",
  },
  {
    id: "downstream-timeout",
    label: "Alasvirran timeout onnistuneen käsittelyn jälkeen",
    description:
      "Hyväksynnän jälkeen lähetyksessä voi simuloida kadonnutta vastausta (lost-response). " +
      "Sama idempotenssiavain reconciloi tuloksen.",
    hint: "Käytä lähetysnäkymän demo-vikakytkintä lost-response.",
    payload: {
      original_text:
        "Pyydän lukuoikeutta demo-hr-testi -järjestelmään EMP-5005 vakituiseen työsuhteeseen. " +
        "Rooli sairaanhoitaja, yksikkö demo-osasto, alkaen 2026-10-01.",
      employee_identifier: "EMP-5005",
      employment_type: "vakituinen",
      job_role: "sairaanhoitaja",
      unit: "demo-osasto",
      target_system: "demo-hr-testi",
      requested_access_role: "lukuoikeus",
      start_date: "2026-10-01",
      end_date: null,
    },
    expectedPhase: "waiting_review",
  },
  {
    id: "approval-bypass",
    label: "Hyväksynnän ohitusyritys",
    description:
      "Luo kelvollinen pyyntö, aloita tarkastus, muokkaa pyyntöä pyytäjänä ja yritä hyväksyä vanhalla tiivisteellä.",
    hint: "Palvelin hylkää vanhentuneen ehdotuksen (409). UI ei näytä onnistunutta hyväksyntää ennen vahvistusta.",
    payload: {
      original_text:
        "Pyydän lukuoikeutta demo-hr-testi -järjestelmään EMP-6006. " +
        "Rooli sairaanhoitaja, vakituinen, yksikkö demo-osasto, alkaen 2026-10-01.",
      employee_identifier: "EMP-6006",
      employment_type: "vakituinen",
      job_role: "sairaanhoitaja",
      unit: "demo-osasto",
      target_system: "demo-hr-testi",
      requested_access_role: "lukuoikeus",
      start_date: "2026-10-01",
      end_date: null,
    },
    expectedPhase: "waiting_review",
  },
];

export const DEMO_USERS = {
  requester: {
    email: "aino.esimerkki@demo.invalid",
    password: "demo-aino-passphrase",
    displayName: "Aino Esimerkki",
  },
  reviewer: {
    email: "ville.valvoja@demo.invalid",
    password: "demo-ville-passphrase",
    displayName: "Ville Valvoja",
  },
  operator: {
    email: "outi.operaattori@demo.invalid",
    password: "demo-outi-passphrase",
    displayName: "Outi Operaattori",
  },
} as const;
