# Thyroid Cytology Assistant

Исследовательский ML-прототип для работы с текстовыми цитологическими описаниями.

Проект включает две функции:
1. **Bethesda classification** — определение предполагаемой категории Bethesda I–VI по тексту цитологического описания.
2. **Similar case search** — поиск наиболее похожих цитологических случаев по тексту описания.

> Исследовательский прототип. Результат требует проверки врачом и не является медицинским заключением.

## Structure

```text
data/
  synthetic/          # только искусственные примеры
notebooks/
  classification/     # эксперименты Савелия
  search/             # эксперименты Вильдана
src/
  classification/     # код Bethesda classification
  search/             # код similar case search
  common/             # общий код
tests/
```

Реальные медицинские Excel/CSV и идентификаторы пациентов в Git не загружаются.

## Environment

Рекомендуемая версия: **Python 3.11**.

```bash
python -m venv .venv
pip install -r requirements.txt
```

## Git workflow

- основная ветка: `main`;
- Савелий: `feature/classification`;
- Вильдан: `feature/search`;
- в `main` напрямую не пишем;
- законченное небольшое изменение фиксируем commit;
- готовую работу добавляем через Pull Request;
- перед merge второй участник просматривает изменения.

## MLflow

Эксперименты:

```text
bethesda-classification
semantic-case-search
```

Запуск локального интерфейса:

```bash
mlflow ui
```

После запуска:

```text
http://127.0.0.1:5000
```

Для каждого запуска сохраняем имя участника, задачу, дату, версию датасета, модель, параметры, размер train/test, метрики, артефакты, обученную модель и Git commit.

## Planned baselines

### Bethesda classification
- TF-IDF + Logistic Regression
- Linear SVM или RuBERT

### Similar case search
- TF-IDF или BM25
- sentence-transformers + FAISS

## Interface

На второй неделе общий интерфейс собирается на Streamlit:
- страница Bethesda classification;
- страница поиска пяти похожих случаев.
