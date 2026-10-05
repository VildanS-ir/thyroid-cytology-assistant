"""Split short descriptions into a separate manual review dataset."""

import csv
import math
from itertools import chain
from pathlib import Path

from data_cleaning import CLEAN_DATA_PATH, main as clean_data, save_dataset


OUTPUT_COLUMNS = ("case_id", "description", "conclusion", "bethesda")
INPUT_COLUMNS = (*OUTPUT_COLUMNS, "needs_review")
OUTPUT_PATH = CLEAN_DATA_PATH.with_name("dataset_first.csv")
REVIEW_PATH = CLEAN_DATA_PATH.with_name("dataset_first_2check.csv")
RECOGNIZED_DESCRIPTION_MARKERS = ("в мазке", "пунктирован")


def read_output_rows(path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        if reader.fieldnames is None or not set(OUTPUT_COLUMNS).issubset(
            reader.fieldnames
        ):
            raise ValueError(
                f"{path.name} должен содержать столбцы: "
                + ", ".join(OUTPUT_COLUMNS)
            )
        return [
            [row[column] or "" for column in OUTPUT_COLUMNS]
            for row in reader
        ]


def read_cleaned_rows() -> list[list[str]]:
    if not CLEAN_DATA_PATH.exists():
        dataset = clean_data()
        save_dataset(dataset)

    with CLEAN_DATA_PATH.open(encoding="utf-8-sig", newline="") as source:
        # data_cleaning.save_dataset uses pandas' default comma delimiter.
        reader = csv.reader(source, delimiter=",")
        columns = next(reader, [])

        # Support files that contain a path line before the CSV header.
        if len(columns) == 1 and columns[0].strip().replace("\\", "/") == (
            "data/processed/cleaned_dataset.csv"
        ):
            columns = next(reader, [])

        normalized_columns = [column.strip() for column in columns]
        if set(INPUT_COLUMNS).issubset(normalized_columns):
            indexes = {
                name: normalized_columns.index(name) for name in INPUT_COLUMNS
            }
            records = reader
        elif len(columns) == len(INPUT_COLUMNS):
            indexes = {name: index for index, name in enumerate(INPUT_COLUMNS)}
            records = chain((columns,), reader)
        else:
            raise ValueError(
                "cleaned_dataset.csv должен содержать столбцы: "
                + ", ".join(INPUT_COLUMNS)
            )

        selected_rows = []
        for record_number, row in enumerate(records, start=1):
            if len(row) != len(columns):
                raise ValueError(
                    f"Некорректное число полей в записи {record_number}"
                )

            review_value = row[indexes["needs_review"]].strip().casefold()
            if review_value not in {"true", "false"}:
                raise ValueError(
                    f"Некорректное значение needs_review в записи {record_number}"
                )
            if review_value == "false":
                selected_rows.append(
                    [row[indexes[column]] for column in OUTPUT_COLUMNS]
                )

    return selected_rows


def write_output_rows(path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target, delimiter=";")
        writer.writerow(OUTPUT_COLUMNS)
        writer.writerows(rows)


def p5(lengths: list[int]) -> int | None:
    if not lengths:
        return None
    sorted_lengths = sorted(lengths)
    nearest_rank = math.ceil(0.05 * len(sorted_lengths))
    return sorted_lengths[nearest_rank - 1]


def main() -> None:
    outputs_exist = OUTPUT_PATH.exists() and REVIEW_PATH.exists()
    script_mtime = Path(__file__).stat().st_mtime_ns
    outputs_need_refresh = outputs_exist and script_mtime > min(
        OUTPUT_PATH.stat().st_mtime_ns,
        REVIEW_PATH.stat().st_mtime_ns,
    )

    if outputs_exist and not outputs_need_refresh:
        clean_rows = read_output_rows(OUTPUT_PATH)
        review_rows = read_output_rows(REVIEW_PATH)
        print("Оба датасета уже существуют; пересоздание пропущено.")
    else:
        # Merge the existing split when a changed script requires a new cutoff.
        if outputs_exist:
            source_rows = read_output_rows(OUTPUT_PATH) + read_output_rows(REVIEW_PATH)
        elif OUTPUT_PATH.exists():
            # Split the old unsplit dataset_first.csv once in place.
            source_rows = read_output_rows(OUTPUT_PATH)
        else:
            source_rows = read_cleaned_rows()

        threshold = p5([len(row[1] or "") for row in source_rows])
        if threshold is None:
            clean_rows = []
            review_rows = []
        else:
            clean_rows = []
            review_rows = []
            for row in source_rows:
                description = row[1] or ""
                has_recognized_marker = any(
                    marker in description.casefold()
                    for marker in RECOGNIZED_DESCRIPTION_MARKERS
                )
                if len(description) < threshold and not has_recognized_marker:
                    review_rows.append(row)
                else:
                    clean_rows.append(row)

        write_output_rows(OUTPUT_PATH, clean_rows)
        write_output_rows(REVIEW_PATH, review_rows)
        print(f"Сохранён чистый датасет: {OUTPUT_PATH.name}")
        print(f"Сохранён датасет для проверки: {REVIEW_PATH.name}")

    all_rows = clean_rows + review_rows
    threshold = p5([len(row[1] or "") for row in all_rows])
    if threshold is None:
        print("В датасете нет строк; P5 определить нельзя.")
        print("Строк короче P5: 0")
        return

    below_p5_count = sum(len(row[1] or "") < threshold for row in all_rows)
    print(f"P5 длины description: {threshold} символов")
    print(f"Строк короче P5: {below_p5_count}")
    print(f"Строк в датасете для проверки: {len(review_rows)}")


if __name__ == "__main__":
    main()
