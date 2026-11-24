import re

GB_VAT_PATTERN = re.compile(
    r"(?<![A-Z0-9])GB[\s.-]*((?:\d[\s.-]*){9})(?![A-Z0-9])",
    re.IGNORECASE,
)

LABELLED_VAT_PATTERN = re.compile(
    r"\b(?:VAT(?:\s+REGISTRATION)?(?:\s+(?:NUMBER|NO\.?))?|VRN)"
    r"\s*[:#-]?\s*(?:GB[\s.-]*)?((?:\d[\s.-]*){9})"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)

CONTEXT_LENGTH = 60


def normalize_vat_number(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)

    if len(digits) != 9:
        return None

    return f"GB{digits}"


def extract_vat_candidates(
    text: str,
    source_url: str,
) -> list[dict[str, str]]:
    candidates = []
    seen = set()

    for pattern in (GB_VAT_PATTERN, LABELLED_VAT_PATTERN):
        for match in pattern.finditer(text):
            vat_number = normalize_vat_number(match.group(1))

            if vat_number is None or vat_number in seen:
                continue

            seen.add(vat_number)

            context_start = max(0, match.start() - CONTEXT_LENGTH)
            context_end = min(len(text), match.end() + CONTEXT_LENGTH)

            context = " ".join(text[context_start:context_end].split())

            candidates.append(
                {
                    "VATNumber": vat_number,
                    "SourceURL": source_url,
                    "EvidenceContext": context,
                }
            )

    return candidates
