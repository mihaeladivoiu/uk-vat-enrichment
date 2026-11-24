import unittest

from src.website_discovery import (
    generate_domain_candidates,
    normalize_company_name,
)


class TestWebsiteDiscovery(unittest.TestCase):
    def test_removes_legal_suffix(self):
        words = normalize_company_name("BHAI EATS LTD")

        self.assertEqual(words, ["BHAI", "EATS"])

    def test_generates_expected_domains(self):
        domains = generate_domain_candidates("BHAI EATS LTD")

        self.assertIn("bhaieats.co.uk", domains)
        self.assertIn("bhaieats.com", domains)
        self.assertIn("bhai.co.uk", domains)

    def test_preserves_full_legal_name_variant(self):
        domains = generate_domain_candidates("MODULAR EXPRESS GROUP LTD")

        self.assertIn(
            "modularexpressgroupltd.com",
            domains,
        )

    def test_avoids_duplicate_domains(self):
        domains = generate_domain_candidates("EXAMPLE LTD")

        self.assertEqual(len(domains), len(set(domains)))

    def test_handles_empty_company_name(self):
        domains = generate_domain_candidates("")

        self.assertEqual(domains, [])


if __name__ == "__main__":
    unittest.main()
