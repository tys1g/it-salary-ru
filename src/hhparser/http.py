import logging
import random
import time

import requests

from .config import CONFIG, Config

log = logging.getLogger(__name__)


class CaptchaError(RuntimeError):
    """hh.ru показал капчу — дальше парсить нельзя, нужно остановиться."""


class Client:
    def __init__(self, config: Config = CONFIG):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.user_agent,
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
        self._last_request = 0.0

    def _wait(self) -> None:
        """Держим паузу между запросами, чтобы не нагружать сайт."""
        delay = random.uniform(self.config.delay_min, self.config.delay_max)
        elapsed = time.monotonic() - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.monotonic()

    @staticmethod
    def _is_captcha(resp: requests.Response) -> bool:
        return "captcha" in resp.url or 'data-qa="captcha' in resp.text

    def get(self, path: str) -> str:
        url = path if path.startswith("http") else self.config.base_url + path
        for attempt in range(1, self.config.retries + 1):
            self._wait()
            try:
                resp = self.session.get(url, timeout=self.config.timeout)
            except requests.RequestException as e:
                log.warning("попытка %d: %s — %s", attempt, url, e)
                time.sleep(2 ** attempt)  # 2, 4, 8 секунд
                continue

            if self._is_captcha(resp):
                raise CaptchaError(f"капча на {url} — остановка")
            if resp.status_code == 404:
                raise FileNotFoundError(url)
            if resp.status_code in (429, 500, 502, 503, 504):
                log.warning("попытка %d: %s — HTTP %d", attempt, url, resp.status_code)
                time.sleep(2 ** attempt)
                continue

            resp.raise_for_status()
            return resp.text

        raise RuntimeError(f"не удалось скачать {url} за {self.config.retries} попытки")
