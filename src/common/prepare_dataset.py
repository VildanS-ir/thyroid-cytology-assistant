"""Подготовка общего рабочего датасета из размеченного master-датасета."""

from pathlib import Path
import math

import pandas as pd

try:
    from .annotate_dataset import ANNOTATED_DATA_PATH, main as annotate_data
    from .dataset_versioning import calculate_sha256, save_dataset_version
except ImportError:
    # Позволяет запускать файл напрямую:
    # python src/common/prepare_dataset.py
    from annotate_dataset import ANNOTATED_DATA_PATH, main as annotate_data
    from dataset_versioning import calculate_sha256, save_dataset_version


PREPARED_DATA_PATH = ANNOTATED_DATA_PATH.with_name("prepared_dataset.csv")
REVIEW_DATA_PATH = ANNOTATED_DATA_PATH.with_name("short_descriptions_review.csv")

OUTPUT_COLUMNS = [
    "case_id",
    "source_table",
    "source_row",
    "description",
    "conclusion",
    "bethesda",
    "duplicate_group",
    "duplicate_type",
]

REQUIRED_COLUMNS = {
    *OUTPUT_COLUMNS,
    "needs_review",
    "target_leakage",
}

RECOGNIZED_DESCRIPTION_MARKERS = (
    "в мазке",
    "пунктирован",
)

OUTPUT_SEPARATOR = ";"


def is_blank(value) -> bool:
    """Проверяет NaN, пустую строку и строку только из пробелов."""

    if pd.isna(value):
        return True

    return isinstance(value, str) and not value.strip()


def parse_bool_column(series: pd.Series, column_name: str) -> pd.Series:
    """Надёжно преобразует CSV-значения True/False в bool."""

    values = series.astype(str).str.strip().str.casefold()
    invalid_values = sorted(set(values) - {"true", "false"})

    if invalid_values:
        raise ValueError(
            f"Столбец {column_name} содержит некорректные значения: "
            + ", ".join(invalid_values)
        )

    return values.eq("true")


def load_annotated_dataset() -> pd.DataFrame:
    """Загружает master-датасет с разметкой, при отсутствии создаёт его."""

    if not ANNOTATED_DATA_PATH.exists():
        print("annotated_dataset.csv не найден. Запускается annotate_dataset.py.")
        annotate_data()

    dataset = pd.read_csv(
        ANNOTATED_DATA_PATH,
        encoding="utf-8-sig",
    )

    missing_columns = REQUIRED_COLUMNS - set(dataset.columns)

    if missing_columns:
        raise ValueError(
            "annotated_dataset.csv не содержит обязательные столбцы: "
            + ", ".join(sorted(missing_columns))
        )

    dataset["needs_review"] = parse_bool_column(
        dataset["needs_review"],
        "needs_review",
    )

    dataset["target_leakage"] = parse_bool_column(
        dataset["target_leakage"],
        "target_leakage",
    )

    return dataset


