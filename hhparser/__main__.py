"""Точка входа: python -m hhparser <команда>.

Порядок работы:
    python -m hhparser ids --mode it      # найти id IT-вакансий
    python -m hhparser fetch --limit 500  # скачать страницы в кеш
    python -m hhparser parse              # разобрать кеш в data/vacancies.parquet
    python -m hhparser inspect 123456789  # посмотреть, что есть на странице
"""

import argparse
import json
import logging

import pandas as pd

from . import config, discover, fetch, parse, trudvsem
from .http import PoliteClient


def cmd_ids(args):
    client = PoliteClient()
    rows = discover.by_it_slugs(client, args.max_slugs) if args.mode == "it" else discover.by_sitemap(client)
    print(f"новых id: {discover.save_ids(rows)} (файл {config.IDS_FILE})")


def cmd_fetch(args):
    fetch.fetch_all(limit=args.limit, shuffle=not args.no_shuffle)


def cmd_parse(args):
    files = sorted(config.RAW_DIR.glob("*.html.gz"))
    rows, errors = [], 0
    for p in files:
        try:
            rows.append(parse.parse_file(p))
        except Exception as e:  # одна битая страница не должна ронять весь разбор
            errors += 1
            logging.warning("ошибка разбора %s: %s", p.name, e)
    df = pd.DataFrame(rows)
    df.to_parquet(config.PARSED_FILE, index=False)
    with_salary = df["salary_from"].notna() | df["salary_to"].notna() if "salary_from" in df else []
    print(f"разобрано {len(df)}, ошибок {errors}, с зарплатой {int(sum(with_salary))}")
    print(f"сохранено в {config.PARSED_FILE}")


def cmd_inspect(args):
    path = fetch.raw_path(args.id)
    if path.exists():
        import gzip
        html = gzip.open(path, "rt", encoding="utf-8").read()
    else:
        resp = PoliteClient().get(f"{config.BASE_URL}/vacancy/{args.id}")
        if resp is None:
            print("вакансия не найдена")
            return
        html = resp.text
    print(json.dumps(parse.inspect_html(html), ensure_ascii=False, indent=2))
    print("\n--- результат разбора ---")
    row = parse.parse_html(html, args.id)
    if row.get("description"):
        row["description"] = row["description"][:300] + "…"
    print(json.dumps(row, ensure_ascii=False, indent=2, default=str))


def cmd_trudvsem(args):
    rows = trudvsem.fetch_vacancies(
        queries=args.query,
        limit_per_query=args.limit,
        page_size=args.page_size,
    )
    df = pd.DataFrame(rows)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(config.TRUDVSEM_PARSED_FILE, index=False)
    print(f"собрано вакансий: {len(df)}")
    print(f"с зарплатой: {int((df['salary_from'].notna() | df['salary_to'].notna()).sum()) if len(df) else 0}")
    print(f"сохранено в {config.TRUDVSEM_PARSED_FILE}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="hhparser")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ids", help="найти ссылки на вакансии")
    p.add_argument("--mode", choices=["it", "all"], default="it")
    p.add_argument("--max-slugs", type=int, default=None, help="ограничить число профессий (для пробы)")
    p.set_defaults(func=cmd_ids)

    p = sub.add_parser("fetch", help="скачать страницы вакансий")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--no-shuffle", action="store_true")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("parse", help="разобрать скачанное в parquet")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("inspect", help="показать, что есть на странице вакансии")
    p.add_argument("id")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("trudvsem", help="скачать вакансии из открытого API Работа России")
    p.add_argument(
        "--query", action="append", required=True,
        help="поисковая фраза; можно указать несколько раз",
    )
    p.add_argument(
        "--limit", type=int, default=100,
        help="максимум вакансий на одну фразу (по умолчанию 100)",
    )
    p.add_argument(
        "--page-size", type=int, default=100,
        help="размер страницы API, максимум 100",
    )
    p.set_defaults(func=cmd_trudvsem)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
