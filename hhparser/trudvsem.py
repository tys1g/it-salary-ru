"""Загрузка вакансий из официального открытого API «Работа России».

В локальный набор попадают только поля, нужные для анализа и ML.
Контакты, ИНН и другие идентификаторы работодателя намеренно не сохраняются.
"""

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

API_URL = "https://opendata.trudvsem.ru/api/v1/vacancies"
REQUEST_DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 30
MAX_PAGE_SIZE = 100


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _normalize(item: dict[str, Any]) -> dict[str, Any] | None:
    vacancy = item.get("vacancy", item)
    if not isinstance(vacancy, dict) or not vacancy.get("id"):
        return None

    region = vacancy.get("region") or {}
    requirement = vacancy.get("requirement") or {}
    category = vacancy.get("category") or {}
    return {
        "id": f"trudvsem:{vacancy['id']}",
        "source_id": str(vacancy["id"]),
        "source": "trudvsem",
        "title": vacancy.get("job-name"),
        "description": vacancy.get("duty"),
        "requirements_text": vacancy.get("requirements"),
        "salary_from": _as_int(vacancy.get("salary_min")),
        "salary_to": _as_int(vacancy.get("salary_max")),
        "salary_text": vacancy.get("salary"),
        "currency": vacancy.get("currency"),
        "salary_period": None,
        # В ответе API налоговый статус зарплаты не указан: не угадываем его.
        "salary_gross": None,
        "salary_tax_status": "unknown",
        "date_posted": vacancy.get("creation-date"),
        "region": region.get("name"),
        "city": None,
        "experience": requirement.get("experience"),
        "education": requirement.get("education"),
        "category": category.get("specialisation"),
        "employment": vacancy.get("employment"),
        "schedule": vacancy.get("schedule"),
        "url": vacancy.get("vac_url"),
    }


def fetch_vacancies(
    queries: list[str],
    limit_per_query: int = 100,
    page_size: int = MAX_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Скачивает до limit_per_query вакансий на поисковую фразу и удаляет дубли."""
    if not queries or any(not query.strip() for query in queries):
        raise ValueError("укажите непустую поисковую фразу")
    if limit_per_query < 1:
        raise ValueError("limit_per_query должен быть больше нуля")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size должен быть от 1 до {MAX_PAGE_SIZE}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "it-salary-ru research project",
        "Accept": "application/json",
    })

    rows_by_id: dict[str, dict[str, Any]] = {}
    for query_index, query in enumerate(queries):
        if query_index:
            time.sleep(REQUEST_DELAY_SECONDS)
        offset = 0
        fetched_for_query = 0
        while fetched_for_query < limit_per_query:
            current_limit = min(page_size, limit_per_query - fetched_for_query)
            params = {"text": query, "limit": current_limit, "offset": offset}
            log.info("запрос Работа России: %r, offset=%d, limit=%d", query, offset, current_limit)
            response = session.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()

            if str(payload.get("status")) != "200":
                raise RuntimeError(f"API Работа России вернул статус: {payload.get('status')}")

            results = payload.get("results") or {}
            items = results.get("vacancies") or []
            if not items:
                break

            for item in items:
                row = _normalize(item)
                if row is not None:
                    rows_by_id.setdefault(row["id"], row)

            fetched_for_query += len(items)
            offset += len(items)

            total = _as_int((payload.get("meta") or {}).get("total"))
            if len(items) < current_limit or (total is not None and offset >= total):
                break
            time.sleep(REQUEST_DELAY_SECONDS)

        log.info("по запросу %r получено строк: %d", query, fetched_for_query)

    return list(rows_by_id.values())
