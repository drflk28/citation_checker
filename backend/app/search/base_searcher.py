from abc import ABC, abstractmethod
from typing import List


class BaseSearcher(ABC):
    """Абстрактный базовый класс для поисковых сервисов"""

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List['SearchMatch']:
        pass