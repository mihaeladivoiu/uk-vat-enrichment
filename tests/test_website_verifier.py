import unittest

from src.website_verifier import (
    find_conflicting_company_numbers,
    is_expected_host,
    normalize_text,
)


class TestWebsiteVerifier(unittest.TestCase):
    def test_normalizes_company_name(self):
        result = normalize_text("IC&E LIMITED")

        self.assertEqual(result, "IC E LIMITED")

    def test_accepts_expected_domain(self):
        result = is_expected_host(
            "https://example.co.uk/contact",
            "example.co.uk",
        )

        self.assertTrue(result)

    def test_accepts_www_subdomain(self):
        result = is_expected_host(
            "https://www.example.co.uk/about",
            "example.co.uk",
        )

        self.assertTrue(result)

    def test_rejects_unrelated_domain(self):
        result = is_expected_host(
            "https://another-company.co.uk/",
            "example.co.uk",
        )

        self.assertFalse(result)

    def test_rejects_misleading_hostname(self):
        result = is_expected_host(
            "https://example.co.uk.other-site.com/",
            "example.co.uk",
        )

        self.assertFalse(result)

    def test_detects_conflicting_company_number(self):
        text = "Reg No. 03079542. VAT No. GB278923705."

        result = find_conflicting_company_numbers(
            text,
            "09976982",
        )

        self.assertEqual(result, ["03079542"])

    def test_accepts_matching_company_number(self):
        text = "Company Number: 09976982"

        result = find_conflicting_company_numbers(
            text,
            "09976982",
        )

        self.assertEqual(result, [])

    def test_ignores_unlabelled_numbers(self):
        text = "Order reference: 03079542"

        result = find_conflicting_company_numbers(
            text,
            "09976982",
        )

        self.assertEqual(result, [])

    def test_rejects_insecure_http(self):
        result = is_expected_host(
            "http://example.co.uk/contact",
            "example.co.uk",
        )

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
