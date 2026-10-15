"""Поиск ссылок на вакансии.

Два способа, оба опираются на карту сайта hh.ru (её указывает robots.txt):
1. by_sitemap  — все вакансии из vacancyN.xml (много, не только IT).
2. by_it_slugs — страницы профессий /vacancies/<slug> для IT-профессий,
                 из них берём id вакансий. Меньше, зато почти только IT.
"""

import csv
import logging
import re
from xml.etree import ElementTree as ET

from . import config
from .http import PoliteClient

log = logging.getLogger(__name__)
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
VACANCY_ID_RE = re.compile(r"/vacancy/(\d+)")


def _locs(xml_text: str) -> list[tuple[str, str | None]]:
    """Достаёт пары (loc, lastmod) из sitemap или sitemap index."""
    root = ET.fromstring(xml_text)
    out = []
    for node in root.findall(".//sm:sitemap", NS) + root.findall(".//sm:url", NS):
        loc = node.findtext("sm:loc", namespaces=NS)
        lastmod = node.findtext("sm:lastmod", namespaces=NS)
        if loc:
            out.append((loc.strip(), lastmod))
    return out


def sitemap_files(client: PoliteClient, prefix: str) -> list[str]:
    """Файлы из индекса карты сайта, имя которых начинается с prefix."""
    log.info("читаем индекс карты сайта %s", config.SITEMAP_INDEX)
    resp = client.get(config.SITEMAP_INDEX)
    if resp is None:
        raise RuntimeError("не удалось получить индекс карты сайта")
    files = [loc for loc, _ in _locs(resp.text)]
    return [f for f in files if f.rsplit("/", 1)[-1].startswith(prefix)]


def by_sitemap(client: PoliteClient) -> list[dict]:
    rows = []
    for sm in sitemap_files(client, "vacancy"):
        # отсекаем vacancies*.xml: там страницы профессий, а не вакансии
        if sm.rsplit("/", 1)[-1].startswith("vacancies"):
            continue
        resp = client.get(sm)
        if resp is None:
            continue
        for loc, lastmod in _locs(resp.text):
            m = VACANCY_ID_RE.search(loc)
            if m:
                rows.append({"id": m.group(1), "url": loc, "lastmod": lastmod, "source": "sitemap"})
        log.info("%s: всего ссылок %d", sm, len(rows))
    return rows


def it_slugs(client: PoliteClient) -> list[str]:
    slugs = []
    for sm in sitemap_files(client, "vacancies"):
        resp = client.get(sm)
        if resp is None:
            continue
        locs = _locs(resp.text)
        found = 0
        for loc, _ in locs:
            slug = loc.rstrip("/").rsplit("/", 1)[-1]
            if any(k in slug for k in config.IT_SLUG_KEYWORDS):
                slugs.append(slug)
                found += 1
        log.info("%s: профессий %d, из них IT %d", sm.rsplit("/", 1)[-1], len(locs), found)
    return sorted(set(slugs))


def by_it_slugs(client: PoliteClient, max_slugs: int | None = None) -> list[dict]:
    slugs = it_slugs(client)
    log.info("найдено IT-профессий: %d", len(slugs))
    rows, seen = [], set()
    for slug in slugs[:max_slugs]:
        resp = client.get(f"{config.BASE_URL}/vacancies/{slug}")
        if resp is None:
            continue
        for vid in VACANCY_ID_RE.findall(resp.text):
            if vid not in seen:
                seen.add(vid)
                rows.append({"id": vid, "url": f"{config.BASE_URL}/vacancy/{vid}",
                             "lastmod": None, "source": f"slug:{slug}"})
        log.info("%s: всего id %d", slug, len(rows))
    return rows


def save_ids(rows: list[dict]) -> int:
    """Дописывает новые id в ids.csv, дубли пропускает. Возвращает число новых."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = set()
    if config.IDS_FILE.exists():
        with config.IDS_FILE.open(newline="") as f:
            existing = {r["id"] for r in csv.DictReader(f)}
    new = [r for r in rows if r["id"] not in existing]
    write_header = not config.IDS_FILE.exists()
    with config.IDS_FILE.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "url", "lastmod", "source"])
        if write_header:
            w.writeheader()
        w.writerows(new)
    return len(new)