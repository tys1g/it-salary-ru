"""Тесты разбора на синтетической странице (без обращения к сайту)."""

import json

import pytest

from hhparser import parse
from hhparser.discover import _locs

LD = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Python-разработчик (Middle)",
    "description": "<p>Пишем бэкенд.</p><p>Пишите: hr@example.com, +7 (999) 123-45-67, @recruiter_anna</p>",
    "datePosted": "2026-10-01",
    "employmentType": "FULL_TIME",
    "hiringOrganization": {"@type": "Organization", "name": "ООО Пример"},
    "jobLocation": {"@type": "Place", "address": {"addressLocality": "Москва"}},
    "baseSalary": {
        "@type": "MonetaryAmount",
        "currency": "RUR",
        "value": {"@type": "QuantitativeValue", "minValue": 200000, "maxValue": 300000, "unitText": "MONTH"},
    },
}

HTML = f"""
<html><head><script type="application/ld+json">{json.dumps(LD, ensure_ascii=False)}</script></head>
<body>
  <span data-qa="vacancy-salary">от 200 000 до 300 000 ₽ на руки</span>
  <span data-qa="vacancy-experience">3–6 лет</span>
  <ul><li data-qa="skills-element">Python</li><li data-qa="skills-element">PostgreSQL</li>
      <li data-qa="skills-element">Python</li></ul>
</body></html>
"""


def test_parse_job_posting():
    row = parse.parse_html(HTML, "123")
    assert row["has_ld"] is True
    assert row["title"] == "Python-разработчик (Middle)"
    assert row["salary_from"] == 200000 and row["salary_to"] == 300000
    assert row["currency"] == "RUR" and row["salary_period"] == "MONTH"
    assert row["city"] == "Москва" and row["company"] == "ООО Пример"
    assert row["experience"] == "3–6 лет"
    assert row["skills"] == ["PostgreSQL", "Python"]  # без дублей
    assert row["salary_gross"] is False  # «на руки»


def test_contacts_removed():
    desc = parse.parse_html(HTML, "123")["description"]
    assert "hr@example.com" not in desc
    assert "999" not in desc
    assert "@recruiter_anna" not in desc


def test_no_ld_falls_back_to_data_qa():
    html = '<h1 data-qa="vacancy-title">Golang-разработчик</h1><div data-qa="vacancy-salary">до 400 000 ₽ до вычета налогов</div>'
    row = parse.parse_html(html, "1")
    assert row["has_ld"] is False
    assert row["title"] == "Golang-разработчик"
    assert row["salary_gross"] is True


def test_single_value_salary():
    ld = {"@type": "JobPosting", "baseSalary": {"currency": "USD", "value": {"value": 5000}}}
    out = parse.salary_from_ld(ld)
    assert out["salary_from"] == out["salary_to"] == 5000


def test_sitemap_locs():
    xml = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://hh.ru/vacancy/136961310</loc><lastmod>2026-09-30T16:16:32+03:00</lastmod></url>
    </urlset>"""
    assert _locs(xml) == [("https://hh.ru/vacancy/136961310", "2026-09-30T16:16:32+03:00")]


NBSP = "\xa0"
SALARY_CASES = [
    (f"от 150{NBSP}000 до 200{NBSP}000 ₽ за месяц на руки", 150000, 200000, "RUR", "month"),
    ("от 250 000 ₽ за месяц до вычета налогов", 250000, None, "RUR", "month"),
    ("до 4 000 $ за месяц на руки", None, 4000, "USD", "month"),
    ("3 500 € за месяц", 3500, 3500, "EUR", "month"),
    ("от 2 500 ₽ за смену", 2500, None, "RUR", "shift"),
    ("Уровень дохода не указан", None, None, None, None),
    (None, None, None, None, None),
]


@pytest.mark.parametrize("text,frm,to,cur,period", SALARY_CASES)
def test_parse_salary_text(text, frm, to, cur, period):
    out = parse.parse_salary_text(text)
    assert (out["salary_from"], out["salary_to"], out["currency"], out["salary_period"]) == (frm, to, cur, period)


# Фрагмент живой страницы hh.ru (октябрь 2026): JSON-LD без зарплаты,
# зарплата и условия только в data-qa.
LIVE_LIKE = """
<script type="application/ld+json">{"@type": "JobPosting", "title": "Системный администратор",
 "hiringOrganization": {"name": "РемиЛинг"}}</script>
<span data-qa="vacancy-salary">от 150 000 до 200 000 ₽ за месяц на руки</span>
<p data-qa="vacancy-experience">3–6 лет</p>
<p data-qa="common-employment-text">Полная занятость</p>
<p data-qa="work-schedule-by-days-text">График: 5/2</p>
<p data-qa="working-hours-text">Рабочие часы: 8</p>
<p data-qa="work-formats-text">Формат работы: на месте работодателя</p>
<p data-qa="compensation-frequency-text">Выплаты: два раза в месяц</p>
<div><h2>Ключевые навыки</h2><ul><li>Linux</li><li>Active Directory</li></ul></div>
"""


def test_live_like_page():
    row = parse.parse_html(LIVE_LIKE, "138504125")
    assert row["salary_source"] == "text"
    assert (row["salary_from"], row["salary_to"], row["currency"]) == (150000, 200000, "RUR")
    assert row["salary_gross"] is False
    assert row["work_format"] == "на месте работодателя"
    assert row["schedule"] == "5/2"
    assert row["working_hours"] == "8"
    assert row["pay_frequency"] == "два раза в месяц"
    assert row["employment"] == "Полная занятость"
    assert row["skills"] == ["Active Directory", "Linux"]  # через заголовок «Ключевые навыки»


def test_ld_salary_wins_over_text():
    row = parse.parse_html(HTML, "123")
    assert row["salary_source"] == "ld"


def test_skills_fallback_ignores_rest_of_page():
    # Как на реальной странице без навыков: «Ключевые навыки» встречается,
    # но рядом нет списка навыков, а ниже есть описание и подвал со списками.
    html = """
    <div>
      <div data-qa="vacancy-description"><ul><li>Настройка и администрирование AD, DNS, DHCP;</li></ul></div>
      <p>Ключевые навыки</p>
      <footer><ul><li>О компании</li><li>Блог</li></ul></footer>
    </div>"""
    assert parse.parse_html(html, "1")["skills"] is None


def test_skills_fallback_rejects_long_items():
    html = "<h2>Ключевые навыки</h2><ul><li>" + "очень длинный пункт описания " * 5 + "</li></ul>"
    assert parse.parse_html(html, "1")["skills"] is None