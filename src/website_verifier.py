import argparse
import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from src.vat_extractor import extract_vat_candidates

INPUT_PATH = Path("data/processed/domain_results.csv")
OUTPUT_PATH = Path("data/processed/website_identity_results.csv")

USER_AGENT = "UKVATResearchBot/0.1"
REQUEST_TIMEOUT = 6
MAX_CONTENT_BYTES = 500_000
MAX_REDIRECTS = 3
MAX_PAGES = 4

RELEVANT_PATHS = (
    "contact",
    "about",
    "terms",
    "legal",
    "company-information",
)


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[A-Z0-9]+", value.upper()))


def find_conflicting_company_numbers(
    text: str,
    expected_number: str,
) -> list[str]:
    pattern = re.compile(
        r"\b(?:COMPANY\s+(?:REGISTRATION\s+)?|"
        r"REGISTRATION\s+|REGISTERED\s+|REG\s*)"
        r"(?:NUMBER|NO\.?)\s*[:#.-]?\s*"
        r"([A-Z]{0,2}\d{6,8})\b",
        re.IGNORECASE,
    )

    expected_number = expected_number.upper().strip()

    return sorted(
        {
            match.group(1).upper()
            for match in pattern.finditer(text)
            if match.group(1).upper() != expected_number
        }
    )


