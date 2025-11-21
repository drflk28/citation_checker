import requests
import time
import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlencode, quote
from app.config import APIConfig

@dataclass
class SearchResult:
    source: str
    title: Optional[str] = None
    authors: List[str] = None
    year: Optional[str] = None
    publisher: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    url: Optional[str] = None
    confidence: float = 0.0
    relevance_score: float = 0.0
    is_search_link: bool = False

class OnlineSearcher:
    def __init__(self, config: APIConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

        # Обновленный приоритет API
        self.api_priority = [
            'crossref',  # Научные статьи
            'open_library',  # Книги
            'arxiv',  # Научные препринты
            'google_books'  # Книги (если есть API key)
        ]

        self.session.headers.update({
            'User-Agent': 'AcademicCitationChecker/1.0',
            'Accept': 'application/json'
        })

    def _generate_search_queries(self, text: str) -> List[str]:
        """Улучшенная генерация запросов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        import re

        queries = []

        # Очищаем текст
        clean_text = re.sub(r'\[.*?\]|\(.*?\)|\/\/.*|:.*?[;,]', '', text)
        clean_text = re.sub(r'\s+', ' ', clean_text.strip())

        print(f"  Генерация запросов для: '{clean_text}'")

        # 1. Основной запрос: авторы + название
        main_query = self._create_main_query(clean_text)
        if main_query and len(main_query) > 3:
            print(f"  Основной запрос: '{main_query}'")
            queries.append(main_query)

        # 2. Запрос только с названием (если оно есть)
        title_only = self._extract_main_title_for_search(clean_text)  # ИСПРАВЛЕНО: используем правильный метод
        if title_only and len(title_only) > 5 and title_only != main_query:
            print(f"  Запрос по названию: '{title_only}'")
            queries.append(title_only)

            # Добавляем варианты с указанием типа
            if any(word in clean_text.lower() for word in ['учебник', 'пособие', 'учебное']):
                queries.append(f'"{title_only}" учебник')
                queries.append(f'"{title_only}" книга')

        # 3. Запрос для английских источников
        if any(word in clean_text.lower() for word in ['book', 'textbook', 'manual']):
            eng_words = re.findall(r'\b[a-zA-Z]{4,}\b', clean_text)
            if eng_words:
                eng_query = ' '.join(eng_words[:6])
                if eng_query and eng_query not in queries:
                    queries.append(eng_query)

        # Убираем дубликаты и пустые запросы
        unique_queries = []
        seen = set()
        for query in queries:
            if query and len(query) > 2 and query not in seen:
                seen.add(query)
                unique_queries.append(query)

        print(f"  Сгенерировано запросов: {unique_queries}")
        return unique_queries[:3]

    def search_publication(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Основной метод поиска публикации с улучшенной фильтрацией"""
        print(f"🔍 Поиск публикации: '{query}'")

        # Генерируем улучшенные запросы
        search_queries = self._generate_search_queries(query)

        if not search_queries:
            print("  ⚠ Не удалось сгенерировать поисковые запросы")
            return []

        all_results = []

        for search_query in search_queries:
            if len(all_results) >= max_results:
                break

            print(f"  Запрос: '{search_query}'")
            query_results = []

            for api_name in self.api_priority:
                if len(query_results) >= 3:
                    break

                # Пропускаем Google Books если нет API key
                if api_name == 'google_books' and not self.config.GOOGLE_BOOKS_API_KEY:
                    print(f"    ⚠ {api_name} пропущен (нет API key)")
                    continue

                try:
                    print(f"    Используем {api_name}...")
                    api_results = self._call_api(api_name, search_query)
                    if api_results:
                        # Фильтруем результаты по релевантности
                        relevant_results = [r for r in api_results if self._is_relevant_result(r, query)]
                        query_results.extend(relevant_results)

                        print(
                            f"    ✅ {api_name}: найдено {len(api_results)} результатов, {len(relevant_results)} релевантных")
                        time.sleep(0.3)
                    else:
                        print(f"    ❌ {api_name}: результатов нет")
                except Exception as e:
                    print(f"    ⚠ Ошибка в {api_name}: {e}")
                    continue

            all_results.extend(query_results)

        # Сортировка и дедупликация
        final_results = self._deduplicate_results(all_results)[:max_results]
        print(f"🎯 Итоговые результаты: {len(final_results)}")

        # Отладочная информация
        for i, result in enumerate(final_results):
            rel_status = "✅ Релевантный" if self._is_relevant_result(result, query) else "⚠ Не релевантный"
            print(f"      {rel_status} результат: '{result.title}' (уверенность: {result.confidence:.2f})")

        return final_results

    def _call_api(self, api_name: str, query: str) -> List[SearchResult]:
        """Вызов конкретного API"""
        if api_name == 'google_books':
            return self._search_google_books(query)
        elif api_name == 'crossref':
            return self._search_crossref(query)
        elif api_name == 'open_library':
            return self._search_open_library(query)
        elif api_name == 'arxiv':
            return self._search_arxiv(query)
        return []

    def _search_crossref(self, query: str) -> List[SearchResult]:
        """Поиск в CrossRef API для научных статей"""
        try:
            params = {
                'query': query,
                'rows': 5,
                'select': 'DOI,title,author,issued,publisher,container-title,volume,issue,page,type'
            }

            response = self.session.get(
                'https://api.crossref.org/works',
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_crossref_results(data)
            else:
                print(f"Crossref API status: {response.status_code}")

        except Exception as e:
            print(f"Crossref API error: {e}")

        return []

    def _parse_crossref_results(self, data: Dict) -> List[SearchResult]:
        """Парсинг результатов Crossref с улучшенной фильтрацией"""
        results = []

        for item in data['message'].get('items', [])[:5]:
            # Пропускаем нерелевантные типы
            item_type = item.get('type')
            if item_type not in ['journal-article', 'book', 'proceedings-article', 'book-chapter']:
                continue

            # Пропускаем статьи с короткими названиями (скорее всего это не книги)
            title = item.get('title', [''])[0] if item.get('title') else ''
            if len(title) < 20 and item_type != 'journal-article':
                continue

            authors = []
            for author in item.get('author', []):
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                if name:
                    authors.append(name)

            year = None
            if item.get('issued', {}).get('date-parts', [[]])[0]:
                year = str(item['issued']['date-parts'][0][0])

            # Вычисляем уверенность на основе типа и полноты данных
            confidence = self._calculate_crossref_confidence(item, title)

            result = SearchResult(
                source='crossref',
                title=title,
                authors=authors,
                year=year,
                publisher=item.get('publisher'),
                journal=item.get('container-title', [''])[0] if item.get('container-title') else None,
                volume=item.get('volume'),
                issue=item.get('issue'),
                pages=item.get('page'),
                doi=item.get('DOI'),
                url=f"https://doi.org/{item.get('DOI')}" if item.get('DOI') else None,
                confidence=confidence
            )
            results.append(result)

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def _calculate_crossref_confidence(self, item: Dict, title: str) -> float:
        """Вычисляет уверенность для Crossref результатов"""
        confidence = 0.0

        # Базовые баллы
        if item.get('DOI'):
            confidence += 0.3
        if title:
            confidence += 0.2
        if item.get('author'):
            confidence += 0.2
        if item.get('publisher'):
            confidence += 0.1
        if item.get('issued'):
            confidence += 0.1

        # Бонусы за тип контента
        item_type = item.get('type')
        if item_type == 'book':
            confidence += 0.3
        elif item_type == 'journal-article':
            confidence += 0.1

        # Штраф за короткие названия (возможно неполные данные)
        if len(title) < 30:
            confidence -= 0.2

        return max(0.1, min(confidence, 1.0))

    def _search_open_library(self, query: str) -> List[SearchResult]:
        """Поиск в Open Library API"""
        try:
            params = {
                'q': query,
                'limit': 5
            }

            response = self.session.get(
                'https://openlibrary.org/search.json',
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_open_library_results(data)

        except Exception as e:
            print(f"Open Library API error: {e}")

        return []

    def _parse_open_library_results(self, data: Dict) -> List[SearchResult]:
        """Парсинг результатов Open Library"""
        results = []

        for doc in data.get('docs', [])[:5]:
            authors = doc.get('author_name', [])
            year = doc.get('first_publish_year')

            result = SearchResult(
                source='open_library',
                title=doc.get('title'),
                authors=authors,
                year=str(year) if year else None,
                publisher=doc.get('publisher', [None])[0] if doc.get('publisher') else None,
                isbn=doc.get('isbn', [None])[0] if doc.get('isbn') else None,
                url=f"https://openlibrary.org{doc.get('key')}" if doc.get('key') else None,
                confidence=self._calculate_open_library_confidence(doc)
            )
            results.append(result)

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def _search_arxiv(self, query: str) -> List[SearchResult]:
        """Поиск в ArXiv API"""
        try:
            # Кодируем запрос для URL
            encoded_query = quote(query)
            url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results=5&sortBy=relevance"

            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                return self._parse_arxiv_results(response.text)
            else:
                print(f"ArXiv API status: {response.status_code}")

        except Exception as e:
            print(f"ArXiv API error: {e}")

        return []

    def _parse_arxiv_results(self, xml_content: str) -> List[SearchResult]:
        """Парсинг результатов ArXiv (XML)"""
        try:
            root = ET.fromstring(xml_content)
            results = []

            # ArXiv использует пространство имен
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            for entry in root.findall('atom:entry', ns):
                title_elem = entry.find('atom:title', ns)
                summary_elem = entry.find('atom:summary', ns)
                published_elem = entry.find('atom:published', ns)

                # Извлекаем авторов
                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)

                # Извлекаем год из даты публикации
                year = None
                if published_elem is not None and published_elem.text:
                    year = published_elem.text[:4]

                # ID ArXiv
                id_elem = entry.find('atom:id', ns)
                arxiv_id = None
                if id_elem is not None:
                    arxiv_id = id_elem.text.split('/')[-1]

                result = SearchResult(
                    source='arxiv',
                    title=title_elem.text if title_elem is not None else None,
                    authors=authors,
                    year=year,
                    url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
                    confidence=0.7
                )
                results.append(result)

            return results

        except Exception as e:
            print(f"ArXiv parsing error: {e}")
            return []

    def _calculate_open_library_confidence(self, doc: Dict) -> float:
        """Вычисляет уверенность для Open Library результатов"""
        confidence = 0.0
        if doc.get('title'):
            confidence += 0.3
        if doc.get('author_name'):
            confidence += 0.3
        if doc.get('first_publish_year'):
            confidence += 0.2
        if doc.get('publisher'):
            confidence += 0.2
        return min(confidence, 1.0)

    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Удаляет дубликаты на основе DOI, ISBN или заголовка"""
        seen = set()
        unique_results = []

        for result in results:
            key = None
            if result.doi:
                key = f"doi:{result.doi.lower()}"
            elif result.isbn:
                key = f"isbn:{result.isbn}"
            elif result.title:
                # Нормализуем заголовок для сравнения
                normalized_title = re.sub(r'[^\w]', '', result.title.lower()) if result.title else ""
                key = f"title:{normalized_title}"

            if key and key not in seen:
                seen.add(key)
                unique_results.append(result)

        return sorted(unique_results, key=lambda x: x.confidence, reverse=True)

    def _search_google_books(self, query: str) -> List[SearchResult]:
        """Поиск в Google Books API"""
        try:
            if not self.config.GOOGLE_BOOKS_API_KEY:
                print("⚠ Google Books API key не настроен")
                return []

            params = {
                'q': query,
                'maxResults': 5,
                'key': self.config.GOOGLE_BOOKS_API_KEY
            }

            response = self.session.get(
                'https://www.googleapis.com/books/v1/volumes',
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_google_books_results(data)
            else:
                print(f"Google Books API status: {response.status_code}")

        except Exception as e:
            print(f"Google Books API error: {e}")

        return []

    def _parse_google_books_results(self, data: Dict) -> List[SearchResult]:
        """Парсинг результатов Google Books"""
        results = []

        for item in data.get('items', [])[:5]:
            volume_info = item.get('volumeInfo', {})

            # Вычисляем уверенность на основе полноты данных
            confidence = self._calculate_confidence(volume_info)

            result = SearchResult(
                source='google_books',
                title=volume_info.get('title'),
                authors=volume_info.get('authors', []),
                year=self._extract_year_from_date(volume_info.get('publishedDate')),
                publisher=volume_info.get('publisher'),
                isbn=self._extract_isbn(volume_info.get('industryIdentifiers', [])),
                url=volume_info.get('infoLink'),
                confidence=confidence
            )
            results.append(result)

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def _calculate_confidence(self, metadata: Dict) -> float:
        """Вычисляет уверенность в результате на основе полноты данных"""
        confidence = 0.0
        if metadata.get('title'):
            confidence += 0.3
        if metadata.get('authors'):
            confidence += 0.3
        if metadata.get('publishedDate'):
            confidence += 0.2
        if metadata.get('publisher') or metadata.get('journal'):
            confidence += 0.2
        return min(confidence, 1.0)

    def _extract_year_from_date(self, date_str: str) -> Optional[str]:
        """Извлекает год из строки даты"""
        if not date_str:
            return None
        import re
        match = re.search(r'(\d{4})', date_str)
        return match.group(1) if match else None

    def _extract_isbn(self, identifiers: List[Dict]) -> Optional[str]:
        """Извлекает ISBN из идентификаторов"""
        for id_obj in identifiers:
            if id_obj.get('type') in ['ISBN_13', 'ISBN_10']:
                return id_obj.get('identifier')
        return None

    def _is_relevant_result(self, result: SearchResult, original_text: str) -> bool:
        """Улучшенная проверка релевантности результата - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        if not result.title:
            return False

        original_lower = original_text.lower()
        result_title = result.title.lower()

        # Извлекаем ключевые компоненты
        original_components = self._extract_components(original_text)
        result_components = self._extract_components(result_title)

        # Проверяем известные классические произведения
        if self._check_known_works(original_lower, result_title):
            return True

        # Проверяем совпадение ключевых слов в названии
        keyword_matches = len(set(original_components['keywords']) & set(result_components['keywords']))

        # Проверяем совпадение авторов - ИСПРАВЛЕНО: используем правильный метод
        author_match = self._check_authors_match(original_lower, result.authors)

        # Проверяем совпадение по году
        year_match = (original_components.get('year') and result_components.get('year') and
                      original_components['year'] == result_components['year'])

        # Условия для признания релевантным:
        # 1. Совпадение авторов + хотя бы 1 ключевое слово
        # 2. 3+ совпадающих ключевых слова
        # 3. 2+ ключевых слова + совпадение года
        if (author_match and keyword_matches >= 1) or \
                (keyword_matches >= 3) or \
                (keyword_matches >= 2 and year_match):
            return True

        # Для книг: проверяем наличие ключевых слов в названии
        book_keywords = ['учебник', 'пособие', 'book', 'textbook', 'manual']
        if any(keyword in result_title for keyword in book_keywords) and keyword_matches >= 2:
            return True

        return False

    def _extract_components(self, text: str) -> Dict:
        """Извлекает ключевые компоненты из текста - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        import re

        components = {
            'keywords': [],
            'year': None,
            'authors': []
        }

        # Извлекаем год
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            components['year'] = year_match.group(0)

        # Извлекаем ключевые слова (слова длиной > 3 символов)
        words = re.findall(r'\b\w{4,}\b', text.lower())

        # Список стоп-слов для русского и английского
        stop_words = {
            'русские': {'издание', 'учебник', 'пособие', 'автор', 'год', 'изд', 'москва',
                        'санкт', 'петербург', 'владимир', 'челябинск', 'издательство',
                        'учебное', 'практикум', 'вузов', 'университет', 'институт'},
            'english': {'edition', 'textbook', 'manual', 'author', 'year', 'publisher',
                        'moscow', 'petersburg', 'university', 'institute', 'press'}
        }

        # Фильтруем стоп-слова
        filtered_words = []
        for word in words:
            if (word not in stop_words['русские'] and
                    word not in stop_words['english'] and
                    not word.isdigit()):
                filtered_words.append(word)

        components['keywords'] = filtered_words

        # Извлекаем фамилии авторов - ИСПРАВЛЕНО: используем правильный метод
        components['authors'] = self._extract_authors_for_search(text)

        return components

    def _check_known_works(self, original_text: str, result_title: str) -> bool:
        """Проверяет известные классические произведения"""
        known_works = {
            'толстой': ['война и мир', 'war and peace'],
            'orwell': ['1984', 'nineteen eighty-four'],
            'кнудсен': ['машинное обучение', 'machine learning'],
            'грачев': ['бизнес-планирование', 'business planning'],
            'лопарева': ['бизнес-планирование', 'business planning'],
            'новосад': ['бизнес-планирование', 'business planning'],
            'уланов': ['технологическое предпринимательство', 'technological entrepreneurship'],
            'каменнова': ['моделирование бизнес-процессов', 'business process modeling'],
            'иванов': ['методы анализа данных', 'data analysis methods'],
            'петров': ['методы анализа данных', 'data analysis methods']
        }

        for author, works in known_works.items():
            if author in original_text:
                for work in works:
                    if work in result_title:
                        return True
        return False

    def _check_authors_match(self, original_text: str, result_authors: List[str]) -> bool:
        """Проверяет совпадение авторов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        if not result_authors:
            return False

        # Извлекаем фамилии из оригинального текста - ИСПРАВЛЕНО: используем правильный метод
        original_authors = self._extract_authors_for_search(original_text)

        for original_author in original_authors:
            for result_author in result_authors:
                # Простая проверка по фамилии
                if original_author.lower() in result_author.lower():
                    return True
        return False

    def _extract_authors_for_search(self, text: str) -> List[str]:
        """Извлекает авторов для поискового запроса - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        import re

        authors = []

        # Паттерны для извлечения авторов из начала строки
        patterns = [
            # Русские авторы: "Фамилия И. О." или "Фамилия И.О."
            r'^([А-Я][а-я]+(?:\s+[А-Я]\.\s*[А-Я]\.)?)',
            # Русские авторы: "Фамилия Имя"
            r'^([А-Я][а-я]+\s+[А-Я][а-я]+)',
            # Английские авторы: "Lastname F." или "Lastname F.I."
            r'^([A-Z][a-z]+(?:\s+[A-Z]\.(?:\s*[A-Z]\.)?)?)',
            # Английские авторы: "Firstname Lastname"
            r'^([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                author_text = match.group(1).strip()
                # Разбиваем на отдельных авторов по запятым или "и"
                author_parts = re.split(r'[,и]|\s+и\s+', author_text)

                for part in author_parts:
                    part = part.strip()
                    if part:
                        # Берем только фамилию (первое слово)
                        surname = part.split()[0]
                        if len(surname) > 2 and surname not in authors:
                            authors.append(surname)

                # Ограничиваем количество авторов
                if len(authors) >= 2:
                    break

        return authors[:2]  # Не более 2 авторов

    def _generate_search_queries(self, text: str) -> List[str]:
        """Улучшенная генерация запросов с фокусировкой на книги"""
        import re

        queries = []

        # Очищаем текст
        clean_text = re.sub(r'\[.*?\]|\(.*?\)|\/\/.*|:.*?[;,]', '', text)

        # 1. Основной запрос: авторы + краткое название
        main_query = self._create_main_query(clean_text)
        if main_query:
            queries.append(main_query)

        # 2. Запрос с указанием типа издания
        if any(word in clean_text.lower() for word in ['учебник', 'пособие', 'учебное']):
            title_only = self._extract_main_title_for_search(clean_text)
            if title_only:
                queries.append(f'"{title_only}" учебник')
                queries.append(f'"{title_only}" книга')

        # 3. Запрос для международных источников
        if any(word in clean_text.lower() for word in ['book', 'textbook', 'manual']):
            eng_query = self._create_english_query(clean_text)
            if eng_query:
                queries.append(eng_query)

        # Убираем дубликаты и ограничиваем количество
        unique_queries = []
        seen = set()
        for query in queries:
            if query and query not in seen:
                seen.add(query)
                unique_queries.append(query)

        return unique_queries[:3]

    def _create_main_query(self, text: str) -> str:
        """Создает основной поисковый запрос - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        import re

        # Очищаем текст от лишних пробелов
        clean_text = re.sub(r'\s+', ' ', text.strip())

        # Извлекаем авторов (первые 1-2 фамилии) - исправленный метод
        authors = self._extract_authors_for_search(clean_text)

        # Извлекаем основное название (исправленный метод)
        title = self._extract_main_title_for_search(clean_text)

        # Формируем запрос
        if authors and title:
            # Объединяем авторов и название
            return f"{' '.join(authors)} {title}"
        elif authors:
            # Только авторы
            return ' '.join(authors)
        elif title:
            # Только название
            return title
        else:
            # Резервный вариант - первые несколько слов
            words = clean_text.split()[:5]
            return ' '.join(words)

    def _remove_authors_from_start(self, text: str) -> str:
        """Убирает блок авторов из начала строки"""
        import re

        # Паттерны для определения конца блока авторов
        patterns = [
            r'^[^.]*?\.\s*',  # Заканчивается точкой
            r'^[^,]*?,\s*',  # Заканчивается запятой (для английского формата)
            r'^[^/]*?/\s*',  # Заканчивается слешем
        ]

        for pattern in patterns:
            match = re.match(pattern, text)
            if match:
                return text[len(match.group(0)):]

        return text

    def _extract_main_title_for_search(self, text: str) -> str:
        """Извлекает основное название для поиска - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        import re

        # Убираем авторов из начала
        text_without_authors = self._remove_authors_from_start(text)

        # Ищем основное название (до двоеточия, точки или года)
        title_match = re.search(r'^([^:.]*?)(?=:\s*[А-ЯA-Z]|\.\s*[А-ЯA-Z]|\s+\d{4}|\s*$)', text_without_authors)

        if title_match:
            title = title_match.group(1).strip()
            # Очищаем от лишних слов - УБРАН ВЫЗОВ _extract_authors_from_text
            title = self._clean_title(title)
            return title

        return ""

    def _clean_title(self, title: str) -> str:
        """Очищает название от лишних слов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        import re

        # Убираем лишние пробелы
        title = re.sub(r'\s+', ' ', title.strip())

        # Убираем короткие слова и мусор в начале
        words = title.split()
        cleaned_words = []

        for word in words:
            # Пропускаем слишком короткие слова и инициалы
            if len(word) > 2 and not re.match(r'^[А-ЯA-Z]\.$', word):
                cleaned_words.append(word)

        return ' '.join(cleaned_words)

    def _extract_main_title(self, text: str) -> str:
        """Извлекает основное название из библиографической записи"""
        import re

        # Убираем техническую информацию в начале
        clean_text = re.sub(r'^[^А-ЯA-Z]*', '', text)

        # Ищем основное название (до двоеточия или точки)
        title_match = re.search(r'^([^:.]*?)(?=:|\.|\s*[А-Я]\.\s*[А-Я]\.)', clean_text)
        if title_match:
            title = title_match.group(1).strip()
            # Убираем авторов из начала названия
            authors = self._extract_authors_for_search(title)
            for author in authors:
                title = title.replace(author, '').strip()
            return title

        return ""

    def _create_english_query(self, text: str) -> str:
        """Создает запрос для английских источников"""
        import re

        # Извлекаем основные слова для английского запроса
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text)
        if words:
            return ' '.join(words[:5])

        return ""

    def _is_likely_book(self, result: SearchResult, original_text: str) -> bool:
        """Проверяет, похож ли результат на книгу"""
        book_indicators = [
            result.source in ['google_books', 'open_library'],
            result.isbn is not None,
            'учебник' in original_text.lower() and 'учеб' in (result.title or '').lower(),
            'book' in (result.title or '').lower() if original_text.lower().count('book') > 0 else False
        ]
        return any(book_indicators)

    def _filter_best_result(self, results: List[SearchResult], original_text: str) -> Optional[SearchResult]:
        """Улучшенная фильтрация с приоритетом книг"""

        # Сначала ищем книги
        books = [r for r in results if self._is_likely_book(r, original_text)]
        if books:
            return max(books, key=lambda x: x.confidence)

        # Затем ищем учебники/пособия в статьях
        textbooks = [r for r in results if 'учеб' in original_text.lower() and self._is_likely_textbook(r)]
        if textbooks:
            return max(textbooks, key=lambda x: x.confidence)

        # Иначе берем самый уверенный результат
        return max(results, key=lambda x: x.confidence) if results else None

    def _is_likely_textbook(self, result: SearchResult) -> bool:
        """Проверяет, похож ли результат на учебник"""
        if not result.title:
            return False
        title_lower = result.title.lower()
        textbook_indicators = [
            'учебник' in title_lower,
            'textbook' in title_lower,
            'пособие' in title_lower,
            'manual' in title_lower
        ]
        return any(textbook_indicators)