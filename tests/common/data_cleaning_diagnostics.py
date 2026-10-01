from pathlib import Path

import pandas as pd

import re

# __file__ - путь к текущему файлу data_cleaning.py
# resolve() - превращает его в полный абсолютный путь
# parents[2] - поднимаемся на два уровня вверх:
#
# data_cleaning.py -> common -> src -> самая верхняя директория
#
# В результате PROJECT_ROOT указывает на корень проекта
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Формируем путь к папке с исходными данными
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Формируем полные пути к двум Excel-файлам
DATA_1_PATH = RAW_DIR / "cytology_data_1.xlsx"
DATA_2_PATH = RAW_DIR / "cytology_data_2.xlsx"

'''
# Поиск строк, откуда начинаются данные
def inspect_raw_table(path, name):
    df = pd.read_excel(path, header=None)

    print(f"\n===== {name} =====")
    print(f"Rows: {df.shape[0]}")
    print(f"Columns: {df.shape[1]}")

    keywords = [
        "описание",
        "заключение",
        "лаб. номер",
        "рез-т",
        "№",
    ]

    print("\nPossible header rows:")

    for row_index in range(min(20, len(df))):
        found_keywords = []

        for value in df.iloc[row_index]:
            if pd.isna(value):
                continue

            text = str(value).strip().lower()

            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(keyword)

        if found_keywords:
            print(
                f"Row {row_index}: "
                f"{sorted(set(found_keywords))}"
            )


def main():
    inspect_raw_table(DATA_1_PATH, "Table 1")
    inspect_raw_table(DATA_2_PATH, "Table 2")
'''

# Функция загрузки данных из таблицы "Описания_и_заключения_цитологии_ЭНЦ_ослепленные_"
def load_table_1():
    # В первой таблице заголовок занимает две строки: pandas-строки 7 и 8
    # header=[7, 8] говорит pandas использовать обе строки, как двухуровневый заголовок в виде кортежей
    df = pd.read_excel(
        DATA_1_PATH,
        header=[7, 8],
    )

    return df

# Функция загрузки данных из таблицы "Доп. описания"
def load_table_2():
    # Во второй таблице заголовок находится в pandas-строке 5
    df = pd.read_excel(
        DATA_2_PATH,
        header=5,
    )

    return df

# Определяем столбцы и заполненные строки
def inspect_table(df, name):
    print(f"\n{name}")

    print("\nColumn names:")

    for column in df.columns:
        print(f"- {column}")

    total_rows = len(df)

    # Строка считается непустой, если заполнена хотя бы одна ячейка
    non_empty_rows = df.notna().any(axis=1).sum()

    # Строка считается полностью заполненной, если во всех столбцах есть значения
    fully_filled_rows = df.notna().all(axis=1).sum()

    print(f"\nTotal rows: {total_rows}")
    print(f"Non-empty rows: {non_empty_rows}")
    print(f"Fully filled rows: {fully_filled_rows}")

# Объединяем таблицы по одинаковым столбцам и создаем новые bethesda и needs_review
def create_dataset(df_1, df_2):
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

    # Объединяем обе таблицы в одну
    dataset = pd.concat(
        [table_1, table_2],
        ignore_index=True,
    )

    # Эти два столбца пока только создаём
    dataset["bethesda"] = pd.NA
    dataset["needs_review"] = False

    # Устанавливаем порядок столбцов
    dataset = dataset[
        [
            "case_id",
            "description",
            "conclusion",
            "bethesda",
            "needs_review",
        ]
    ]

    return dataset

# Удаляем полные дубликаты. Считаем полными дубликатами строки,
# у которых одновременно совпадают описание и заключение
def remove_full_duplicates(dataset):
    duplicates_count = dataset.duplicated(
        subset=["description", "conclusion"]
    ).sum()

    # Оставляем первое вхождение каждой записи
    dataset = dataset.drop_duplicates(
        subset=["description", "conclusion"],
        keep="first",
    )

    # После удаления восстанавливаем обычную последовательную индексацию
    dataset = dataset.reset_index(drop=True)

    print(f"\nRemoved full duplicates: {duplicates_count}")
    print(f"Rows after duplicate removal: {len(dataset)}")

    return dataset