def is_expected_host(url: str, domain: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    return parsed.scheme == "https" and hostname in {
        domain.lower(),
        f"www.{domain.lower()}",
    }


def is_allowed(
    session: requests.Session,
    url: str,
    domain: str,
) -> bool:
    robots_url = urljoin(url, "/robots.txt")

    try:
        for _ in range(MAX_REDIRECTS + 1):
            if not is_expected_host(robots_url, domain):
                return False

            response = session.get(
                robots_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )

            if response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    return False

                robots_url = urljoin(robots_url, location)
                continue

            if response.status_code == 404:
                return True

            if response.status_code != 200:
                return False

            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser.can_fetch(USER_AGENT, url)

    except requests.RequestException:
        return False

    return False


def fetch_page(
    session: requests.Session,
    url: str,
    domain: str,
) -> tuple[str, str, BeautifulSoup | None]:
    try:
        for _ in range(MAX_REDIRECTS + 1):
            if not is_expected_host(url, domain):
                return "external_redirect", url, None

            if not is_allowed(session, url, domain):
                return "access_not_confirmed", url, None

            with session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        return "redirect_error", url, None

                    url = urljoin(url, location)
                    continue

                if response.status_code != 200:
                    return f"http_{response.status_code}", url, None

                content_type = response.headers.get("Content-Type", "").lower()

                if "text/html" not in content_type:
                    return "not_html", url, None

                content = bytearray()

                for chunk in response.iter_content(chunk_size=8192):
                    content.extend(chunk)

                    if len(content) > MAX_CONTENT_BYTES:
                        return "content_too_large", url, None

                soup = BeautifulSoup(bytes(content), "html.parser")
                return "accessible", url, soup

        return "too_many_redirects", url, None

    except requests.RequestException:
        return "access_error", url, None


def extract_relevant_links(
    soup: BeautifulSoup,
    page_url: str,
    domain: str,
) -> list[str]:
    links = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        link = urljoin(page_url, anchor["href"])
        parsed = urlparse(link)

        if parsed.scheme != "https":
            continue

        if not is_expected_host(link, domain):
            continue

        path = parsed.path.lower()

        if not any(keyword in path for keyword in RELEVANT_PATHS):
            continue

        clean_url = parsed._replace(
            query="",
            fragment="",
        ).geturl()

        if clean_url not in seen:
            seen.add(clean_url)
            links.append(clean_url)

    return links[: MAX_PAGES - 1]


def inspect_website(
    company: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    domain = company["CandidateDomain"].strip()
    homepage = f"https://{domain}/"

    result = {
        **company,
        "WebsiteURL": homepage,
        "WebsiteStatus": "access_error",
        "PagesChecked": "0",
        "CompanyNumberMatch": "False",
        "CompanyNameMatch": "False",
        "ConflictingCompanyNumbers": "",
        "PostcodeMatch": "False",
        "EvidenceURLs": "",
        "IdentityStatus": "unverified",
    }
    vat_candidates = []

    company_number = normalize_text(company["CompanyNumber"])
    company_name = normalize_text(company["CompanyName"])
    postcode = normalize_text(company["RegAddress.PostCode"])

    matched_number = False
    matched_name = False
    matched_postcode = False
    evidence_urls = []
    pages_checked = 0
    conflicting_numbers = set()

    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})

        status, final_url, homepage_soup = fetch_page(session, homepage, domain)

        result["WebsiteStatus"] = status
        result["WebsiteURL"] = final_url

        if status != "accessible" or homepage_soup is None:
            return result, vat_candidates

        pages = [(final_url, homepage_soup)]
        checked_urls = {final_url}

        for link in extract_relevant_links(homepage_soup, final_url, domain):
            if link in checked_urls:
                continue

            page_status, page_url, soup = fetch_page(session, link, domain)

            if page_status == "accessible" and soup is not None:
                pages.append((page_url, soup))
                checked_urls.add(page_url)

        for page_url, soup in pages:
            for element in soup(["script", "style", "noscript"]):
                element.decompose()

            page_text = soup.get_text(" ", strip=True)

            conflicting_numbers.update(
                find_conflicting_company_numbers(
                    page_text,
                    company["CompanyNumber"],
                )
            )

            for candidate in extract_vat_candidates(page_text, page_url):
                vat_candidates.append(
                    {
                        "CompanyNumber": company["CompanyNumber"],
                        "CompanyName": company["CompanyName"],
                        "CandidateDomain": domain,
                        **candidate,
                    }
                )

            page_text = normalize_text(page_text)
            pages_checked += 1

            number_match = bool(
                company_number
                and re.search(
                    rf"(?<![A-Z0-9]){re.escape(company_number)}(?![A-Z0-9])",
                    page_text,
                )
            )

            name_match = bool(
                company_name
                and re.search(
                    rf"(?<![A-Z0-9]){re.escape(company_name)}(?![A-Z0-9])",
                    page_text,
                )
            )

            postcode_match = bool(postcode and postcode in page_text)

            matched_number |= number_match
            matched_name |= name_match
            matched_postcode |= postcode_match

            if number_match or name_match or postcode_match:
                evidence_urls.append(page_url)

    result["PagesChecked"] = str(pages_checked)
    result["ConflictingCompanyNumbers"] = " | ".join(sorted(conflicting_numbers))
    result["CompanyNumberMatch"] = str(matched_number)
    result["CompanyNameMatch"] = str(matched_name)
    result["PostcodeMatch"] = str(matched_postcode)
    result["EvidenceURLs"] = " | ".join(evidence_urls)

    if conflicting_numbers and not matched_number:
        result["IdentityStatus"] = "identity_conflict"
    elif conflicting_numbers:
        result["IdentityStatus"] = "manual_review"
    elif matched_number and (matched_name or matched_postcode):
        result["IdentityStatus"] = "strong_candidate"
    elif matched_number or (matched_name and matched_postcode):
        result["IdentityStatus"] = "manual_review"

    return result, vat_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect candidate company websites.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--domain", type=str)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")

    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required = {
            "CompanyNumber",
            "CompanyName",
            "RegAddress.PostCode",
            "CandidateDomain",
            "DNSStatus",
        }

        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Input CSV is missing required columns.")

        candidates = [
            row
            for row in reader
            if row["DNSStatus"] == "resolved"
            and (args.domain is None or row["CandidateDomain"] == args.domain)
        ]

    candidates = candidates[: args.limit]

    if not candidates:
        print("No matching resolved domains found.")
        return

    inspections = []

    for company in candidates:
        inspections.append(inspect_website(company))
        time.sleep(1)

    results = [result for result, _ in inspections]

    vat_candidates = [
        {
            **candidate,
            "IdentityStatus": result["IdentityStatus"],
        }
        for result, candidates_found in inspections
        for candidate in candidates_found
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(results[0]),
        )
        writer.writeheader()
        writer.writerows(results)

    vat_output_path = Path("data/processed/vat_candidates.csv")

    with vat_output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "CompanyNumber",
                "CompanyName",
                "CandidateDomain",
                "VATNumber",
                "SourceURL",
                "EvidenceContext",
                "IdentityStatus",
            ],
        )
        writer.writeheader()
        writer.writerows(vat_candidates)

    print(f"Extracted {len(vat_candidates)} VAT occurrences.")
    print(f"VAT results saved to: {vat_output_path}")

    for result in results:
        print(
            f"{result['CandidateDomain']}: "
            f"{result['WebsiteStatus']} / "
            f"{result['IdentityStatus']} "
            f"({result['PagesChecked']} pages)"
        )

    print(f"Inspected {len(results)} candidate websites.")
    print(f"Results saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
