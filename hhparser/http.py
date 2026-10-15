"""Вежливый HTTP-клиент: паузы, повторы с отступом, остановка на капче."""

import logging
import random
import time

import requests

from . import config

log = logging.getLogger(__name__)


class BlockedError(RuntimeError):
    """Сайт показал капчу или запретил доступ. Дальше не идём."""


class PoliteClient:
    def __init__(self, delay: float = config.DELAY_SECONDS, jitter: float = config.JITTER_SECONDS):
        self.delay = delay
        self.jitter = jitter
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9",
        })

    def _wait(self) -> None:
        pause = self.delay + random.uniform(0, self.jitter)
        elapsed = time.monotonic() - self._last
        if elapsed < pause:
            time.sleep(pause - elapsed)
        self._last = time.monotonic()

    def get(self, url: str) -> requests.Response | None:
        """Возвращает ответ, None для 404/410, бросает BlockedError на капче/403."""
        for attempt in range(1, config.MAX_RETRIES + 1):
            self._wait()
            try:
                resp = self.session.get(url, timeout=config.TIMEOUT_SECONDS)
            except requests.RequestException as e:
                log.warning("сетевая ошибка %s (%s), попытка %d", url, e, attempt)
                time.sleep(2 ** attempt)
                continue

            if "captcha" in resp.url or resp.status_code == 403:
                # Не обходим защиту. Если она появилась, мы слишком быстрые.
                raise BlockedError(f"доступ ограничен ({resp.status_code}) на {url}")
            if resp.status_code in (404, 410):
                return None  # вакансию удалили, это нормально
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 10 * attempt
                log.warning("код %d на %s, ждём %d с", resp.status_code, url, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        log.error("не удалось скачать %s за %d попыток", url, config.MAX_RETRIES)
        return None
