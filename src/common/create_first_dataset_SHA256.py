"""Сохраняет версию dataset_first.csv с SHA256-хешем в имени файла."""

from pathlib import Path

from dataset_versioning import save_dataset_version


# Определяем корень проекта
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Путь к основному датасету классификации
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "dataset_first.csv"


def main() -> None:
    """Сохраняет текущую версию dataset_first.csv в архив."""

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Датасет не найден: {DATASET_PATH}"
        )

    # Сохраняем версию датасета и получаем его SHA256
    dataset_hash, version_path = save_dataset_version(DATASET_PATH)

    print(f"Dataset: {DATASET_PATH.name}")
    print(f"Dataset version: {dataset_hash[:12]}")
    print(f"Full SHA256: {dataset_hash}")
    print(f"Saved version: {version_path}")


if __name__ == "__main__":
    main()