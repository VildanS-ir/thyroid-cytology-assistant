"""Collect IDs marked for review and IDs with very short descriptions."""

import csv
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "annotated_dataset.csv"
OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "review_case_ids.csv"
)
INPUT_COLUMNS = ("case_id", "description", "needs_review")

RECOGNIZED_DESCRIPTION_MARKERS = ("в мазке", "пунктирован")


def main() -> None:
    with INPUT_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=",")
        if reader.fieldnames is None:
            raise ValueError("annotated_dataset.csv должен содержать заголовок.")

        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        if not set(INPUT_COLUMNS).issubset(reader.fieldnames):
            raise ValueError(
                "annotated_dataset.csv должен содержать столбцы: "
                + ", ".join(INPUT_COLUMNS)
            )

        flagged_case_ids = []
        unflagged_rows = []
        for record_number, row in enumerate(reader, start=1):
            if None in row or any(row.get(column) is None for column in INPUT_COLUMNS):
                raise ValueError(
                    f"Некорректное число полей в записи {record_number}."
                )

            review_value = row["needs_review"].strip().casefold()
            if review_value not in {"true", "false"}:
                raise ValueError(
                    f"Некорректное значение needs_review в записи {record_number}."
                )

            case_id = row["case_id"]
            description = row["description"]
            if review_value == "true":
                flagged_case_ids.append(case_id)
            else:
                unflagged_rows.append((case_id, description))

    # P5 здесь рассчитывается отдельно для всех needs_review=False.
    # В prepare_dataset.py P5 рассчитывается после отбора дубликатов,
    # поэтому наборы коротких описаний могут различаться.
    if unflagged_rows:
        sorted_lengths = sorted(len(description) for _, description in unflagged_rows)
        p5_index = math.ceil(0.05 * len(sorted_lengths)) - 1
        description_threshold = sorted_lengths[p5_index]
        short_description_case_ids = [
            case_id
            for case_id, description in unflagged_rows
            if len(description) < description_threshold
            and not any(
                marker in description.casefold()
                for marker in RECOGNIZED_DESCRIPTION_MARKERS
            )
        ]
    else:
        short_description_case_ids = []

    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target, delimiter=";")
        writer.writerow(("case_id",))
        writer.writerows((case_id,) for case_id in flagged_case_ids)
        writer.writerows((case_id,) for case_id in short_description_case_ids)


if __name__ == "__main__":
    main()
