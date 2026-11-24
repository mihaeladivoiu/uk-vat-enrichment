import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import dns.exception
import dns.resolver


def check_domain(domain: str) -> str:
    try:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ["1.1.1.1", "8.8.8.8"]
        resolver.timeout = 2
        resolver.lifetime = 3

        for record_type in ("A", "AAAA"):
            try:
                records = resolver.resolve(domain, record_type)
                if records:
                    return "resolved"
            except dns.resolver.NoAnswer:
                continue

        return "no_address_record"

    except dns.resolver.NXDOMAIN:
        return "not_found"
    except dns.exception.DNSException:
        return "dns_error"


def check_domains(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        companies = list(reader)

    if not companies:
        raise ValueError("No domain candidates found.")

    if "CandidateDomain" not in companies[0]:
        raise ValueError("Missing CandidateDomain column.")

    unique_domains = list(dict.fromkeys(row["CandidateDomain"] for row in companies))

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = dict(zip(unique_domains, executor.map(check_domain, unique_domains)))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as file:
        fieldnames = list(companies[0]) + ["DNSStatus"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for company in companies:
            writer.writerow(
                {
                    **company,
                    "DNSStatus": statuses[company["CandidateDomain"]],
                }
            )

    resolved_count = sum(status == "resolved" for status in statuses.values())

    print(f"Checked {len(unique_domains)} unique domains.")
    print(f"Resolved domains: {resolved_count}")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    check_domains(
        Path("data/processed/website_candidates.csv"),
        Path("data/processed/domain_results.csv"),
    )
