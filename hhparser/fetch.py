"""Скачивание страниц вакансий в кеш data/raw/<id>.html.gz.

Каждая страница качается один раз. Если парсер потом поменяется,
перезапускаем только разбор, а не загрузку.
"""

import csv
import gzip
import logging
import random

from . import config
from .http import BlockedError, PoliteClient

log = logging.getLogger(__name__)


def raw_path(vid: str):
    return config.RAW_DIR / f"{vid}.html.gz"


def fetch_all(limit: int | None = None, shuffle: bool = True) -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    with config.IDS_FILE.open(newline="") as f:
        ids = [r["id"] for r in csv.DictReader(f)]
    todo = [i for i in ids if not raw_path(i).exists()]
    already = len(ids) - len(todo)  # считаем ДО обрезки по limit, иначе цифра врёт
    if shuffle:
        random.shuffle(todo)  # случайная выборка лучше, чем первые N по порядку
    if limit:
        todo = todo[:limit]
    log.info("всего id %d, уже скачано %d, в очереди сейчас %d", len(ids), already, len(todo))

    client = PoliteClient()
    done = gone = 0
    try:
        for n, vid in enumerate(todo, 1):
            resp = client.get(f"{config.BASE_URL}/vacancy/{vid}")
            if resp is None:
                gone += 1
                continue
            with gzip.open(raw_path(vid), "wt", encoding="utf-8") as out:
                out.write(resp.text)
            done += 1
            if n % 50 == 0:
                log.info("прогресс: %d/%d, скачано %d, удалённых %d", n, len(todo), done, gone)
    except BlockedError as e:
        log.error("%s. Остановились. Подожди и запусти позже с большей задержкой (HH_DELAY).", e)
    except KeyboardInterrupt:
        log.info("остановлено вручную, уже скачанное сохранено")
    log.info("итог: скачано %d, удалённых %d", done, gone)
