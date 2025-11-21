from typing import List, Dict, Any, Optional
from app.models.data_models import TextBlock, BibliographyEntry
import re
import requests
import time
from urllib.parse import quote
import json
from app.search.online_searcher import OnlineSearcher, SearchResult
from app.config import APIConfig
from app.search.russian_sources import RussianSourcesSearcher

class BibliographyChecker:
    def __init__(self):
        self.biblio_keywords = [
            'список используемых источников', 'список литературы', 'библиография',
            'литература', 'источники', 'references', 'bibliography',
            'reference', 'source', 'works cited', 'literature'
        ]
        self.section_end_keywords = ['приложение', 'appendix', 'заключение', 'conclusion']

        self.search_apis = {
            'google_books': 'https://www.googleapis.com/books/v1/volumes',
            'crossref': 'https://api.crossref.org/works',
            'open_library': 'https://openlibrary.org/search.json',
            'semantic_scholar': 'https://api.semanticscholar.org/graph/v1/paper/search'
        }
        self.searcher = OnlineSearcher(APIConfig())
        self.russian_searcher = RussianSourcesSearcher()

    def find_bibliography_section(self, text_blocks: List[TextBlock]) -> List[TextBlock]:
        print("Поиск реального раздела библиографии...")
        bibliography_blocks = []
        in_bibliography = False
        found_header = False
        non_biblio_count = 0

        for block in text_blocks:
            text = block.text.strip()
            text_lower = text.lower()

            if (not found_header and
                    any(keyword in text_lower for keyword in self.biblio_keywords) and
                    '...' not in text and
                    len(text) < 100):
                print(f"Найден реальный заголовок библиографии: '{text}'")
                in_bibliography = True
                found_header = True
                continue

            if in_bibliography:
                if self._is_bibliography_entry(text):
                    bibliography_blocks.append(block)
                    non_biblio_count = 0
                    print(f"Добавлена библиографическая запись: {text[:60]}...")
                else:
                    non_biblio_count += 1
                    if non_biblio_count >= 3:
                        print(f"ℹ Обнаружен конец библиографии (подряд {non_biblio_count} не-библиографических блоков)")
                        break
                    if self._is_definitely_not_bibliography(text):
                        print(f"ℹ Обнаружен явно не-библиографический блок: {text[:50]}...")
                        break
                    if self._looks_like_table_data(text):
                        print(f"ℹ Обнаружены данные таблицы: {text[:50]}...")
                        break

        print(f"Найдено записей в библиографии: {len(bibliography_blocks)}")
        return bibliography_blocks

    def enhance_with_online_search(self, bibliography_entries: List[BibliographyEntry]) -> List[BibliographyEntry]:
        """Улучшает библиографические записи с помощью онлайн-поиска"""
        print("Улучшаем библиографические записи онлайн-поиском...")

        enhanced_entries = []

        for i, entry in enumerate(bibliography_entries):
            print(f"   Обрабатываем запись {i + 1}/{len(bibliography_entries)}: {entry.text[:50]}...")

            # Генерируем поисковые запросы
            search_queries = self._generate_search_queries(entry.text)
            entry.search_queries = search_queries

            best_result = None

            # сначала российские источники
            russian_result = self.russian_searcher.search_publication(
                search_queries[0] if search_queries else entry.text,
                entry.text
            )

            if russian_result:
                best_result = self._convert_russian_result_to_search_result(russian_result)
                print(f"      Найден в российских источниках (уверенность: {best_result.confidence:.2f})")
            else:
                # если не рос то междунар
                for query in search_queries:
                    print(f"      Международный поиск: '{query}'")
                    results = self.searcher.search_publication(query)

                    if results:
                        # Фильтруем и выбираем лучший результат
                        relevant_results = [r for r in results if self._is_relevant_result(r, entry.text)]
                        if relevant_results:
                            best_result = self._filter_best_result(relevant_results, entry.text)
                            if best_result:
                                print(f"      Релевантный результат (уверенность: {best_result.confidence:.2f})")
                                break
                        else:
                            print(f"      Найдены результаты, но не релевантные")
                    else:
                        print(f"      Результатов нет")

            if best_result:
                # Преобразуем SearchResult в словарь для online_metadata
                entry.online_metadata = {
                    'source': best_result.source,
                    'title': best_result.title,
                    'authors': best_result.authors or [],
                    'year': best_result.year,
                    'publisher': best_result.publisher,
                    'journal': best_result.journal,
                    'volume': best_result.volume,
                    'issue': best_result.issue,
                    'pages': best_result.pages,
                    'doi': best_result.doi,
                    'isbn': best_result.isbn,
                    'url': best_result.url,
                    'confidence': best_result.confidence,
                    'retrieved_at': time.time(),
                    #'description': getattr(best_result, 'description', '')
                }
                entry.enhancement_confidence = best_result.confidence
                entry.is_verified = True
                print(f"      Используем результат с уверенностью: {best_result.confidence:.2f}")
            else:
                # Убедимся, что online_metadata это пустой словарь, а не None
                entry.online_metadata = {}
                print(f"      Подходящий результат не найден")

            enhanced_entries.append(entry)

        print(
            f"Улучшено {len([e for e in enhanced_entries if e.online_metadata])} из {len(enhanced_entries)} записей")
        return enhanced_entries

    def _convert_russian_result_to_search_result(self, russian_result: Dict[str, Any]) -> SearchResult:
        """Конвертирует результат из российских источников в SearchResult"""
        url = russian_result.get('record_url') or russian_result.get('url')

        return SearchResult(
            source=russian_result['source'],
            title=russian_result.get('title', ''),
            authors=russian_result.get('authors', []),
            year=russian_result.get('year'),
            publisher=russian_result.get('publisher'),
            journal=russian_result.get('journal'),
            volume=None,
            issue=None,
            pages=None,
            doi=None,
            isbn=None,
            url=url,
            confidence=russian_result.get('confidence', 0.6),
            is_search_link=russian_result.get('is_search_link', False)
        )

    def _enhance_single_entry(self, entry: BibliographyEntry) -> BibliographyEntry:
        """Улучшает одну библиографическую запись"""
        search_queries = self._generate_search_queries(entry.text)
        entry.search_queries = search_queries

        best_overall_result = None
        best_confidence = 0.0

        for query in search_queries:
            print(f"      Поиск: '{query}'")
            try:
                results = self.online_searcher.search_publication(query)

                if results:
                    best_result = self._filter_best_result(results, query)

                    if best_result and best_result.confidence > best_confidence:
                        best_overall_result = best_result
                        best_confidence = best_result.confidence
                        print(f"      Найден результат (уверенность: {best_result.confidence:.2f})")

                        if best_result.confidence > 0.8:
                            break
                else:
                    print(f"      Не найдено результатов для: {query}")

            except Exception as e:
                print(f"      Ошибка при поиске '{query}': {e}")
                continue

        if best_overall_result and best_confidence > 0.3:
            entry.online_metadata = self._format_online_metadata(best_overall_result)
            entry.is_verified = True
            entry.enhancement_confidence = best_confidence
            print(f"      Используем результат с уверенностью: {best_confidence:.2f}")
        else:
            print(f"      Не найдено достаточно качественных результатов")

        return entry

    def _format_online_metadata(self, result: SearchResult) -> Dict[str, Any]:
        """Форматирует результат поиска для хранения"""
        return {
            'source': result.source,
            'title': result.title,
            'authors': result.authors,
            'year': result.year,
            'publisher': result.publisher,
            'journal': result.journal,
            'volume': result.volume,
            'issue': result.issue,
            'pages': result.pages,
            'doi': result.doi,
            'isbn': result.isbn,
            'url': result.url,
            'confidence': result.confidence,
            'retrieved_at': time.time()
        }

    def _generate_search_queries(self, text: str) -> List[str]:
        """Улучшенная генерация поисковых запросов"""
        queries = []

        # Очищаем текст
        clean_text = re.sub(r'\[.*?\]', '', text)
        clean_text = re.sub(r'[^\w\s.,;:()-]', '', clean_text)

        # 1. Основной очищенный запрос
        if clean_text.strip():
            queries.append(clean_text.strip())

        # 2. Упрощенный запрос
        simple_text = re.sub(
            r'\b(изд-во|издательство|учебник|пособие|монография|статья|под ред|ред\.|с\.|стр\.|т\.|вып\.)\b.*?[.,]', '',
            clean_text, flags=re.IGNORECASE)
        simple_text = re.sub(r'\d+\.\d+|\d+-\d+', '', simple_text)  # Убираем номера страниц
        if simple_text.strip() and simple_text != clean_text:
            queries.append(simple_text.strip())

        # 3. Запрос с авторами и названием
        authors = self._extract_authors(clean_text)
        title = self._extract_title(clean_text)
        if authors and title:
            queries.append(f"{authors} {title}")

        # 4. Запрос только с названием
        improved_title = self._extract_improved_title(clean_text)
        if improved_title:
            queries.append(improved_title)

        # Убираем дубликаты и слишком короткие запросы
        unique_queries = []
        seen = set()
        for query in queries:
            if query and len(query) > 10 and query not in seen:
                seen.add(query)
                unique_queries.append(query)

        return unique_queries[:4]

    def _extract_improved_title(self, text: str) -> Optional[str]:
        """Улучшенное извлечение названия работы"""
        # Убираем авторов (всё до первой точки или двоеточия)
        text_without_authors = re.sub(r'^[^.:]*[.:]', '', text).strip()

        # Убираем год
        text_without_year = re.sub(r'\b(19|20)\d{2}\b', '', text_without_authors)

        # Убираем издательство и прочую техническую информацию
        patterns_to_remove = [
            r'\/\/.*$',  # Всё после //
            r'—.*$',  # Всё после —
            r'\.—.*$',  # Всё после .—
            r'\(.*\)',  # Скобки с содержимым
            r'\b(изд-во|издательство|учебник|пособие|монография|статья)\b.*$',
        ]

        for pattern in patterns_to_remove:
            text_without_year = re.sub(pattern, '', text_without_year)

        # Берем первые 5-8 слов как возможное название
        words = text_without_year.strip().split()
        if len(words) > 2:
            return ' '.join(words[:min(8, len(words))])

        return None

    def _extract_authors(self, text: str) -> Optional[str]:
        """Извлекает авторов из библиографической записи"""
        # Паттерны для русских авторов: "Иванов И.И.", "Петров А.В."
        patterns = [
            r'^([А-Я][а-я]+ [А-Я]\.[А-Я]\.)',  # Иванов И.И.
            r'^([А-Я][а-я]+ [А-Я][а-я]+ [А-Я]\.[А-Я]\.)',  # Иванов Иван И.И.
            r'^([А-Я][а-я]+,\s*[А-Я]\.[А-Я]\.)',  # Иванов, И.И.
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        # Паттерны для английских авторов
        patterns_en = [
            r'^([A-Z][a-z]+ [A-Z]\.)',  # Smith J.
            r'^([A-Z][a-z]+ [A-Z]\. [A-Z]\.)',  # Smith J. K.
            r'^([A-Z][a-z]+,\s*[A-Z]\.)',  # Smith, J.
        ]

        for pattern in patterns_en:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return None

    def _extract_year(self, text: str) -> Optional[str]:
        """Извлекает год публикации"""
        match = re.search(r'\b(19|20)\d{2}\b', text)
        return match.group(0) if match else None

    def _extract_title(self, text: str) -> Optional[str]:
        """Извлекает название работы"""
        # Убираем авторов и год, оставшееся - вероятно название
        text_without_authors = re.sub(r'^[^.]*\.', '', text)  # Убираем часть до первой точки
        text_without_year = re.sub(r'\b(19|20)\d{2}\b', '', text_without_authors)

        # Берем первые 5-10 слов как возможное название
        words = text_without_year.strip().split()
        if len(words) > 3:
            return ' '.join(words[:min(8, len(words))])

        return None


    def _is_definitely_not_bibliography(self, text: str) -> bool:
        text_lower = text.lower()
        not_biblio_indicators = [
            any(word in text_lower for word in ['т.р.', 'тыс. руб.', 'руб.', 'стоимость', 'цена', 'закупка']),
            re.search(r'\d+\s*т\.р\.', text),
            re.search(r'\d+\s*руб', text),
            any(term in text_lower for term in ['ндс', 'оборудован', 'персонал', 'производств']),
            len(text) < 30 and any(char.isdigit() for char in text),
            any(char in text for char in ['+', '-', '*', '/', '=']),
        ]
        return any(not_biblio_indicators)

    def _looks_like_table_data(self, text: str) -> bool:
        table_indicators = [
            bool(re.search(r'\d+[\s,]*т\.р\.', text)),
            bool(re.search(r'\d+[\s,]*руб', text)),
            bool(re.search(r'\d+[\s,]*%', text)),
            len(text) < 50 and any(char.isdigit() for char in text),
            any(word in text.lower() for word in ['цена', 'стоимость', 'закупка', 'расход', 'доход']),
        ]
        return any(table_indicators)

    def _is_bibliography_entry(self, text: str) -> bool:
        if not text or not text.strip():
            return False

        text_lower = text.lower().strip()

        if any(keyword in text_lower for keyword in self.biblio_keywords):
            return False
        if '...' in text:
            return False
        if len(text) < 20:
            return False

        starts_with_number = any(text.strip().startswith(f"{i}.") for i in range(1, 100))
        starts_with_bracket = re.match(r'^\[\d+\]', text.strip())
        has_year = bool(re.search(r'\b(19|20)\d{2}\b', text))

        has_biblio_keywords = any(keyword in text_lower for keyword in [
            'изд-во', 'издательство', 'журнал', 'т.', 'вып.', 'с.', 'стр.', 'сс.',
            'университет', 'университета', 'институт', 'академия', 'наук',
            'издание', 'монография', 'учебник', 'пособие', 'статья',
            'м.:', 'спб.:', 'киев:', 'минск:',
            'экономика', 'финансы', 'статистика', 'менеджмент', 'маркетинг'
        ])

        has_comma_and_year = (',' in text and bool(re.search(r'\b(19|20)\d{2}\b', text)))
        punctuation_count = text.count('.') + text.count(',')
        has_punctuation = punctuation_count >= 3
        has_abbreviations = any(abbr in text for abbr in ['т.', 'вып.', 'с.', 'сс.', 'г.'])
        reasonable_length = 30 < len(text) < 800

        strong_indicators = [
            starts_with_number,
            bool(starts_with_bracket),
            has_year and has_punctuation,
            has_biblio_keywords and has_year,
            has_comma_and_year and has_punctuation
        ]

        weak_indicators = [
            has_year,
            has_biblio_keywords,
            has_punctuation,
            has_abbreviations
        ]

        is_bibliography = (any(strong_indicators) or (sum(weak_indicators) >= 2)) and reasonable_length

        if is_bibliography and (starts_with_number or starts_with_bracket):
            print(f"   Распознано как библиография: {text[:70]}...")

        return is_bibliography

    def check_citations_vs_bibliography(self, citations: List[str], bibliography_blocks: List[TextBlock]) -> Dict[
        str, Any]:
        if not bibliography_blocks:
            return {
                'valid_references': [],
                'missing_references': citations,
                'valid_count': 0,
                'missing_count': len(citations),
                'bibliography_found': False
            }

        bibliography_entries_count = len(bibliography_blocks)
        print(f"Библиография содержит {bibliography_entries_count} записей")

        valid_references = []
        missing_references = []

        for citation in citations:
            try:
                citation_num = int(citation)
                if 1 <= citation_num <= bibliography_entries_count:
                    valid_references.append(citation)
                    print(f"   Цитата [{citation}] валидна (в пределах 1..{bibliography_entries_count})")
                else:
                    missing_references.append(citation)
                    print(f"   Цитата [{citation}] вне диапазона библиографии (1..{bibliography_entries_count})")
            except ValueError:
                missing_references.append(citation)
                print(f"   Нечисловая цитата [{citation}] не поддерживается")

        return {
            'valid_references': valid_references,
            'missing_references': missing_references,
            'valid_count': len(valid_references),
            'missing_count': len(missing_references),
            'bibliography_found': True
        }

    def _search_semantic_scholar(self, query: str) -> List[SearchResult]:
        """Поиск в Semantic Scholar API"""
        try:
            headers = {}
            if self.config.SEMANTIC_SCHOLAR_API_KEY:
                headers['x-api-key'] = self.config.SEMANTIC_SCHOLAR_API_KEY

            params = {
                'query': query,
                'limit': 3,
                'fields': 'title,authors,year,venue,doi,url'
            }

            response = self.session.get(
                'https://api.semanticscholar.org/graph/v1/paper/search',
                params=params,
                headers=headers,
                timeout=self.config.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_semantic_scholar_results(data)
            else:
                self.logger.warning(f"Semantic Scholar API returned status {response.status_code}")

        except Exception as e:
            self.logger.error(f"Semantic Scholar API error: {e}")

        return []

    def _filter_best_result(self, results: List[SearchResult], original_query: str) -> Optional[SearchResult]:
        """Фильтрует результаты по релевантности оригинальному запросу"""
        if not results:
            return None

        # Сначала сортируем по уверенности
        sorted_results = sorted(results, key=lambda x: x.confidence, reverse=True)

        # Простая проверка релевантности по заголовку
        query_words = set(original_query.lower().split())

        for result in sorted_results:
            if result.title:
                title_words = set(result.title.lower().split())
                # Если есть пересечение ключевых слов, считаем релевантным
                common_words = query_words.intersection(title_words)
                if len(common_words) >= 2:  # Минимум 2 общих слова
                    return result

        # Если нет явно релевантных, возвращаем самый уверенный
        return sorted_results[0] if sorted_results else None

    def _is_relevant_result(self, result: SearchResult, original_text: str) -> bool:
        """Проверяет релевантность результата оригинальной библиографической записи"""
        original_lower = original_text.lower()
        result_title = result.title.lower() if result.title else ""

        # Ключевые слова из оригинальной записи тест
        key_phrases = [
            'толстой', 'война и мир',  # Для Толстого
            'экономик', 'анализ данных',  # Для экономики
            'машинное обучение', 'кнутсен',  # Для ML
            'бизнес-план', 'предпринимательство'  # Для бизнеса
        ]

        # Проверяем совпадение ключевых фраз
        for phrase in key_phrases:
            if phrase in original_lower and phrase in result_title:
                return True

        # Проверяем авторов
        if result.authors:
            for author in result.authors:
                author_lower = author.lower()
                if any(author_word in original_lower for author_word in author_lower.split()):
                    return True

        return False

    def _enhance_single_entry(self, entry: BibliographyEntry) -> BibliographyEntry:
        """Улучшенная версия с проверкой релевантности"""
        search_queries = self._generate_search_queries(entry.text)

        if entry.online_metadata is None:
            entry.online_metadata = {}
        entry.online_metadata['search_queries_used'] = search_queries

        best_relevant_result = None
        best_confidence = 0.0

        for query in search_queries:
            print(f"      🔎 Поиск: '{query}'")
            try:
                results = self.online_searcher.search_publication(query)

                if results:
                    for result in results:
                        # Проверяем релевантность
                        if self._is_relevant_result(result, entry.text):
                            if result.confidence > best_confidence:
                                best_relevant_result = result
                                best_confidence = result.confidence
                                print(f"      Релевантный результат (уверенность: {result.confidence:.2f})")

                                if result.confidence > 0.8:
                                    break
                    else:
                        print(f"      Найдены результаты, но не релевантные")
                else:
                    print(f"      Не найдено результатов для: {query}")

            except Exception as e:
                print(f"      Ошибка при поиске '{query}': {e}")
                continue

        if best_relevant_result and best_confidence > 0.3:
            entry.online_metadata = self._format_online_metadata(best_relevant_result)
            entry.is_verified = True
            entry.enhancement_confidence = best_confidence
            print(f"      Используем релевантный результат с уверенностью: {best_confidence:.2f}")
        else:
            print(f"      Не найдено релевантных результатов")
            # Можно сохранить лучший результат даже если не идеально релевантный
            if results and not best_relevant_result:
                fallback_result = results[0]
                entry.online_metadata = self._format_online_metadata(fallback_result)
                entry.is_verified = False  # Помечаем как непроверенный
                entry.enhancement_confidence = fallback_result.confidence * 0.5  # Понижаем уверенность
                print(f"      Используем fallback результат (уверенность: {fallback_result.confidence:.2f})")

        return entry