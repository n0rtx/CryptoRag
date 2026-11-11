"""Обучение фильтра мусорных запросов. Запуск: python scripts/train_filter.py

Результат: models/query_filter.joblib (коммитится в репозиторий — на сервере обучать не нужно).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from backend import config
from backend.guard.dataset import build


def make_pipeline() -> Pipeline:
    feats = FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True)),
    ])
    return Pipeline([("tfidf", feats), ("clf", LogisticRegression(C=8, max_iter=2000, class_weight="balanced"))])


def main():
    X, y = build(extra_csv=config.ROOT / "data" / "filter_extra.csv")
    X = [t.lower() for t in X]
    print(f"Примеров: {len(X)} (крипта: {sum(y)}, мусор: {len(y) - sum(y)})")
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=1, stratify=y)
    p = make_pipeline().fit(Xtr, ytr)
    print(classification_report(yte, p.predict(Xte), target_names=["junk", "crypto"], digits=3))
    p = make_pipeline().fit(X, y)  # финальная модель — на всех данных
    config.MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(p, config.MODEL_PATH, compress=3)
    print(f"Сохранено: {config.MODEL_PATH} ({config.MODEL_PATH.stat().st_size / 1024:.0f} КБ)")


if __name__ == "__main__":
    main()
