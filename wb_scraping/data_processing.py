import csv
import json
from pathlib import Path

from config import OUTPUT_PATH
from scraper import ProfileData
from dataclasses import asdict


def read_staff_names(file_path: Path) -> list[str]:
    with open(file_path, mode="r") as f:
        reader = csv.reader(f)
        staff_names = [row[0].strip() for row in reader][1:]  # Skip header
    return [" ".join(reversed(name.split(sep=","))) for name in staff_names]


def save_profile_data(profile_data: ProfileData):
    output_file = OUTPUT_PATH / "persons_profiles.csv"
    file_exists = output_file.exists()

    with open(output_file, "a", newline="", encoding="utf-8") as f:
        csv_writer = csv.DictWriter(f, fieldnames=ProfileData.__annotations__.keys(), quoting=csv.QUOTE_ALL, escapechar='\\')
        if not file_exists:
            csv_writer.writeheader()

        # Convert ProfileData to dictionary, ensure all values are strings, and truncate if necessary
        row_data = {}
        for k, v in asdict(profile_data).items():
            value = str(v).replace('\n', '\\n').replace('\r', '\\r')
            if len(value) > 32000:  # Leave some margin for safety
                value = value[:32000] + "... (truncated)"
            row_data[k] = value

        csv_writer.writerow(row_data)


def save_names_not_found(name: str):
    with open(OUTPUT_PATH / "persons_not_found.csv", "a", newline="") as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow([name])


def save_profile_data_json(profile_data: ProfileData):
    output_file = OUTPUT_PATH / "persons_profiles.json"

    existing_data = []
    if output_file.exists():
        with open(output_file, "r") as f:
            existing_data = json.load(f)

    existing_data.append(profile_data.__dict__)

    with open(output_file, "w") as f:
        json.dump(existing_data, f, indent=2)


def read_existing_profiles(file_path: Path) -> set:
    existing_profiles = set()
    if file_path.exists():
        with open(file_path, mode="r") as f:
            reader = csv.DictReader(f)
            existing_profiles = {row["name"] for row in reader}
    return existing_profiles
