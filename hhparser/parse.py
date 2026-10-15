"""Разбор страницы вакансии в плоский словарь.

Стратегия:
1. JSON-LD с типом JobPosting — стандартная разметка для поисковиков,
   меняется редко. Отсюда берём основу, включая зарплату.
2. Атрибуты data-qa в HTML — запасной источник для того,
   чего нет в JSON-LD (опыт, навыки, «на руки» или «до вычета»).

Если hh поменяет вёрстку, смотри `python -m hhparser inspect <id>`
и поправь DATA_QA ниже.
"""

import gzip
import json
import re

from bs4 import BeautifulSoup

# data-qa → имя поля. Сверено с живой страницей hh.ru (октябрь 2026).
DATA_QA = {
    "vacancy-title": "title_html",
    "vacancy-salary": "salary_text",
    "vacancy-experience": "experience",
    "vacancy-company-name": "company_html",
    "vacancy-view-raw-address": "address",
    "vacancy-description": "description_html",
    "common-employment-text": "employment",
    "work-formats-text": "work_format",
    "work-schedule-by-days-text": "schedule",
    "working-hours-text": "working_hours",
    "compensation-frequency-text": "pay_frequency",
}
SKILL_QA = ("skills-element", "bloko-tag__text", "skills-list-item")

# «Формат работы: удалённо» → «удалённо»: убираем подписи перед двоеточием.
STRIP_LABEL_FIELDS = ("work_format", "schedule", "working_hours", "pay_frequency")

# --- зарплата из текста ---
CURRENCIES = [("₽", "RUR"), ("руб", "RUR"), ("$", "USD"), ("usd", "USD"),
              ("€", "EUR"), ("eur", "EUR"), ("₸", "KZT"), ("kzt", "KZT"),
              ("byn", "BYN"), ("сум", "UZS"), ("₾", "GEL")]
PERIODS = [("за месяц", "month"), ("в месяц", "month"), ("за смену", "shift"),
           ("за час", "hour"), ("в час", "hour"), ("за день", "day"), ("за год", "year")]
_NUM = r"(\d[\d ]*)"
_FROM_RE = re.compile(r"от\s*" + _NUM)
_TO_RE = re.compile(r"до\s*" + _NUM)
_ANY_NUM_RE = re.compile(_NUM)


def _to_int(s: str) -> int | None:
    digits = s.replace(" ", "")
    return int(digits) if digits.isdigit() else None


def parse_salary_text(text: str | None) -> dict:
    """«от 150 000 до 200 000 ₽ за месяц на руки» → from/to/валюта/период."""
    out = {"salary_from": None, "salary_to": None, "currency": None, "salary_period": None}
    if not text:
        return out
    # неразрывные пробелы между разрядами → обычные
    s = text.replace("\xa0", " ").replace(" ", " ").replace(" ", " ").lower()
    # «до вычета налогов» содержит «до», но это не верхняя граница — вырезаем
    s = s.replace("до вычета", "")
    m_from, m_to = _FROM_RE.search(s), _TO_RE.search(s)
    if m_from:
        out["salary_from"] = _to_int(m_from.group(1))
    if m_to:
        out["salary_to"] = _to_int(m_to.group(1))
    if not m_from and not m_to:
        m = _ANY_NUM_RE.search(s)
        if m:
            out["salary_from"] = out["salary_to"] = _to_int(m.group(1))
    if out["salary_from"] is None and out["salary_to"] is None:
        return out
    out["currency"] = next((code for sym, code in CURRENCIES if sym in s), None)
    out["salary_period"] = next((p for phrase, p in PERIODS if phrase in s), None)
    return out


MAX_SKILLS = 40
MAX_SKILL_LEN = 60


def _skills_by_heading(soup: BeautifulSoup) -> list[str]:
    """Запасной путь: заголовок «Ключевые навыки» и список СРАЗУ после него.

    Берём только ближайший следующий соседний элемент заголовка. Вверх по
    странице не поднимаемся: иначе цепляются описание, подвал и похожие вакансии.
    Если список подозрительный (слишком длинный или с длинными строками),
    возвращаем пусто: лучше пропустить навыки, чем записать мусор.
    """
    head = soup.find(string=re.compile(r"^\s*Ключевые навыки\s*$"))
    if head is None:
        return []
    heading = head.find_parent()
    nxt = heading.find_next_sibling() if heading else None
    # список должен идти прямо за заголовком: <ul>/<ol> или обёртка, чей первый ребёнок — список
    if nxt is not None and nxt.name not in ("ul", "ol"):
        if nxt.name != "div":  # footer, nav, section и прочее — точно не блок навыков
            return []
        first = nxt.find(True, recursive=False)
        nxt = first if first is not None and first.name in ("ul", "ol") else None
    if nxt is None:
        return []
    items = [li.get_text(" ", strip=True) for li in nxt.find_all("li")]
    if not items or len(items) > MAX_SKILLS or any(len(s) > MAX_SKILL_LEN for s in items):
        return []
    return items

