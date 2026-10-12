from pathlib import Path
import re
import unicodedata

import pandas as pd

try:
    from .dataset_versioning import save_dataset_version
except ImportError:
    # Позволяет запускать файл напрямую:
    # python src/common/annotate_dataset.py
    from dataset_versioning import save_dataset_version


# Пути проекта
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DATA_1_PATH = RAW_DIR / "cytology_data_1.xlsx"
DATA_2_PATH = RAW_DIR / "cytology_data_2.xlsx"

ANNOTATED_DATA_PATH = PROCESSED_DIR / "annotated_dataset.csv"


# Учитываем визуально одинаковые латинские и кириллические буквы:
# Bethesda, Вethesda, Bеthesda, Bethеsda, Bethesdа и т.д.
BETHESDA_WORD_PATTERN = r"\b[bв][eе]th[eе]sd[aа]\b"

# Категории Bethesda I-VI.
ROMAN_PATTERN = r"(?<![A-Za-zА-Яа-я])(?:VI|IV|V|III|II|I)(?![A-Za-zА-Яа-я])"

# Признаки того, что в conclusion могла попасть описательная часть.
# Автоматически переносить этот текст в description мы не будем.
DESCRIPTION_MARKERS = (
    "в мазке",
    "пунктирован",
)


def is_blank(value):
    """Проверяет NaN, пустую строку и строку только из пробелов."""

    if pd.isna(value):
        return True

    if isinstance(value, str) and not value.strip():
        return True

    return False


def load_table_1():
    # В первой таблице заголовок занимает Excel-строки 8 и 9.
    # Данные начинаются с Excel-строки 10.
    return pd.read_excel(
        DATA_1_PATH,
        header=[7, 8],
    )


def load_table_2():
    # Во второй таблице заголовок находится в Excel-строке 6.
    # Данные начинаются с Excel-строки 7.
    return pd.read_excel(
        DATA_2_PATH,
        header=5,
    )


def inspect_table(df, name):
    """
    Выводит структуру исходной таблицы.

    Whitespace-only значения считаются пустыми.
    """

    blank_mask = df.apply(
        lambda column: column.map(is_blank)
    )

    filled_by_column = (~blank_mask).sum()
    missing_by_column = blank_mask.sum()
    fully_filled_rows = (~blank_mask).all(axis=1).sum()

    print(f"\n{name}")
    print(f"Total rows: {len(df)}")

    print("\nColumn names:")
    for column in df.columns:
        print(f"- {column}")

    print("\nFilled values:")
    for column, count in filled_by_column.items():
        print(f"- {column}: {count}")

    print("\nMissing values:")
    for column, count in missing_by_column.items():
        print(f"- {column}: {count}")

    print(f"\nFully filled rows: {fully_filled_rows}")


def create_dataset(df_1, df_2):
    """
    Приводит две исходные таблицы к общей структуре
    и сохраняет происхождение каждой записи.
    """

    table_1 = pd.DataFrame({
        "case_id": [
            f"T1_{i:06d}"
            for i in range(1, len(df_1) + 1)
        ],
        "source_table": DATA_1_PATH.name,
        "source_row": range(10, 10 + len(df_1)),
        "description": df_1.iloc[:, 2].to_numpy(),
        "conclusion": df_1.iloc[:, 1].to_numpy(),
    })

    table_2 = pd.DataFrame({
        "case_id": [
            f"T2_{i:06d}"
            for i in range(1, len(df_2) + 1)
        ],
        "source_table": DATA_2_PATH.name,
        "source_row": range(7, 7 + len(df_2)),
        "description": df_2["Описание"].to_numpy(),
        "conclusion": df_2["Заключение"].to_numpy(),
    })

    return pd.concat(
        [table_1, table_2],
        ignore_index=True,
    )


