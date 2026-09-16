import type { ProposalOut } from "@/lib/api-types";
import { formatFieldName, VIOLATION_LABELS } from "@/lib/labels";
import { isApprovable } from "@/lib/processing-state";

const FAKE_LABEL = "SYNTEETTINEN FAKE-TARJOAJA";

function asText(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function SourceReferenceCard({ source }: { source: Record<string, unknown> }) {
  const title =
    asText(source.title) ?? asText(source.source_id) ?? asText(source.source) ?? "Lähde";
  const version = asText(source.version);
  const excerpt = asText(source.excerpt);
  const label = asText(source.synthetic_label);
  const documentId = asText(source.document_id);
  const validFrom = asText(source.valid_from);
  const validTo = asText(source.valid_to);
  const known =
    asText(source.title) ||
    asText(source.source_id) ||
    asText(source.excerpt) ||
    asText(source.document_id);

  return (
    <article className="source-card">
      <h3>{title}</h3>
      <p className="muted small">
        {label ? `${label} · ` : null}
        {version ? `versio ${version}` : null}
        {documentId ? ` · ${documentId}` : null}
        {validFrom ? ` · ${validFrom}` : null}
        {validTo ? `–${validTo}` : null}
      </p>
      {excerpt ? <p>{excerpt}</p> : null}
      <p className="help">Ohje on näyttöä tarkastajalle, ei valtuutus.</p>
      {!known ? <pre className="source-json">{JSON.stringify(source, null, 2)}</pre> : null}
    </article>
  );
}

export function ProposalPanel({
  proposal,
  showApprovalEligibility = false,
}: {
  proposal: ProposalOut;
  showApprovalEligibility?: boolean;
}) {
  const eligible = isApprovable(proposal);
  const hasFindings = proposal.missing_fields.length > 0 || proposal.rule_violations.length > 0;
  const providerLabel =
    typeof proposal.provider_metadata.llm_label === "string"
      ? proposal.provider_metadata.llm_label
      : typeof proposal.provider_metadata.fake_output === "boolean" &&
          proposal.provider_metadata.fake_output
        ? FAKE_LABEL
        : null;

  return (
    <div className="stack" data-testid="proposal-panel">
      {showApprovalEligibility ? (
        <section className="card card--policy" aria-labelledby="policy-heading">
          <h2 id="policy-heading">Deterministinen päätös (säännöt)</h2>
          <p
            className={eligible ? "eligibility eligibility--ok" : "eligibility eligibility--no"}
            data-testid="approval-eligibility"
          >
            {eligible
              ? "Ehdotus kelpaa hyväksyntään nykyisten sääntöjen mukaan."
              : "Ehdotus ei kelpaa hyväksyntään ennen puutteiden korjausta."}
          </p>
          <p className="help">
            Hyväksyntä on ihmisen toimenpide. Malli ei myönnä käyttöoikeuksia eikä valitse
            hyväksyjää.
          </p>
        </section>
      ) : null}

      <section className="card" aria-labelledby="extracted-heading">
        <h2 id="extracted-heading">Poimitut kentät</h2>
        <dl className="field-list">
          {Object.entries(proposal.extracted_fields).map(([key, value]) => (
            <div key={key}>
              <dt>{formatFieldName(key)}</dt>
              <dd>{value === null || value === "" ? "—" : String(value)}</dd>
              {proposal.excerpts[key] ? (
                <dd className="excerpt">
                  <span className="excerpt-label">Tekstiotteet:</span> {proposal.excerpts[key]}
                </dd>
              ) : null}
            </div>
          ))}
        </dl>
      </section>

      <section
        className={hasFindings ? "card card--warning" : "card card--ok"}
        aria-labelledby="findings-heading"
      >
        <h2 id="findings-heading">Puuttuvat tiedot ja sääntöhavainnot</h2>
        {!hasFindings ? (
          <p>Ei puuttuvia kenttiä eikä estäviä sääntöhavaintoja.</p>
        ) : (
          <>
            {proposal.missing_fields.length > 0 ? (
              <div>
                <h3>Puuttuvat tiedot</h3>
                <ul data-testid="missing-fields">
                  {proposal.missing_fields.map((field) => (
                    <li key={field}>{formatFieldName(field)}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {proposal.rule_violations.length > 0 ? (
              <div>
                <h3>Sääntöhavainnot</h3>
                <ul data-testid="rule-violations">
                  {proposal.rule_violations.map((item, index) => (
                    <li key={`${item.code}-${index}`}>
                      <strong>{VIOLATION_LABELS[item.code] ?? item.code}</strong>
                      {item.message ? `: ${item.message}` : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section className="card" aria-labelledby="sources-heading">
        <h2 id="sources-heading">Ohjelähteet ja versiot</h2>
        {proposal.source_references.length === 0 ? (
          <p>Ei noudettuja ohjeita.</p>
        ) : (
          <ul className="source-list" data-testid="source-references">
            {proposal.source_references.map((ref, index) => (
              <li key={index}>
                <SourceReferenceCard source={ref} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card card--ai" aria-labelledby="ai-heading">
        <h2 id="ai-heading">Mallin selitys (ei päätös)</h2>
        {providerLabel ? <p className="fake-label">{providerLabel}</p> : null}
        <p>{proposal.explanation_text}</p>
        {proposal.clarification_draft ? (
          <div>
            <h3>Täsmennysehdotus pyytäjälle</h3>
            <p>{proposal.clarification_draft}</p>
          </div>
        ) : null}
      </section>

      <section className="card" aria-labelledby="downstream-heading">
        <h2 id="downstream-heading">Ehdotettu eteenpäin lähetettävä rakenne</h2>
        <p className="help">
          Tämä on tarkalleen se snapshot, joka lähetetään mock-integraatioon hyväksynnän jälkeen.
          Se ei luo tiliä.
        </p>
        <p className="mono small">
          Tiiviste: {proposal.payload_hash} · Versio: {proposal.policy_version} · Revisio:{" "}
          {proposal.revision}
        </p>
        <details className="details-block">
          <summary>Näytä JSON-rakenne</summary>
          <pre className="payload-preview" data-testid="downstream-payload">
            {JSON.stringify(proposal.downstream_payload, null, 2)}
          </pre>
        </details>
      </section>
    </div>
  );
}
