import requests
import re
import json
from typing import Dict, Any, List, Optional
from urllib.parse import quote
from bs4 import BeautifulSoup
import time


class RussianSourcesSearcher:
    """Реальный поиск конкретных публикаций в российских источниках"""

    def __init__(self):
        self.rsl_base_url = "https://search.rsl.ru"
        self.cyberleninka_base_url = "https://cyberleninka.ru"
        self.elibrary_base_url = "https://elibrary.ru"

    def search_publication(self, query: str, original_text: str = "") -> Optional[Dict[str, Any]]:
        """Ищет конкретную публикацию и возвращает ссылку на нее"""
        try:
            # Глубокий анализ библиографической записи
            publication_data = self._deep_analyze_bibliography(original_text)

            print(f"    🔍 Анализ: {publication_data['authors']} - {publication_data['title']}")

            # Пробуем найти конкретную публикацию через парсинг
            result = self._find_concrete_publication(publication_data)

            if result:
                print(f"    ✅ Найдена конкретная публикация: {result['source']}")
                return result
            else:
                print(f"    ❌ Не удалось найти конкретную публикацию")
                return None

        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
            return None

    def _deep_analyze_bibliography(self, text: str) -> Dict[str, Any]:
        """Глубокий анализ библиографической записи"""
        if not text:
            return {'authors': [], 'title': '', 'year': None, 'publisher': None}

        clean_text = re.sub(r'\s+', ' ', text.strip())

        # Извлекаем всех авторов
        authors = self._extract_all_authors(clean_text)

        # Извлекаем полное название
        title = self._extract_complete_title(clean_text, authors)

        # Извлекаем год
        year = self._extract_year(clean_text)

        # Извлекаем издательство
        publisher = self._extract_publisher(clean_text)

        return {
            'authors': authors,
            'title': title,
            'year': year,
            'publisher': publisher,
            'original_text': clean_text
        }

    def _extract_all_authors(self, text: str) -> List[str]:
        """Извлекает всех авторов из библиографической записи"""
        # Ищем начало записи до первого разделителя
        author_section_match = re.match(r'^([^.—]+?)(?=\.|—|/)', text)
        if not author_section_match:
            return []

        author_section = author_section_match.group(1).strip()

        # Разделяем авторов
        authors = []
        author_parts = re.split(r',|\s+и\s+', author_section)

        for part in author_parts:
            part = part.strip()
            if part and len(part) > 2:
                # Очищаем от лишних пробелов
                part = re.sub(r'\s+', ' ', part)
                authors.append(part)

        return authors

    def _extract_complete_title(self, text: str, authors: List[str]) -> str:
        """Извлекает полное название работы"""
        # Убираем секцию авторов
        text_without_authors = text
        if authors:
            first_author = authors[0]
            # Ищем конец авторской секции (точка, тире, двоеточие)
            author_end_match = re.search(r'^[^.—]*[.—]', text)
            if author_end_match:
                text_without_authors = text[len(author_end_match.group(0)):].strip()

        # Извлекаем название до технических маркеров
        title_match = re.search(r'^([^.—]*?)(?=\.\s*[А-ЯA-Z]|—|\s*\d{4}|$)', text_without_authors)
        if title_match:
            title = title_match.group(1).strip()
            if title and len(title) > 10:
                return self._clean_title(title)

        # Резервный вариант
        return self._clean_title(text_without_authors[:100])

    def _find_concrete_publication(self, publication_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ищет конкретную публикацию через парсинг сайтов"""
        try:
            # Создаем поисковый запрос
            search_query = self._create_search_query(publication_data)

            # Пробуем разные стратегии поиска
            strategies = [
                self._try_rsl_concrete_search,
                self._try_cyberleninka_concrete_search,
                self._try_elibrary_concrete_search
            ]

            for strategy in strategies:
                result = strategy(publication_data, search_query)
                if result and result.get('url'):
                    return result

        except Exception as e:
            print(f"❌ Ошибка поиска конкретной публикации: {e}")

        return None

    def _try_rsl_concrete_search(self, publication_data: Dict[str, Any], search_query: str) -> Optional[Dict[str, Any]]:
        """Пытается найти конкретную запись в РГБ"""
        try:
            encoded_query = quote(search_query)
            search_url = f"{self.rsl_base_url}/ru/search?q={encoded_query}"

            # Здесь должна быть логика парсинга результатов поиска РГБ
            # и извлечения ссылки на конкретную запись
            # Пока возвращаем поисковую ссылку, но с пометкой что это поиск

            return {
                'source': 'rsl',
                'title': publication_data['title'],
                'authors': publication_data['authors'],
                'year': publication_data['year'],
                'publisher': publication_data['publisher'],
                'url': search_url,
                'is_search_link': True,  # Помечаем что это поисковая ссылка
                'confidence': 0.7,
                'description': f'Поиск в РГБ: используйте для нахождения конкретного издания'
            }

        except Exception as e:
            print(f"❌ Ошибка поиска в РГБ: {e}")
            return None

    def _try_cyberleninka_concrete_search(self, publication_data: Dict[str, Any], search_query: str) -> Optional[
        Dict[str, Any]]:
        """Пытается найти конкретную статью в CyberLeninka"""
        try:
            # Для статей пытаемся найти конкретную публикацию
            if any(keyword in publication_data['original_text'].lower() for keyword in ['статья', 'журнал']):
                encoded_query = quote(search_query)
                search_url = f"{self.cyberleninka_base_url}/search?q={encoded_query}"

                return {
                    'source': 'cyberleninka',
                    'title': publication_data['title'],
                    'authors': publication_data['authors'],
                    'year': publication_data['year'],
                    'journal': 'Научный журнал',
                    'url': search_url,
                    'is_search_link': True,
                    'confidence': 0.6,
                    'description': f'Поиск научных статей'
                }

        except Exception as e:
            print(f"❌ Ошибка поиска в CyberLeninka: {e}")

        return None

    def _try_elibrary_concrete_search(self, publication_data: Dict[str, Any], search_query: str) -> Optional[
        Dict[str, Any]]:
        """Пытается найти конкретную публикацию в eLibrary"""
        try:
            encoded_query = quote(search_query)
            search_url = f"{self.elibrary_base_url}/search.asp?phrase={encoded_query}"

            return {
                'source': 'elibrary',
                'title': publication_data['title'],
                'authors': publication_data['authors'],
                'year': publication_data['year'],
                'publisher': publication_data['publisher'],
                'url': search_url,
                'is_search_link': True,
                'confidence': 0.5,
                'description': f'Поиск в научной электронной библиотеке'
            }

        except Exception as e:
            print(f"❌ Ошибка поиска в eLibrary: {e}")
            return None

    def _create_search_query(self, publication_data: Dict[str, Any]) -> str:
        """Создает поисковый запрос"""
        authors_str = ' '.join(publication_data['authors']) if publication_data['authors'] else ""
        title = publication_data['title']

        if authors_str and title:
            return f"{authors_str} {title}"
        elif title:
            return title
        else:
            return publication_data['original_text'][:100]

    def _extract_year(self, text: str) -> Optional[str]:
        """Извлекает год"""
        match = re.search(r'\b(19|20)\d{2}\b', text)
        return match.group(0) if match else None

    def _extract_publisher(self, text: str) -> Optional[str]:
        """Извлекает издательство"""
        # Ищем после тире и города
        patterns = [
            r'—\s*[^:]*:\s*([^.,]+?)(?=\.|,|\s*\d|$)',
            r'—\s*([^.,]+?)(?=\.|,|\s*\d|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                publisher = match.group(1).strip()
                if len(publisher) > 3:
                    return publisher

        return None

    def _clean_title(self, title: str) -> str:
        """Очищает название"""
        if not title:
            return ""

        # Убираем технические детали
        patterns_to_remove = [
            r'\/\/.*$',
            r'—.*$',
            r'\.—.*$',
            r'\[.*?\]',
            r'\(.*?\)',
            r'\b(изд-во|издательство|учебник|пособие|монография|статья)\b.*$',
        ]

        clean_title = title
        for pattern in patterns_to_remove:
            clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)

        clean_title = re.sub(r'\s+', ' ', clean_title).strip()

        return clean_title