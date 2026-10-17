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
TRUDVSEM_PARSED_FILE = DATA_DIR / "trudvsem_vacancies.parquet"

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
# Slug режем по «-» на слова и сравниваем каждое слово целиком или по началу.
# Раньше искали подстроку, и «produkt» ловил «administrator-produktovogo-magazina».

# Слово начинается с одного из этих префиксов → IT (длинные, без ложных совпадений).
IT_SLUG_PREFIXES = [
    "developer", "razrabotchik", "programmist", "python", "golang", "java",
    "frontend", "backend", "fullstack", "devops", "devsecops", "analitik",
    "analyst", "machine", "testirovsh", "tester", "android", "kotlin", "swift",
    "sistemnyj", "architect", "tehlid", "teamlead", "scala", "unity", "rust",
    "product", "scientist", "engineer", "postgres", "mysql", "mssql", "oracle",
]
# Короткие слова: только точное совпадение, иначе «ml» найдётся где угодно.
IT_SLUG_WORDS = {"ml", "qa", "1c", "sre", "ios", "php", "go", "bi", "sql", "data", "it", "c"}
# Если в slug есть такое слово — это точно не IT, даже если нашлось ключевое.
NON_IT_SLUG_WORDS = {
    "magazina", "magazin", "prodazh", "prodazham", "sklada", "kassir",
    "torgovogo", "zala", "restorana", "gostinicy", "salona", "ofisa",
}
