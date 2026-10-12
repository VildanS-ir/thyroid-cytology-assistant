"""Функции для версионирования файлов датасетов."""

import hashlib
import shutil
from pathlib import Path


def calculate_sha256(file_path: Path) -> str:
    """Возвращает полный SHA256-хеш файла."""

    sha256 = hashlib.sha256()

    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def save_dataset_version(dataset_path: Path) -> tuple[str, Path]:
    """
    Сохраняет неизменяемую копию датасета с коротким хешем в имени.

    Возвращает полный SHA256 и путь к сохранённой версии.
    """

    file_hash = calculate_sha256(dataset_path)

    versions_dir = dataset_path.parent / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    version_path = (
        versions_dir
        / f"{dataset_path.stem}_{file_hash[:12]}{dataset_path.suffix}"
    )

    # Одинаковый датасет повторно не копируем
    if not version_path.exists():
        shutil.copy2(dataset_path, version_path)

    return file_hash, version_path