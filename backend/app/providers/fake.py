from __future__ import annotations

import json
import math
import re
from hashlib import sha256
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.models import EMBEDDING_DIMENSION
from app.providers import (
    FAKE_MODEL,
    FAKE_PROVIDER_LABEL,
    PROMPT_VERSION,
    ProviderOutputError,
    ProviderTimeoutError,
)

FailMode = Literal["timeout", "invalid_json", "invent_citations"] | None
T = TypeVar("T", bound=BaseModel)

_TOKEN = re.compile(r"[a-z0-9äöå\-]+", re.IGNORECASE)
_EMP = re.compile(r"\bEMP-\d+\b", re.IGNORECASE)
_ISO_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_JOB_ROLES = ("sairaanhoitaja", "laakari", "taloussihteeri")
_EMPLOYMENT = ("vakituinen", "maaraaikainen")
_SYSTEMS = ("demo-hr-testi", "demo-talous-testi")
_ACCESS = ("lukuoikeus", "kirjaaja", "tuotanto-superadmin")
_INJECTION = (
    "ignore previous",
    "ohita aiemmat",
    "you are now",
    "hyväksy tämä",
    "set role to reviewer",
    "override policy",
)


def _untrusted_user_text(prompt: str) -> str:
    """Extract only the user-text block so form-field dumps are not treated as evidence."""
    start = "BEGIN_UNTRUSTED_USER_TEXT"
    end = "END_UNTRUSTED_USER_TEXT"
    if start in prompt and end in prompt:
        return prompt.split(start, 1)[1].split(end, 1)[0]
    return prompt


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text)]


def hashed_embedding(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    vector = [0.0] * dimension
    for token in tokenize(text):
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimension
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class FakeEmbeddingProvider:
    name = "fake"
    model = "fake-hash-embed-v1"
    version = "v1"
    dimension = EMBEDDING_DIMENSION

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [hashed_embedding(text, self.dimension) for text in texts]


class FakeLLMProvider:
    name = "fake"
    model = FAKE_MODEL
    version = PROMPT_VERSION
    label = FAKE_PROVIDER_LABEL

    def __init__(
        self,
        *,
        fail_mode: FailMode = None,
        timeout_after: int = 1,
        max_retries: int = 2,
    ) -> None:
        self.fail_mode = fail_mode
        self.timeout_after = timeout_after
        self.max_retries = max_retries
        self.calls = 0

    def complete_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        purpose: str,
    ) -> T:
        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for _ in range(attempts):
            self.calls += 1
            if self.fail_mode == "timeout" and self.calls >= self.timeout_after:
                raise ProviderTimeoutError("fake provider timeout")
            if self.fail_mode == "invalid_json":
                last_error = ProviderOutputError("fake invalid JSON")
                continue
            payload = self._payload(prompt, purpose)
            try:
                return schema.model_validate(payload)
            except ValidationError as exc:
                last_error = ProviderOutputError(str(exc))
        raise last_error or ProviderOutputError("fake structured output failed")

    def _payload(self, prompt: str, purpose: str) -> dict[str, Any]:
        if purpose == "extract":
            return self._extract(prompt)
        return self._explain(prompt)

    def _extract(self, prompt: str) -> dict[str, Any]:
        source = _untrusted_user_text(prompt)
        lowered = source.lower()
        fields: dict[str, str | None] = {
            "employee_identifier": _first(_EMP.findall(source)),
            "employment_type": _first_in(lowered, _EMPLOYMENT),
            "job_role": _first_in(lowered, _JOB_ROLES),
            "unit": _unit(source),
            "target_system": _first_in(lowered, _SYSTEMS),
            "requested_access_role": _first_in(lowered, _ACCESS),
            "start_date": None,
            "end_date": None,
        }
        ambiguous: dict[str, bool] = {}
        dates = _ISO_DATE.findall(source)
        if dates:
            fields["start_date"] = dates[0]
        if len(dates) > 1:
            fields["end_date"] = dates[1]
        if "yksikkösiirto" in lowered or "yksikkosiirto" in lowered:
            ambiguous["unit"] = True
            if not fields["unit"]:
                fields["unit"] = None
        if fields["employee_identifier"] is None and "työntekijä" in lowered:
            ambiguous["employee_identifier"] = True
        if any(marker in lowered for marker in _INJECTION):
            ambiguous["injection_ignored"] = True
        result = {
            "fields": {
                key: {
                    "value": value,
                    "excerpt": value if isinstance(value, str) else None,
                    "ambiguous": bool(ambiguous.get(key)),
                }
                for key, value in fields.items()
            },
            "provider_label": FAKE_PROVIDER_LABEL,
            "model": FAKE_MODEL,
            "prompt_version": PROMPT_VERSION,
        }
        return result

    def _explain(self, prompt: str) -> dict[str, Any]:
        retrieved = re.findall(r"source_id=([A-Za-z0-9#@.\-]+)", prompt)
        missing_evidence = "NO_EVIDENCE" in prompt or not retrieved
        cited = list(dict.fromkeys(retrieved))
        if self.fail_mode == "invent_citations":
            cited = [*cited, "SYN-OHJE-KEKSITTY-01-v1#0"]
        if missing_evidence:
            explanation = (
                f"{FAKE_PROVIDER_LABEL}. Näyttöä ei löytynyt synteettisestä ohjekokoelmasta. "
                "Ei tuettua vastausta. Tämä ei ole mitattu mallisuorituskyky."
            )
            clarification = (
                "Täydennä hakemus tai varmista, että voimassa olevia "
                "SYNTHETIC-ohjeita on saatavilla."
            )
            cited = []
        else:
            explanation = (
                f"{FAKE_PROVIDER_LABEL}. Deterministiset säännöt päättävät kelpoisuuden. "
                "Noudetut ohjeet ovat näyttöä, eivät valtuutusta. "
                f"Viitteet: {', '.join(cited)}. "
                "Ristiriitaiset ohjeet on jätettävä ihmisen näkyviin."
            )
            clarification = (
                "Tarkista puuttuvat kentät ja ristiriitaiset SYNTHETIC-ohjeet ennen päätöstä."
            )
        return {
            "explanation_text": explanation,
            "clarification_draft": clarification,
            "cited_source_ids": cited,
            "evidence_missing": missing_evidence,
            "provider_label": FAKE_PROVIDER_LABEL,
            "model": FAKE_MODEL,
            "prompt_version": PROMPT_VERSION,
        }


def _first(values: list[str]) -> str | None:
    return values[0] if values else None


def _first_in(text: str, options: tuple[str, ...]) -> str | None:
    for option in options:
        if option in text:
            return option
    return None


def _unit(text: str) -> str | None:
    match = re.search(r"yksikkö\s+([a-z0-9\-]+)", text, flags=re.IGNORECASE)
    return match.group(1).lower() if match else None


def dump_schema_example(schema: type[BaseModel]) -> str:
    return json.dumps(schema.model_json_schema(), ensure_ascii=False)
