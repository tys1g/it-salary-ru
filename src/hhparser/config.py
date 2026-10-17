from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    base_url: str = "https://hh.ru"
    api_url: str = "https://api.hh.ru"
    # pause after request
    delay_min: float = 1.5
    delay_max: float = 3.5
    timeout: float = 20.0
    retries: int = 3
    user_agent: str = os.getenv(
        "HH_USER_AGENT", "it-salary-ru/0.1 (public vacancy research)"
    )
    data_dir: Path = Path("data")

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


CONFIG = Config()
