import logging
import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlencode

from .config import CONFIG
from .http import Client

log = logging.getLogger(__name__)

IT_ROLES = {
    96: "Программист, разработчик",
    160: "DevOps-инженер",
    165: "Дата-сайентист",
    124: "Тестировщик",
    148: "Системный аналитик",
    164: "Продуктовый аналитик",
    156: "BI-аналитик",
    10: "Аналитик",
    104: "Руководитель группы разработки",
    125: "Технический директор (CTO)",
    113: "Системный администратор",
    114: "Системный инженер",
    116: "Специалист по информационной безопасности",
}

AREAS = {1: "Москва", 2: "Санкт-Петербург", 113: "Россия"}

VACANCY_ID = re.compile(r"/vacancy/(\d{6,})")
MAX_PAGES = 40 


def search_url(role: int, area: int, page: int) -> str:
    params = {
        "professional_role": role,
        "area": area,
        "page": page,
        "items_on_page": 50,
        "order_by": "publication_time",
    }
    return "/search/vacancy?" + urlencode(params)


def iter_ids(client: Client, role: int, area: int) -> Iterator[str]:
    """Отдаёт ID вакансий по одной роли в одном регионе, страница за страницей."""
    seen: set[str] = set()
    for page in range(MAX_PAGES):
        html = client.get(search_url(role, area, page))
        ids = set(VACANCY_ID.findall(html)) - seen
        if not ids: 
            break
        seen |= ids
        log.info("роль %s, регион %s, стр. %d: +%d", role, area, page, len(ids))
        yield from ids


def collect(roles=IT_ROLES, areas=AREAS, out: Path = CONFIG.data_dir / "ids.txt") -> int:
    """Собирает ID по всем ролям и регионам, дописывает новые в файл. Возвращает число новых."""
    out.parent.mkdir(parents=True, exist_ok=True)
    known = set(out.read_text().split()) if out.exists() else set()
    client = Client()
    added = 0
    with out.open("a") as f:
        for role in roles:
            for area in areas:
                for vid in iter_ids(client, role, area):
                    if vid not in known:
                        known.add(vid)
                        f.write(vid + "\n")
                        added += 1
                f.flush()
    return added