def filter_eligible_rows(dataset: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Отбирает записи по действующим критериям качества и наличию Bethesda."""

    missing_description = dataset["description"].map(is_blank)

    valid_bethesda = (
        dataset["bethesda"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.fullmatch(r"I|II|III|IV|V|VI")
    )

    needs_review = dataset["needs_review"]
    target_leakage = dataset["target_leakage"]

    eligible_mask = (
        ~missing_description
        & valid_bethesda
        & ~needs_review
        & ~target_leakage
    )

    statistics = {
        "missing_description": int(missing_description.sum()),
        "invalid_or_multiple_bethesda": int((~valid_bethesda).sum()),
        "target_leakage": int(target_leakage.sum()),
        "needs_review": int(needs_review.sum()),
        "excluded_total": int((~eligible_mask).sum()),
    }

    return dataset.loc[eligible_mask].copy(), statistics


def select_duplicate_representatives(
    dataset: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Оставляет одного представителя каждой duplicate-группы."""

    dataset = dataset.copy()
    dataset["_row_order"] = range(len(dataset))

    duplicate_group = dataset["duplicate_group"]
    has_group = duplicate_group.notna() & duplicate_group.astype(str).str.strip().ne("")

    grouped_rows = dataset.loc[has_group]
    unique_rows = dataset.loc[~has_group]

    grouped_representatives = grouped_rows.drop_duplicates(
        subset=["duplicate_group"],
        keep="first",
    )

    result = pd.concat(
        [unique_rows, grouped_representatives],
        ignore_index=False,
    )

    result = (
        result.sort_values("_row_order")
        .drop(columns="_row_order")
        .reset_index(drop=True)
    )

    removed_count = len(dataset) - len(result)

    return result, removed_count


def p5(lengths: list[int]) -> int | None:
    """Возвращает 5-й процентиль методом nearest rank, как в старом скрипте."""

    if not lengths:
        return None

    sorted_lengths = sorted(lengths)
    nearest_rank = math.ceil(0.05 * len(sorted_lengths))

    return sorted_lengths[nearest_rank - 1]


def split_short_descriptions(
    dataset: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, int | None]:
    """Отправляет слишком короткие description без известных маркеров на проверку."""

    lengths = dataset["description"].astype(str).map(len).tolist()
    threshold = p5(lengths)

    if threshold is None:
        empty = dataset.iloc[0:0].copy()
        return dataset.copy(), empty, None

    description_text = dataset["description"].astype(str)
    description_lengths = description_text.map(len)

    has_recognized_marker = description_text.str.casefold().apply(
        lambda text: any(
            marker in text
            for marker in RECOGNIZED_DESCRIPTION_MARKERS
        )
    )

    short_for_review = (
        (description_lengths < threshold)
        & ~has_recognized_marker
    )

    prepared_rows = dataset.loc[~short_for_review].copy()
    review_rows = dataset.loc[short_for_review].copy()

    return (
        prepared_rows.reset_index(drop=True),
        review_rows.reset_index(drop=True),
        threshold,
    )


def select_output_columns(dataset: pd.DataFrame) -> pd.DataFrame:
    """Оставляет поля, необходимые классификации и поиску похожих случаев."""

    return dataset[OUTPUT_COLUMNS].copy()


def save_output_dataset(path: Path, dataset: pd.DataFrame) -> tuple[str, Path]:
    """Сохраняет CSV и создаёт неизменяемую SHA256-версию."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataset.to_csv(
        path,
        sep=OUTPUT_SEPARATOR,
        index=False,
        encoding="utf-8-sig",
    )

    return save_dataset_version(path)


def print_summary(
    source_rows: int,
    source_hash: str,
    filter_statistics: dict[str, int],
    eligible_rows: int,
    duplicate_rows_removed: int,
    threshold: int | None,
    prepared_rows: int,
    review_rows: int,
    prepared_hash: str,
    prepared_version_path: Path,
    review_hash: str,
    review_version_path: Path,
) -> None:
    """Выводит краткую статистику построения производных датасетов."""

    print("\nPrepared dataset build summary")
    print(f"Rows in annotated_dataset: {source_rows}")
    print(f"annotated_dataset SHA256: {source_hash}")

    print("\nExcluded before P5 check:")
    print(
        f"- missing description: "
        f"{filter_statistics['missing_description']}"
    )
    print(
        f"- invalid or multiple Bethesda: "
        f"{filter_statistics['invalid_or_multiple_bethesda']}"
    )
    print(
        f"- target leakage: "
        f"{filter_statistics['target_leakage']}"
    )
    print(
        f"- needs review: "
        f"{filter_statistics['needs_review']}"
    )
    print(
        f"- unique rows excluded in total: "
        f"{filter_statistics['excluded_total']}"
    )

    print(f"\nEligible rows before duplicate selection: {eligible_rows}")
    print(f"Duplicate rows not selected: {duplicate_rows_removed}")

    if threshold is None:
        print("P5 description length: not available")
    else:
        print(f"P5 description length: {threshold} characters")

    print(f"Rows in prepared_dataset.csv: {prepared_rows}")
    print(f"Rows in short_descriptions_review.csv: {review_rows}")

    print("\nSaved versions:")
    print(f"prepared_dataset SHA256: {prepared_hash}")
    print(f"prepared_dataset version: {prepared_version_path}")
    print(f"short_descriptions_review SHA256: {review_hash}")
    print(f"short_descriptions_review version: {review_version_path}")


def main() -> pd.DataFrame:
    # Строим датасеты заново из актуального файла разметки.
    dataset = load_annotated_dataset()
    source_hash = calculate_sha256(ANNOTATED_DATA_PATH)

    source_rows = len(dataset)

    eligible_dataset, filter_statistics = filter_eligible_rows(dataset)
    eligible_rows = len(eligible_dataset)

    deduplicated_dataset, duplicate_rows_removed = select_duplicate_representatives(
        eligible_dataset
    )

    prepared_dataset, review_dataset, threshold = split_short_descriptions(
        deduplicated_dataset
    )

    prepared_dataset = select_output_columns(prepared_dataset)
    review_dataset = select_output_columns(review_dataset)

    prepared_hash, prepared_version_path = save_output_dataset(
        PREPARED_DATA_PATH,
        prepared_dataset,
    )

    review_hash, review_version_path = save_output_dataset(
        REVIEW_DATA_PATH,
        review_dataset,
    )

    print_summary(
        source_rows=source_rows,
        source_hash=source_hash,
        filter_statistics=filter_statistics,
        eligible_rows=eligible_rows,
        duplicate_rows_removed=duplicate_rows_removed,
        threshold=threshold,
        prepared_rows=len(prepared_dataset),
        review_rows=len(review_dataset),
        prepared_hash=prepared_hash,
        prepared_version_path=prepared_version_path,
        review_hash=review_hash,
        review_version_path=review_version_path,
    )

    return prepared_dataset


if __name__ == "__main__":
    main()