# Есть ли Bethesda в описании?
def inspect_bethesda_in_description(dataset):
    # Берём только столбец description.
    # Пропуски заменяем пустой строкой, чтобы поиск не выдавал ошибок.
    descriptions = dataset["description"].fillna("").astype(str)

    # Ищем слово Bethesda без учёта регистра
    bethesda_mask = descriptions.str.contains(
        r"\bbethesda\b",
        case=False,
        regex=True,
    )

    # Ищем основу слова "категор"
    category_mask = descriptions.str.contains(
        r"категор",
        case=False,
        regex=True,
    )

    # Римские числа Bethesda от I до VI
    roman_pattern = r"(?<![A-Za-z])(?:VI|IV|V|III|II|I)(?![A-Za-z])"

    roman_mask = descriptions.str.contains(
        roman_pattern,
        case=False,
        regex=True,
    )

    # Ищем конструкции, где Bethesda находится рядом с римской категорией
    #
    # Примеры:
    # Bethesda-II
    # Bethesda II
    # Bethesda: II
    # Bethesda: диагностическая категория VI
    bethesda_category_mask = descriptions.str.contains(
        rf"\bbethesda\b[\s\S]{{0,100}}?{roman_pattern}",
        case=False,
        regex=True,
    )

    # Отдельно ищем конструкции вида:
    # категория II
    # диагностическая категория VI
    category_number_mask = descriptions.str.contains(
        rf"категор\w*[\s\S]{{0,50}}?{roman_pattern}",
        case=False,
        regex=True,
    )

    # Строка считается подозрительной на наличие Bethesda-категории,
    # если сработал хотя бы один из двух контекстных вариантов.
    suspected_bethesda_mask = (
        bethesda_category_mask | category_number_mask
    )

    print("\nBethesda check in description:")

    print(
        f"Rows containing 'Bethesda': "
        f"{bethesda_mask.sum()}"
    )

    print(
        f"Rows containing 'категор': "
        f"{category_mask.sum()}"
    )

    print(
        f"Rows containing Roman numerals I-VI: "
        f"{roman_mask.sum()}"
    )

    print(
        f"Rows containing a probable Bethesda category: "
        f"{suspected_bethesda_mask.sum()}"
    )

    suspected_ids = dataset.loc[
        suspected_bethesda_mask,
        "case_id",
    ]

    print("\nCase IDs with probable Bethesda category in description:")

    for case_id in suspected_ids:
        print(case_id)

# Функция поиска категории Bethesda в заключении
def extract_bethesda_categories(text):
    # Если заключение отсутствует, категорию определить невозможно.
    if pd.isna(text):
        return pd.NA

    text = str(text)

    # Римские категории Bethesda.
    # Более длинные варианты идут первыми, чтобы, например,
    # III не распознавалось как I.
    roman_pattern = r"(VI|IV|V|III|II|I)"

    # Здесь будем хранить все найденные категории.
    found_categories = []

    # Ищем варианты, где прямо упоминается Bethesda.
    #
    # Учитываем:
    # Bethesda II
    # Bethesda-II
    # Bethesda: II
    # Bethesda: диагностическая категория VI
    #
    # [aа] учитывает как латинскую "a", так и кириллическую "а"
    # в слове Bethesda, потому что в исходных текстах такое может встречаться.
    bethesda_pattern = (
        rf"\bbethesd[aа]\b"
        rf"[\s\S]{{0,250}}?"
        rf"\b{roman_pattern}\b"
    )

    # Ищем варианты:
    # категория II
    # диагностическая категория IV
    # категории VI
    category_pattern = (
        rf"категор\w*"
        rf"[\s\S]{{0,80}}?"
        rf"\b{roman_pattern}\b"
    )

    # Поиск категорий рядом со словом Bethesda.
    for match in re.finditer(
        bethesda_pattern,
        text,
        flags=re.IGNORECASE,
    ):
        category = match.group(1).upper()

        if category not in found_categories:
            found_categories.append(category)

    # Поиск категорий рядом со словом "категория".
    for match in re.finditer(
        category_pattern,
        text,
        flags=re.IGNORECASE,
    ):
        category = match.group(1).upper()

        if category not in found_categories:
            found_categories.append(category)

    # Если ничего не найдено.
    if not found_categories:
        return pd.NA

    # Например:
    # ["II"] -> "II"
    # ["I", "III"] -> "I, III"
    return ", ".join(found_categories)

# Заполнение столбца bethesda найденными категориями
def fill_bethesda(dataset):
    dataset["bethesda"] = dataset["conclusion"].apply(
        extract_bethesda_categories
    )

    return dataset

# Заполнение столбца needs_review, если описание отсутствует;
# найдено несколько категорий;
# категория не распознана
def mark_needs_review(dataset):
    # 1. Описание отсутствует:
    # либо NaN, либо пустая строка, либо строка только из пробелов.
    missing_description = (
        dataset["description"].isna()
        | dataset["description"].fillna("").str.strip().eq("")
    )

    # 2. Найдено несколько разных категорий Bethesda.
    multiple_categories = (
        dataset["bethesda"]
        .fillna("")
        .str.contains(",")
    )

    # 3. Категория Bethesda не распознана.
    category_not_found = dataset["bethesda"].isna()

    # needs_review = True, если выполнено хотя бы одно условие.
    dataset["needs_review"] = (
        missing_description
        | multiple_categories
        | category_not_found
    )

    return dataset


def main():
    df_1 = load_table_1()
    df_2 = load_table_2()

    inspect_table(df_1,"Table_1: Описания_и_заключения_цитологии_ЭНЦ_ослепленные_")

    inspect_table(df_2,"Table_2: Доп. описания")

    dataset = create_dataset(df_1, df_2)
    print("\nCombined dataset")

    print("\nColumn names:")
    for column in dataset.columns:
        print(f"- {column}")

    print(f"\nTotal rows: {len(dataset)}")

    dataset = remove_full_duplicates(dataset)

    inspect_bethesda_in_description(dataset)

    dataset = fill_bethesda(dataset)

    dataset = mark_needs_review(dataset)


if __name__ == "__main__":
    main()