import csv
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "sample_companies.csv"

SAMPLE_SIZE = 30
RANDOM_SEED = 42

OUTPUT_COLUMNS = [
    "CompanyNumber",
    "CompanyName",
    "CompanyStatus",
    "RegAddress.AddressLine1",
    "RegAddress.AddressLine2",
    "RegAddress.PostTown",
    "RegAddress.County",
    "RegAddress.PostCode",
    "SICCode.SicText_1",
]


def sample_companies():
    csv_files = sorted(RAW_DATA_DIR.glob("BasicCompanyData-*-part*_7.csv"))

    if len(csv_files) != 7:
        raise FileNotFoundError(
            f"Expected 7 Companies House CSV files, found {len(csv_files)}."
        )
    random_generator = random.Random(RANDOM_SEED)
    sample = []
    eligible_count = 0

    for file_path in csv_files:
        print(f"Processing: {file_path.name}")

        with file_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, skipinitialspace=True)
            # print("CSV columns:", [repr(column) for column in reader.fieldnames])

            missing_columns = set(OUTPUT_COLUMNS) - set(reader.fieldnames or [])

            if missing_columns:
                raise ValueError(
                    f"Missing columns in {file_path.name}: {sorted(missing_columns)}"
                )

            for company in reader:
                if company["CompanyStatus"].strip().lower() != "active":
                    continue

                if not company["CompanyNumber"].strip():
                    continue

                if not company["CompanyName"].strip():
                    continue

                eligible_count += 1

                selected_company = {
                    column: company[column].strip() for column in OUTPUT_COLUMNS
                }

                if len(sample) < SAMPLE_SIZE:
                    sample.append(selected_company)
                else:
                    random_index = random_generator.randrange(eligible_count)

                    if random_index < SAMPLE_SIZE:
                        sample[random_index] = selected_company

    if eligible_count < SAMPLE_SIZE:
        raise ValueError("Not enough eligible companies to create the sample.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(sample)

    print(f"\nEligible companies: {eligible_count}")
    print(f"Selected companies: {len(sample)}")
    print(f"Sample saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    sample_companies()
