import argparse
import csv
import re
from pathlib import Path

LEGAL_SUFFIXES = {"LTD", "LIMITED", "PLC", "LLP"}
GENERIC_SUFFIXES = {"COMPANY", "CO"}
DOMAIN_SUFFIXES = ("co.uk", "com", "uk")


def normalize_company_name(company_name: str) -> list[str]:
    words = re.findall(r"[A-Z0-9]+", company_name.upper())

    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()

    while len(words) > 1 and words[-1] in GENERIC_SUFFIXES:
        words.pop()

    return words


def generate_domain_candidates(company_name: str) -> list[str]:
    normalized_words = normalize_company_name(company_name)
    original_words = re.findall(r"[A-Z0-9]+", company_name.upper())

    if not normalized_words:
        return []

    name_variants = [
        "".join(normalized_words),
        "".join(original_words),
        "".join(normalized_words[:2]),
        normalized_words[0],
    ]

    candidates = []
    seen = set()

    for name in name_variants:
        if not name or name in seen:
            continue

        seen.add(name)

        for suffix in DOMAIN_SUFFIXES:
            candidates.append(f"{name.lower()}.{suffix}")

    return candidates


def generate_candidates(input_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_candidates = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)

        required_columns = {
            "CompanyNumber",
            "CompanyName",
            "RegAddress.PostCode",
        }
        if not required_columns.issubset(reader.fieldnames or []):
            raise ValueError("Input CSV is missing required columns.")

        with output_path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(
                output_file,
                fieldnames=[
                    "CompanyNumber",
                    "CompanyName",
                    "RegAddress.PostCode",
                    "CandidateDomain",
                ],
            )
            writer.writeheader()

            for company in reader:
                company_number = company["CompanyNumber"].strip()
                company_name = company["CompanyName"].strip()

                for domain in generate_domain_candidates(company_name):
                    writer.writerow(
                        {
                            "CompanyNumber": company_number,
                            "CompanyName": company_name,
                            "RegAddress.PostCode": company[
                                "RegAddress.PostCode"
                            ].strip(),
                            "CandidateDomain": domain,
                        }
                    )
                    total_candidates += 1

    return total_candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate candidate domains for UK companies."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/sample_companies.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/website_candidates.csv"),
    )

    args = parser.parse_args()
    total = generate_candidates(args.input, args.output)

    print(f"Generated {total} candidate domains.")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
