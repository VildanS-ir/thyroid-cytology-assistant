"""Count review cases whose conclusion contains a possible description boundary."""

import csv
import random
import re
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "annotated_dataset.csv"
WITH_PHRASE_PATH = DATA_PATH.with_name("to_check_with_phrase.csv")
NO_PHRASE_PATH = DATA_PATH.with_name("to_check_no_phrase.csv")
SAMPLE_SIZE = 50
SAMPLE_SEED = 42
PHRASE_START = re.compile(
    r"\bВ\s+соответствии\s+с\s+критериями\b",
    flags=re.IGNORECASE,
)


def main() -> None:
    review_count = 0
    review_without_description_count = 0
    phrase_start_count = 0
    no_phrase_count = 0
    sampled_with_phrase_rows = []
    sampled_no_phrase_rows = []
    with_phrase_rng = random.Random(SAMPLE_SEED)
    no_phrase_rng = random.Random(SAMPLE_SEED + 1)

    with DATA_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        columns = next(reader, [])

        required_columns = {"needs_review", "description", "conclusion"}
        if required_columns.issubset(columns):
            records = reader
        else:
            missing_columns = required_columns - set(columns)
            raise ValueError(f"Отсутствуют столбцы: {', '.join(sorted(missing_columns))}")

        description_index = columns.index("description")
        conclusion_index = columns.index("conclusion")
        review_index = columns.index("needs_review")

        for record_number, row in enumerate(records, start=1):
            if len(row) != len(columns):
                raise ValueError(f"Некорректное число столбцов в записи {record_number}")

            review_value = row[review_index].strip().casefold()
            if review_value not in {"true", "false"}:
                raise ValueError(
                    f"Некорректное значение needs_review в записи {record_number}"
                )
            if review_value != "true":
                continue

            review_count += 1
            if row[description_index].strip():
                continue

            review_without_description_count += 1
            if PHRASE_START.search(row[conclusion_index]):
                phrase_start_count += 1
                if len(sampled_with_phrase_rows) < SAMPLE_SIZE:
                    sampled_with_phrase_rows.append(row)
                else:
                    sample_index = with_phrase_rng.randrange(phrase_start_count)
                    if sample_index < SAMPLE_SIZE:
                        sampled_with_phrase_rows[sample_index] = row
            else:
                no_phrase_count += 1
                if len(sampled_no_phrase_rows) < SAMPLE_SIZE:
                    sampled_no_phrase_rows.append(row)
                else:
                    sample_index = no_phrase_rng.randrange(no_phrase_count)
                    if sample_index < SAMPLE_SIZE:
                        sampled_no_phrase_rows[sample_index] = row

    for output_path, sampled_rows in (
        (WITH_PHRASE_PATH, sampled_with_phrase_rows),
        (NO_PHRASE_PATH, sampled_no_phrase_rows),
    ):
        with output_path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(columns)
            writer.writerows(sampled_rows)

    print(f"Строк с needs_review == True: {review_count}")
    print(
        "Из них с пустым description: "
        f"{review_without_description_count}"
    )
    print(
        "Из них с началом фразы в conclusion: "
        f"{phrase_start_count}"
    )
    print(f"Из них без начала фразы в conclusion: {no_phrase_count}")
    print(f"Сохранено в {WITH_PHRASE_PATH.name}: {len(sampled_with_phrase_rows)}")
    print(f"Сохранено в {NO_PHRASE_PATH.name}: {len(sampled_no_phrase_rows)}")


if __name__ == "__main__":
    main()
