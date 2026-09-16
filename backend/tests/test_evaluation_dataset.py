from app.evaluation.loader import load_cases


def test_no_real_organization_names_in_evaluation_corpus() -> None:
    forbidden = ("päijät", "hyvinvointialue", "phhy", "terveys")
    cases = load_cases()
    for case in cases:
        lowered = case.input.original_text.lower()
        for token in forbidden:
            assert token not in lowered, f"{case.id} contains forbidden token {token!r}"