def extract_bethesda_categories(text):
    """
    Извлекает все разные категории Bethesda I-VI
    в порядке появления в тексте.

    Примеры результата:
    "II"
    "I, III"
    """

    if is_blank(text):
        return pd.NA

    text = str(text)
    matches = []

    # 1. Ищем категории после прямого упоминания Bethesda.
    #
    # Примеры:
    # Bethesda-II
    # Bethesda: диагностическая категория VI
    # Вethesda - IV диагностическая категория
    for marker in re.finditer(
        BETHESDA_WORD_PATTERN,
        text,
        flags=re.IGNORECASE,
    ):
        fragment = text[
            marker.end(): marker.end() + 180
        ]

        # Ограничиваемся ближайшим предложением/фрагментом.
        fragment = re.split(
            r"[.;\n]",
            fragment,
            maxsplit=1,
        )[0]

        for match in re.finditer(
            ROMAN_PATTERN,
            fragment,
            flags=re.IGNORECASE,
        ):
            matches.append(
                (
                    marker.end() + match.start(),
                    match.group(0).upper(),
                )
            )

    # 2. Ищем конструкции:
    # категория II
    # диагностическая категория IV
    for marker in re.finditer(
        r"категор\w*",
        text,
        flags=re.IGNORECASE,
    ):
        fragment = text[
            marker.end(): marker.end() + 60
        ]

        for match in re.finditer(
            ROMAN_PATTERN,
            fragment,
            flags=re.IGNORECASE,
        ):
            matches.append(
                (
                    marker.end() + match.start(),
                    match.group(0).upper(),
                )
            )

    # 3. Ищем обратный вариант:
    # IV диагностическая категория
    reverse_pattern = (
        rf"({ROMAN_PATTERN})"
        rf"[\s,:;\-–—]{{0,20}}"
        rf"(?:диагностическ\w*\s+)?"
        rf"категор\w*"
    )

    for match in re.finditer(
        reverse_pattern,
        text,
        flags=re.IGNORECASE,
    ):
        roman_match = re.search(
            ROMAN_PATTERN,
            match.group(0),
            flags=re.IGNORECASE,
        )

        if roman_match:
            matches.append(
                (
                    match.start() + roman_match.start(),
                    roman_match.group(0).upper(),
                )
            )

    if not matches:
        return pd.NA

    matches.sort(key=lambda item: item[0])

    found_categories = []

    # Одинаковую категорию повторно не записываем.
    for _, category in matches:
        if category not in found_categories:
            found_categories.append(category)

    return ", ".join(found_categories)


def fill_bethesda(dataset):
    """Заполняет Bethesda по полю conclusion."""

    dataset["bethesda"] = dataset["conclusion"].apply(
        extract_bethesda_categories
    )

    return dataset


def mark_target_leakage(dataset):
    """
    Проверяет, встречается ли категория Bethesda прямо
    в description.

    Текст не изменяется и категория из description не удаляется.
    """

    dataset["target_leakage"] = (
        dataset["description"]
        .apply(extract_bethesda_categories)
        .notna()
    )

    return dataset


def mark_description_in_conclusion(dataset):
    """
    Ищет вероятные случаи, когда description отсутствует,
    но в conclusion присутствуют признаки описательной части.

    Это только флаг для проверки.
    Автоматического восстановления description здесь нет.
    """

    missing_description = dataset["description"].map(
        is_blank
    )

    conclusion_text = (
        dataset["conclusion"]
        .fillna("")
        .astype(str)
        .str.casefold()
    )

    has_description_marker = conclusion_text.apply(
        lambda text: any(
            marker in text
            for marker in DESCRIPTION_MARKERS
        )
    )

    dataset["description_in_conclusion"] = (
        missing_description
        & has_description_marker
    )

    return dataset


def normalize_text_for_duplicates(text):
    """
    Безопасная нормализация текста для поиска текстовых дубликатов.

    Не удаляем слова, цифры и пунктуацию.
    """

    if is_blank(text):
        return ""

    text = str(text)

    # Унифицируем Unicode-представление символов.
    text = unicodedata.normalize("NFKC", text)

    # Неразрывный пробел заменяем обычным.
    text = text.replace("\xa0", " ")

    # Убираем различия из-за количества пробелов и переносов строк.
    text = " ".join(text.split())

    # Игнорируем регистр.
    return text.casefold()


def raw_duplicate_value(value):
    """
    Представление исходного значения для определения
    буквальных технических дубликатов.
    """

    if is_blank(value):
        return ""

    return str(value)


def mark_duplicates(dataset):
    """
    Помечает группы дубликатов, ничего не удаляя.

    technical:
        description и conclusion буквально совпадают.

    text:
        тексты различаются технически, но совпадают после
        безопасной нормализации.
    """

    normalized_keys = []

    for _, row in dataset.iterrows():
        key = (
            normalize_text_for_duplicates(
                row["description"]
            ),
            normalize_text_for_duplicates(
                row["conclusion"]
            ),
        )

        normalized_keys.append(key)

    groups = {}

    # dict сохраняет порядок добавления,
    # поэтому номера DUP будут воспроизводимыми.
    for index, key in enumerate(normalized_keys):
        groups.setdefault(key, []).append(index)

    dataset["duplicate_group"] = pd.NA
    dataset["duplicate_type"] = pd.NA

    duplicate_number = 1

    for indexes in groups.values():
        if len(indexes) < 2:
            continue

        group_id = f"DUP_{duplicate_number:06d}"
        duplicate_number += 1

        raw_pairs = {
            (
                raw_duplicate_value(
                    dataset.at[index, "description"]
                ),
                raw_duplicate_value(
                    dataset.at[index, "conclusion"]
                ),
            )
            for index in indexes
        }

        # Если внутри нормализованной группы существует
        # только одна исходная пара текстов, это буквальные копии.
        if len(raw_pairs) == 1:
            duplicate_type = "technical"
        else:
            duplicate_type = "text"

        dataset.loc[
            indexes,
            "duplicate_group",
        ] = group_id

        dataset.loc[
            indexes,
            "duplicate_type",
        ] = duplicate_type

    return dataset