# Чистим описание от контактов: это персональные данные рекрутеров.
CONTACT_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                 # email
    re.compile(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}"),  # телефон
    re.compile(r"(?:https?://)?t\.me/\S+"),                  # ссылки на Telegram
    re.compile(r"(?<!\w)@[A-Za-z][\w]{3,}"),                 # @username
]


def scrub_contacts(text: str) -> str:
    for p in CONTACT_PATTERNS:
        text = p.sub("[контакт]", text)
    return text


def html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    text = BeautifulSoup(html, "lxml").get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def _iter_ld(soup: BeautifulSoup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        yield from (i for i in items if isinstance(i, dict))


def job_posting(soup: BeautifulSoup) -> dict | None:
    for item in _iter_ld(soup):
        t = item.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            return item
    return None


def _num(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def salary_from_ld(jp: dict) -> dict:
    out = {"salary_from": None, "salary_to": None, "currency": None, "salary_period": None}
    bs = jp.get("baseSalary")
    if not isinstance(bs, dict):
        return out
    out["currency"] = bs.get("currency")
    val = bs.get("value")
    if isinstance(val, dict):
        out["salary_from"] = _num(val.get("minValue"))
        out["salary_to"] = _num(val.get("maxValue"))
        single = _num(val.get("value"))
        if single is not None and out["salary_from"] is None and out["salary_to"] is None:
            out["salary_from"] = out["salary_to"] = single
        out["salary_period"] = val.get("unitText")
    else:
        out["salary_from"] = out["salary_to"] = _num(val)
    return out


def gross_flag(salary_text: str | None) -> bool | None:
    """True — до вычета налогов, False — на руки, None — не указано."""
    if not salary_text:
        return None
    s = salary_text.lower()
    if "до вычета" in s:
        return True
    if "на руки" in s:
        return False
    return None


def _ld_location(jp: dict) -> str | None:
    loc = jp.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        addr = loc.get("address")
        if isinstance(addr, dict):
            return addr.get("addressLocality") or addr.get("addressRegion")
    return None


def parse_html(html: str, vid: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    row: dict = {"id": vid}

    # 1. JSON-LD
    jp = job_posting(soup)
    row["has_ld"] = jp is not None
    if jp:
        org = jp.get("hiringOrganization")
        row.update({
            "title": jp.get("title"),
            "description": html_to_text(jp.get("description")),
            "date_posted": jp.get("datePosted"),
            "valid_through": jp.get("validThrough"),
            "employment_type": jp.get("employmentType"),
            "company": org.get("name") if isinstance(org, dict) else None,
            "city": _ld_location(jp),
            "ld_experience": json.dumps(jp.get("experienceRequirements"), ensure_ascii=False)
            if jp.get("experienceRequirements") else None,
            **salary_from_ld(jp),
        })

    # 2. data-qa (дополняем то, чего не хватило)
    for qa, field in DATA_QA.items():
        el = soup.find(attrs={"data-qa": qa})
        if el is None:
            continue
        if field.endswith("_html"):
            key = field.removesuffix("_html")
            if not row.get(key):
                row[key] = html_to_text(str(el))
        else:
            row[field] = el.get_text(" ", strip=True)

    for field in STRIP_LABEL_FIELDS:
        if row.get(field) and ":" in row[field]:
            row[field] = row[field].split(":", 1)[1].strip()

    skills = []
    for qa in SKILL_QA:
        skills += [el.get_text(" ", strip=True) for el in soup.find_all(attrs={"data-qa": qa})]
    if not skills:
        skills = _skills_by_heading(soup)
    row["skills"] = sorted(set(s for s in skills if s)) or None

    # Зарплата: если в JSON-LD её не было, берём из текста на странице.
    row["salary_source"] = "ld" if (row.get("salary_from") or row.get("salary_to")) else None
    if row["salary_source"] is None:
        parsed = parse_salary_text(row.get("salary_text"))
        if parsed["salary_from"] or parsed["salary_to"]:
            row.update(parsed)
            row["salary_source"] = "text"

    row["salary_gross"] = gross_flag(row.get("salary_text"))
    if row.get("description"):
        row["description"] = scrub_contacts(row["description"])
    return row


def parse_file(path) -> dict:
    vid = path.name.split(".")[0]
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return parse_html(f.read(), vid)


def inspect_html(html: str) -> dict:
    """Что есть на странице: типы JSON-LD и все data-qa. Для подгонки парсера."""
    soup = BeautifulSoup(html, "lxml")
    ld_types = [i.get("@type") for i in _iter_ld(soup)]
    qa = {}
    for el in soup.find_all(attrs={"data-qa": True}):
        key = el["data-qa"]
        if key not in qa:
            qa[key] = el.get_text(" ", strip=True)[:80]
    return {"ld_types": ld_types, "data_qa": qa}