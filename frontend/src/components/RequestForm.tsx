"use client";

import { useState, type FormEvent } from "react";

import type { RequestWrite } from "@/lib/api-types";
import { formatFieldName } from "@/lib/labels";

const EMPTY: RequestWrite = {
  original_text: "",
  employee_identifier: "",
  employment_type: "",
  job_role: "",
  unit: "",
  target_system: "",
  requested_access_role: "",
  start_date: "",
  end_date: "",
};

interface RequestFormProps {
  initial?: RequestWrite;
  submitLabel: string;
  busy?: boolean;
  error?: string | null;
  onSubmit: (payload: RequestWrite) => Promise<void>;
}

function normalize(payload: RequestWrite): RequestWrite {
  const nullable = (value: string | null | undefined) => {
    const trimmed = (value ?? "").trim();
    return trimmed === "" ? null : trimmed;
  };
  return {
    original_text: payload.original_text.trim(),
    employee_identifier: nullable(payload.employee_identifier),
    employment_type: nullable(payload.employment_type),
    job_role: nullable(payload.job_role),
    unit: nullable(payload.unit),
    target_system: nullable(payload.target_system),
    requested_access_role: nullable(payload.requested_access_role),
    start_date: nullable(payload.start_date),
    end_date: nullable(payload.end_date),
  };
}

export function RequestForm({
  initial,
  submitLabel,
  busy = false,
  error,
  onSubmit,
}: RequestFormProps) {
  const [form, setForm] = useState<RequestWrite>({ ...EMPTY, ...initial });

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    await onSubmit(normalize(form));
  }

  const fields: Array<keyof RequestWrite> = [
    "employee_identifier",
    "employment_type",
    "job_role",
    "unit",
    "target_system",
    "requested_access_role",
    "start_date",
    "end_date",
  ];

  return (
    <form className="stack" onSubmit={(event) => void handleSubmit(event)} data-testid="request-form">
      <div className="field">
        <label htmlFor="original_text">{formatFieldName("original_text")}</label>
        <textarea
          id="original_text"
          name="original_text"
          required
          rows={5}
          value={form.original_text}
          onChange={(event) => setForm({ ...form, original_text: event.target.value })}
          aria-describedby="original_text_help"
        />
        <p id="original_text_help" className="help">
          Vapaateksti synteettisestä pyynnöstä. Malli ei myönnä oikeuksia.
        </p>
      </div>
      <fieldset className="fieldset-plain stack">
        <legend className="eyebrow">Täydentävät kentät</legend>
        <div className="grid-2">
          {fields.map((field) => (
            <div className="field" key={field}>
              <label htmlFor={field}>{formatFieldName(field)}</label>
              <input
                id={field}
                name={field}
                type={field.includes("date") ? "date" : "text"}
                value={(form[field] as string | null | undefined) ?? ""}
                onChange={(event) => setForm({ ...form, [field]: event.target.value })}
              />
            </div>
          ))}
        </div>
      </fieldset>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" className="btn btn--primary" disabled={busy} aria-busy={busy}>
        {busy ? "Lähetetään…" : submitLabel}
      </button>
    </form>
  );
}
