import unittest

from src.vat_extractor import (
    extract_vat_candidates,
    normalize_vat_number,
)


class TestVatExtractor(unittest.TestCase):
    def test_normalizes_vat_number(self):
        result = normalize_vat_number("GB 290 7521 52")

        self.assertEqual(result, "GB290752152")

    def test_rejects_invalid_length(self):
        result = normalize_vat_number("12345")

        self.assertIsNone(result)

    def test_extracts_prefixed_vat(self):
        text = "Our VAT number is GB290752152."

        result = extract_vat_candidates(
            text,
            "https://example.com/contact",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["VATNumber"], "GB290752152")

    def test_extracts_labelled_vat(self):
        text = "VAT Registration Number: 243 555 507"

        result = extract_vat_candidates(
            text,
            "https://example.com/terms",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["VATNumber"], "GB243555507")

    def test_removes_duplicates(self):
        text = "VAT: GB290752152. Registration VAT: GB290752152."

        result = extract_vat_candidates(
            text,
            "https://example.com",
        )

        self.assertEqual(len(result), 1)

    def test_ignores_unlabelled_numbers(self):
        text = "Reference number: 123456789"

        result = extract_vat_candidates(
            text,
            "https://example.com",
        )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
