import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class APIConfig:
    # API Keys (опциональные)
    GOOGLE_BOOKS_API_KEY = os.getenv('GOOGLE_BOOKS_API_KEY', '')

    # Настройки запросов
    REQUEST_TIMEOUT = 10
    RATE_LIMIT_DELAY = 0.5

    # Приоритет API (обновленный)
    API_PRIORITY = ['crossref', 'open_library', 'arxiv']