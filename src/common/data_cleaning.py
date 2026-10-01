from pathlib import Path

import pandas as pd

import re

# Определяем корень проекта и пути к исходным Excel-файлам.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DATA_1_PATH = RAW_DIR / "cytology_data_1.xlsx"
DATA_2_PATH = RAW_DIR / "cytology_data_2.xlsx"

CLEAN_DATA_PATH = PROCESSED_DIR / "cleaned_dataset.csv"


def load_table_1():
    # В первой таблице заголовок занимает две строки:
    # pandas-строки 7 и 8.
    df = pd.read_excel(
        DATA_1_PATH,
        header=[7, 8],
    )

    return df


def load_table_2():
    # Во второй таблице заголовок находится в pandas-строке 5.
    df = pd.read_excel(
        DATA_2_PATH,
        header=5,
    )

    return df


def inspect_table(df, name):
    # По заданию выводим исходные названия столбцов
    # и количество полностью заполненных строк.
    print(f"\n{name}")

    print("Column names:")
    for column in df.columns:
        print(f"- {column}")

    filled_rows = df.notna().all(axis=1).sum()

    print(f"Fully filled rows: {filled_rows}")


def create_dataset(df_1, df_2):
    # Приводим обе исходные таблицы к общей структуре.
    table_1 = pd.DataFrame({
        "case_id": [
            f"T1_{i:06d}"
            for i in range(1, len(df_1) + 1)
        ],
        "description": df_1.iloc[:, 2].to_numpy(),
        "conclusion": df_1.iloc[:, 1].to_numpy(),
    })

    table_2 = pd.DataFrame({
        "case_id": [
            f"T2_{i:06d}"
            for i in range(1, len(df_2) + 1)
        ],
        "description": df_2["Описание"].to_numpy(),
        "conclusion": df_2["Заключение"].to_numpy(),
    })

    dataset = pd.concat(
        [table_1, table_2],
        ignore_index=True,
    )

    # Столбцы будут заполнены на следующих этапах обработки.
    dataset["bethesda"] = pd.NA
    dataset["needs_review"] = False

    return dataset[
        [
            "case_id",
            "description",
            "conclusion",
            "bethesda",
            "needs_review",
        ]
    ]


def remove_full_duplicates(dataset):
    # Полными дубликатами считаем строки,
    # где одновременно совпадают описание и заключение.
    dataset = dataset.drop_duplicates(
        subset=["description", "conclusion"],
        keep="first",
    )

    return dataset.reset_index(drop=True)


def extract_bethesda_categories(text):
    # Если заключение отсутствует,
    # определить категорию невозможно.
    if pd.isna(text):
        return pd.NA

    text = str(text)

    roman_pattern = r"(VI|IV|V|III|II|I)"

    # Учитываем варианты:
    # Bethesda II
    # Bethesda-II
    # Bethesda: диагностическая категория VI
    # Bethesdа с кириллической буквой "а".
    bethesda_pattern = (
        rf"\bbethesd[aа]\b"
        rf"[\s\S]{{0,250}}?"
        rf"\b{roman_pattern}\b"
    )

    # Учитываем варианты:
    # категория II
    # диагностическая категория IV
    # категории VI.
    category_pattern = (
        rf"категор\w*"
        rf"[\s\S]{{0,80}}?"
        rf"\b{roman_pattern}\b"
    )

    matches = []

    for match in re.finditer(
        bethesda_pattern,
        text,
        flags=re.IGNORECASE,
    ):
        matches.append(
            (match.start(), match.group(1).upper())
        )

    for match in re.finditer(
        category_pattern,
        text,
        flags=re.IGNORECASE,
    ):
        matches.append(
            (match.start(), match.group(1).upper())
        )

    if not matches:
        return pd.NA

    # Сортируем найденные категории по их положению в тексте.
    matches.sort(key=lambda item: item[0])

    found_categories = []

    # Одинаковую категорию несколько раз не дублируем.
    for _, category in matches:
        if category not in found_categories:
            found_categories.append(category)

    # Одна категория: "II"
    # Несколько категорий: "I, III"
    return ", ".join(found_categories)


def fill_bethesda(dataset):
    dataset["bethesda"] = dataset["conclusion"].apply(
        extract_bethesda_categories
    )

    return dataset


def mark_needs_review(dataset):
    # Описание отсутствует, если значение NaN,
    # пустое или состоит только из пробелов.
    missing_description = (
        dataset["description"].isna()
        | dataset["description"]
        .fillna("")
        .str.strip()
        .eq("")
    )

    # Несколько категорий записываются в формате "II, IV".
    multiple_categories = (
        dataset["bethesda"]
        .fillna("")
        .str.contains(",")
    )

    # Категория не распознана.
    category_not_found = dataset["bethesda"].isna()

    dataset["needs_review"] = (
        missing_description
        | multiple_categories
        | category_not_found
    )

    return dataset

def save_dataset(dataset):
    dataset.to_csv(
        CLEAN_DATA_PATH,
        index=False,
        encoding="utf-8-sig",
    )


def main():
    # Загружаем оба Excel-файла.
    df_1 = load_table_1()
    df_2 = load_table_2()

    # Выводим названия столбцов и количество заполненных строк.
    inspect_table(
        df_1,
        "Table_1: Описания_и_заключения_цитологии_ЭНЦ_ослепленные_",
    )

    inspect_table(
        df_2,
        "Table_2: Доп. описания",
    )

    # Создаём общую таблицу требуемой структуры.
    dataset = create_dataset(df_1, df_2)

    # Удаляем полные дубликаты.
    dataset = remove_full_duplicates(dataset)

    # Извлекаем категорию Bethesda из заключения.
    dataset = fill_bethesda(dataset)

    # Отмечаем строки, требующие ручной проверки.
    dataset = mark_needs_review(dataset)

    # Сохраняем в data/processed/cleaned_dataset.csv
#    save_dataset(dataset)

    return dataset


if __name__ == "__main__":
    main()