def mark_needs_review(dataset):
    """
    Формирует needs_review и сохраняет причины,
    по которым запись требует ручной проверки.
    """

    review_reasons = []

    for _, row in dataset.iterrows():
        reasons = []

        if is_blank(row["description"]):
            reasons.append("missing_description")

        if pd.isna(row["bethesda"]):
            reasons.append("bethesda_not_found")

        elif "," in str(row["bethesda"]):
            reasons.append("multiple_bethesda")

        if row["target_leakage"]:
            reasons.append("target_leakage")

        if row["description_in_conclusion"]:
            reasons.append("description_in_conclusion")

        review_reasons.append("; ".join(reasons))

    dataset["review_reason"] = review_reasons

    dataset["needs_review"] = (
        dataset["review_reason"] != ""
    )

    return dataset


def set_column_order(dataset):
    """Устанавливает фиксированный порядок столбцов."""

    return dataset[
        [
            "case_id",
            "source_table",
            "source_row",
            "description",
            "conclusion",
            "bethesda",
            "needs_review",
            "review_reason",
            "target_leakage",
            "description_in_conclusion",
            "duplicate_group",
            "duplicate_type",
        ]
    ]


def save_dataset(dataset):
    """
    Сохраняет основной annotated_dataset.csv
    и его неизменяемую SHA256-версию.
    """

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataset.to_csv(
        ANNOTATED_DATA_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    file_hash, version_path = save_dataset_version(
        ANNOTATED_DATA_PATH
    )

    return file_hash, version_path


def print_annotation_summary(dataset, file_hash, version_path):
    """Краткая итоговая статистика разметки."""

    bethesda_as_text = dataset["bethesda"].fillna("")

    multiple_bethesda = (
        bethesda_as_text.str.contains(",").sum()
    )

    bethesda_not_found = dataset["bethesda"].isna().sum()

    missing_description = (
        dataset["description"].map(is_blank).sum()
    )

    duplicate_groups = (
        dataset["duplicate_group"]
        .dropna()
        .nunique()
    )

    print("\nAnnotated dataset")
    print(f"Rows: {len(dataset)}")
    print(f"Missing description: {missing_description}")
    print(f"Bethesda not found: {bethesda_not_found}")
    print(f"Multiple Bethesda: {multiple_bethesda}")
    print(
        f"Target leakage: "
        f"{dataset['target_leakage'].sum()}"
    )
    print(
        f"Description in conclusion: "
        f"{dataset['description_in_conclusion'].sum()}"
    )
    print(f"Duplicate groups: {duplicate_groups}")
    print(
        f"Needs review: "
        f"{dataset['needs_review'].sum()}"
    )

    print(f"\nSaved: {ANNOTATED_DATA_PATH}")
    print(f"SHA256: {file_hash}")
    print(f"Version: {version_path}")


def main():
    # Загружаем исходные Excel.
    df_1 = load_table_1()
    df_2 = load_table_2()

    # Анализ исходных таблиц согласно требованиям.
    inspect_table(
        df_1,
        "Table 1: cytology_data_1.xlsx",
    )

    inspect_table(
        df_2,
        "Table 2: cytology_data_2.xlsx",
    )

    # Создаём полный master-датасет.
    dataset = create_dataset(
        df_1,
        df_2,
    )

    # Извлекаем Bethesda только из conclusion.
    dataset = fill_bethesda(dataset)

    # Проверяем утечку target в description.
    dataset = mark_target_leakage(dataset)

    # Помечаем вероятный перенос описания в conclusion.
    dataset = mark_description_in_conclusion(dataset)

    # Ищем дубликаты, но ничего не удаляем.
    dataset = mark_duplicates(dataset)

    # Выставляем needs_review и причины.
    dataset = mark_needs_review(dataset)

    dataset = set_column_order(dataset)

    # Сохраняем текущую и неизменяемую версию датасета.
    file_hash, version_path = save_dataset(dataset)

    print_annotation_summary(
        dataset,
        file_hash,
        version_path,
    )

    return dataset


if __name__ == "__main__":
    main()
