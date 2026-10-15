"""Настройки парсера. Всё, что может понадобиться поменять, лежит здесь."""

import os
from pathlib import Path

BASE_URL = "https://hh.ru"
SITEMAP_INDEX = f"{BASE_URL}/sitemap/main.xml"

# Папки с данными. Сырые данные в git не попадают (см. .gitignore).
DATA_DIR = Path(os.getenv("HH_DATA_DIR", "data"))
RAW_DIR = DATA_DIR / "raw"            # скачанные страницы вакансий, html.gz
IDS_FILE = DATA_DIR / "ids.csv"       # найденные ссылки на вакансии
PARSED_FILE = DATA_DIR / "vacancies.parquet"

# Вежливость. Не уменьшай задержку: частые запросы = бан IP и нагрузка на чужой сайт.
DELAY_SECONDS = float(os.getenv("HH_DELAY", "3.0"))   # базовая пауза между запросами
JITTER_SECONDS = float(os.getenv("HH_JITTER", "1.5")) # случайная добавка к паузе
TIMEOUT_SECONDS = 20
MAX_RETRIES = 4

# Честный User-Agent с контактом, чтобы владелец сайта мог с тобой связаться.
USER_AGENT = os.getenv(
    "HH_USER_AGENT",
    "it-salary-ru research bot (pet project; contact: your-email@example.com)",
)

# Ключевые слова для поиска IT-профессий среди страниц /vacancies/<slug>.
# Это латиница из транслитерированных названий профессий в карте сайта.
IT_SLUG_KEYWORDS = [
    "developer", "razrabotchik", "programmist", "python", "golang", "java",
    "frontend", "backend", "fullstack", "devops", "sre", "data", "analitik",
    "analyst", "ml", "machine", "qa", "testirovshik", "tester", "android",
    "ios", "kotlin", "swift", "php", "c-", "1c", "sistemnyj", "arhitektor",
    "architect", "tehlid", "teamlead", "inzhener-po-dannym", "devsecops",
    "sql", "bi-", "product-manager", "produkt", "unity", "rust", "scala",
]
