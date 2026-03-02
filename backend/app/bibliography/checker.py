from typing import List, Dict, Any, Optional
from app.models.data_models import TextBlock, BibliographyEntry
import re
import requests
import time
from urllib.parse import quote
import json
from app.services.library_service import library_service
from app.bibliography.semantic_matcher import semantic_matcher
import logging

class BibliographyChecker:
    def __init__(self):
        self.biblio_keywords = [
            'список используемых источников', 'список литературы', 'библиография',
            'литература', 'источники', 'references', 'bibliography',
            'reference', 'source', 'works cited', 'literature'
        ]
        self.section_end_keywords = ['приложение', 'appendix', 'заключение', 'conclusion']
        self.library_service = library_service
        self.semantic_matcher = semantic_matcher
        self.logger = logging.getLogger(__name__)

    def _check_authors_strict(self, search_params: Dict, source: Dict) -> bool:
        """Строгая проверка совпадения авторов"""
        if not search_params.get('authors') or not source.get('authors'):
            return False

        search_authors = [self._normalize_author_name(a) for a in search_params['authors']]
        source_authors = [self._normalize_author_name(a) for a in source['authors']]

        # Проверяем, есть ли хотя бы один общий автор
        common_authors = set(search_authors).intersection(set(source_authors))

        return len(common_authors) > 0

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

    def _convert_library_match_to_search_result(self, library_match: Dict) -> SearchResult:
        """Конвертирует результат из библиотеки в SearchResult"""
        return SearchResult(
            source='personal_library',
            title=library_match.get('title', ''),
            authors=library_match.get('authors', []),
            year=library_match.get('year'),
            publisher=library_match.get('publisher'),
            journal=library_match.get('journal'),
            volume=None,
            issue=None,
            pages=None,
            doi=library_match.get('doi'),
            isbn=library_match.get('isbn'),
            url=library_match.get('url'),
            confidence=min(library_match.get('match_score', 60) / 100.0, 1.0),  # Преобразуем score в confidence 0-1
            is_search_link=False
        )

    def _search_in_library(self, entry_text: str, search_queries: List[str]) -> Optional[Dict[str, Any]]:
        """Ищет запись в локальной библиотеке - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            print(f"\n      🔍 ПОИСК В ЛОКАЛЬНОЙ БИБЛИОТЕКЕ ДЛЯ: '{entry_text[:80]}...'")
            original_text = entry_text
            # Извлекаем ключевые данные из записи
            search_params = self._extract_search_params_from_entry(entry_text)
            print(f"      📊 ПАРАМЕТРЫ ПОИСКА: {search_params}")

            # Используем user_id для демо (в production это будет реальный user_id)
            user_id = "demo_user"
            print(f"      👤 USER ID: {user_id}")

            # Проверяем доступность library_service
            if not hasattr(self, 'library_service') or self.library_service is None:
                print(f"      ❌ library_service не доступен!")
                return None

            # Получаем все источники пользователя
            if not hasattr(self.library_service, 'sources'):
                print(f"      ❌ library_service.sources не доступен!")
                return None

            user_sources = self.library_service.sources.get(user_id, [])
            print(f"      📚 Всего источников у пользователя: {len(user_sources)}")

            if not user_sources:
                print(f"      📭 Библиотека пользователя пуста")
                return None

            # Выводим первые 5 источников для отладки
            print(f"      🔎 ПЕРВЫЕ 5 ИСТОЧНИКОВ В БИБЛИОТЕКЕ:")
            for i, source in enumerate(user_sources[:5]):
                print(f"        {i + 1}. '{source.get('title', 'No title')}'")
                print(f"           Авторы: {source.get('authors', [])}")
                print(f"           Год: {source.get('year')}")
                if source.get('doi'):
                    print(f"           DOI: {source.get('doi')}")

            best_match = None
            best_score = 0
            all_matches = []
            used_source_ids = set()

            # Ищем совпадения среди всех источников
            for source in user_sources:
                if source.get('id') in used_source_ids:
                    continue

                score = self._calculate_library_match_score(source, search_params)

                if score > 0:
                    all_matches.append({
                        'source': source,
                        'score': score,
                        'matched_fields': self._get_matched_fields(source, search_params)
                    })

                    if score > best_score:
                        best_score = score
                        best_match = source
                        print(f"      🎯 НОВОЕ ЛУЧШЕЕ СОВПАДЕНИЕ: {score} баллов")
                        print(f"        Название: {source.get('title', 'No title')}")

            # Если нашли хотя бы одно совпадение с минимальным порогом
            if best_match and best_score >= 80:
                print(f"      ✅ НАЙДЕНО СОВПАДЕНИЕ В БИБЛИОТЕКЕ!")
                print(f"      📊 Лучший результат: {best_score} баллов")
                print(f"      📖 Источник: {best_match.get('title', 'No title')}")
                used_source_ids.add(best_match.get('id'))
                # Форматируем результат
                result = {
                    'id': best_match.get('id'),
                    'title': best_match.get('title'),
                    'authors': best_match.get('authors', []),
                    'year': best_match.get('year'),
                    'publisher': best_match.get('publisher'),
                    'journal': best_match.get('journal'),
                    'doi': best_match.get('doi'),
                    'isbn': best_match.get('isbn'),
                    'url': best_match.get('url'),
                    'has_file': best_match.get('has_file', False),
                    'has_content': best_match.get('has_content', False),
                    'full_content': best_match.get('full_content', ''),
                    'content_preview': best_match.get('content_preview', ''),
                    'text_length': best_match.get('text_length', 0),
                    'match_score': best_score,
                    'matched_fields': self._get_matched_fields(best_match, search_params)
                }

                print(f"      📝 Результат: {result.get('title')}")
                print(f"      🎯 Баллы совпадения: {best_score}")
                return result
            elif best_match and best_score >= 60:
                print(f"      📊 ХОРОШЕЕ СОВПАДЕНИЕ: {best_score} баллов")
                # Проверяем, не является ли это ложным срабатыванием
                # Сравниваем авторов более строго
                if self._check_authors_strict(search_params, best_match):
                    print(f"      ✅ АВТОРЫ ПОДТВЕРЖДЕНЫ - ИСПОЛЬЗУЕМ")
                    # ... вернуть результат ...
                else:
                    print(f"      ⚠ АВТОРЫ НЕ СОВПАДАЮТ - ПРОПУСКАЕМ")
                    return None
            else:
                print(f"      ❌ НЕТ ДОСТАТОЧНО ХОРОШИХ СОВПАДЕНИЙ В БИБЛИОТЕКЕ")
                print(f"      📊 Лучший score: {best_score} (нужно минимум 60)")
                if all_matches:
                    print(f"      📈 Все совпадения:")
                    for match in sorted(all_matches, key=lambda x: x['score'], reverse=True)[:3]:
                        print(f"        - {match['score']} баллов: {match['source'].get('title')}")
                return None

        except Exception as e:
            print(f"      ❌ ОШИБКА ПРИ ПОИСКЕ В БИБЛИОТЕКЕ: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_matched_fields(self, source: Dict, search_params: Dict) -> List[str]:
        """Возвращает список полей, по которым было найдено совпадение"""
        matched_fields = []

        if search_params.get('doi') and source.get('doi'):
            if search_params['doi'].lower() == source['doi'].lower():
                matched_fields.append('doi')

        if search_params.get('isbn') and source.get('isbn'):
            if search_params['isbn'].replace('-', '') == source['isbn'].replace('-', ''):
                matched_fields.append('isbn')

        if search_params.get('title') and source.get('title'):
            search_title = search_params['title'].lower()
            source_title = source['title'].lower()
            if search_title == source_title:
                matched_fields.append('title_exact')
            elif search_title in source_title or source_title in search_title:
                matched_fields.append('title_partial')
            else:
                search_words = set(re.findall(r'\w+', search_title))
                source_words = set(re.findall(r'\w+', source_title))
                if search_words.intersection(source_words):
                    matched_fields.append('title_words')

        if search_params.get('authors') and source.get('authors'):
            search_authors = [a.lower().strip() for a in search_params['authors'] if a.strip()]
            source_authors = [a.lower().strip() for a in source['authors'] if a.strip()]

            for search_author in search_authors:
                search_surname = search_author.split()[0] if search_author.split() else search_author
                for source_author in source_authors:
                    source_surname = source_author.split()[0] if source_author.split() else source_author
                    if search_surname == source_surname:
                        matched_fields.append('authors')
                        break

        if search_params.get('year') and source.get('year'):
            if str(search_params['year']) == str(source['year']):
                matched_fields.append('year')

        return list(set(matched_fields))  # Убираем дубликаты

    def verify_citation_in_source(self, citation_context: str, source_content: str) -> Dict[str, Any]:
        """Проверяет, содержит ли источник семантически похожий текст"""
        if not source_content or not citation_context:
            return {
                'found': False,
                'confidence': 0,
                'reason': 'Недостаточно данных для проверки'
            }

        # Извлекаем ключевые слова
        keywords = self._extract_keywords(citation_context)

        # Ищем ключевые слова в источнике
        matches = []
        source_lower = source_content.lower()

        for keyword in keywords:
            if keyword in source_lower:
                matches.append(keyword)

        # Рассчитываем уверенность
        confidence = self._calculate_match_confidence(len(matches), len(keywords))

        # Находим лучший фрагмент
        best_snippet = self._find_best_snippet_by_keywords(source_content, matches)

        if len(matches) > 0:
            return {
                'found': True,
                'confidence': confidence,
                'match_type': 'semantic',
                'matched_keywords': matches,
                'best_snippet': best_snippet,
                'keywords_found': len(matches),
                'keywords_total': len(keywords)
            }
        else:
            return {
                'found': False,
                'confidence': 0,
                'reason': 'Ключевые слова цитаты не найдены в источнике'
            }

    def _calculate_match_confidence(self, found: int, total: int) -> float:
        """Рассчитывает уверенность совпадения"""
        if total == 0:
            return 0

        ratio = found / total

        if ratio >= 0.7:
            return 90
        elif ratio >= 0.5:
            return 75
        elif ratio >= 0.3:
            return 60
        elif ratio >= 0.2:
            return 40
        else:
            return 20

    def _calculate_library_match_score(self, source: Dict, search_params: Dict) -> int:
        """Вычисляет оценку совпадения - ИСПРАВЛЕННАЯ"""
        score = 0

        print(f"\n        🔍 Сравниваем с источником: '{source.get('title', 'No title')[:50]}...'")

        # Нормализуем данные
        search_title = (search_params.get('title') or '').lower().strip()
        source_title = (source.get('title') or '').lower().strip()

        # 1. Проверка DOI/ISBN (самые точные) - пропускаем, их нет

        # 2. Проверка названия - ИСПРАВЛЕННАЯ ЛОГИКА
        if search_title and source_title:
            # Убираем ВСЕ инициалы, точки, запятые и короткие слова
            def clean_text(text):
                # Удаляем инициалы типа "а.", "с.", "м."
                text = re.sub(r'\b[а-я]\.\s*', '', text)
                # Удаляем отдельные буквы с точками
                text = re.sub(r'\b[а-яё]\.', '', text)
                # Удаляем запятые, точки, двоеточия
                text = re.sub(r'[.,:;]', '', text)
                # Удаляем короткие слова (меньше 3 букв)
                words = text.split()
                words = [w for w in words if len(w) > 2]
                return ' '.join(words).lower()

            clean_search = clean_text(search_title)
            clean_source = clean_text(source_title)

            print(f"        🔧 Очищенные заголовки:")
            print(f"           Ищем: '{clean_search}'")
            print(f"           В: '{clean_source}'")

            # Точное совпадение после очистки
            if clean_search == clean_source:
                score += 70
                print(f"        ✅ ТОЧНОЕ СОВПАДЕНИЕ НАЗВАНИЯ (после очистки) (+70)")

            # Одно содержит другое
            elif clean_search in clean_source or clean_source in clean_search:
                score += 60
                print(f"        ✅ ЧАСТИЧНОЕ СОВПАДЕНИЕ НАЗВАНИЯ (+60)")

            # Совпадение ключевых слов (только длинных!)
            else:
                search_words = set(clean_search.split())
                source_words = set(clean_source.split())
                common_words = search_words.intersection(source_words)

                # Фильтруем: берем только слова длиной > 4 (значимые)
                significant_common = {w for w in common_words if len(w) > 4}

                if significant_common:
                    keyword_score = len(significant_common) * 20
                    score += keyword_score
                    print(f"        ✅ ОБЩИЕ КЛЮЧЕВЫЕ СЛОВА: {significant_common} (+{keyword_score})")
                else:
                    # Незначительные совпадения (инициалы и т.д.) - НЕ ДАЕМ БАЛЛОВ!
                    print(f"        ⚠ Незначительные совпадения: {common_words} (0 баллов)")

        # 3. Проверка авторов - САМОЕ ВАЖНОЕ!
        if search_params.get('authors') and source.get('authors'):
            search_authors = [a.lower().strip() for a in search_params['authors'] if a and len(a) > 2]
            source_authors = [a.lower().strip() for a in source['authors'] if a and len(a) > 2]

            print(f"        🔍 Сравнение авторов:")
            print(f"          Ищем: {search_authors}")
            print(f"          В: {source_authors}")

            # Убираем дубликаты
            search_authors = list(set(search_authors))
            source_authors = list(set(source_authors))

            author_matches = 0
            for search_author in search_authors:
                for source_author in source_authors:
                    # Нормализуем: убираем точки, инициалы
                    norm_search = self._normalize_author_name(search_author)
                    norm_source = self._normalize_author_name(source_author)

                    if norm_search and norm_source and norm_search == norm_source:
                        author_matches += 1
                        print(f"        ✅ ТОЧНОЕ СОВПАДЕНИЕ АВТОРА: {search_author} == {source_author}")
                        break

            # ВЕС авторов должен быть ВЫШЕ, чем вес заголовка!
            if author_matches > 0:
                score += author_matches * 50  # 50 баллов за каждого совпавшего автора
                print(f"        📊 Авторских совпадений: {author_matches} (+{author_matches * 50} баллов)")
            else:
                # Если авторы НЕ совпадают - СИЛЬНЫЙ ШТРАФ
                score -= 40
                print(f"        ❌ АВТОРЫ НЕ СОВПАДАЮТ! (-40)")

        # 4. Проверка года
        if search_params.get('year') and source.get('year'):
            search_year = str(search_params['year']).strip()
            source_year = str(source['year']).strip()
            if search_year == source_year:
                score += 20
                print(f"        ✅ СОВПАДЕНИЕ ГОДА: {search_year} (+20)")
            else:
                score -= 15
                print(f"        ❌ НЕСОВПАДЕНИЕ ГОДА: {search_year} != {source_year} (-15)")

        print(f"        📊 ИТОГОВЫЙ SCORE: {score} баллов")
        return max(score, 0)  # Не меньше 0

    def _extract_search_params_from_entry(self, entry_text: str) -> Dict[str, Any]:
        """Извлекает параметры поиска из библиографической записи - УЛУЧШЕННАЯ ВЕРСИЯ"""
        # Очищаем текст
        clean_text = re.sub(r'\s+', ' ', entry_text.strip())
        print(f"\n        📝 Оригинальный текст: '{clean_text}'")

        # 1. Сначала пытаемся извлечь полное название (новый метод)
        full_title = self._extract_complete_title(clean_text)

        # 2. Если не удалось, используем старый метод
        if not full_title:
            full_title = self._extract_title(clean_text)

        # 3. Извлекаем авторы
        authors = self._extract_authors(clean_text)

        # 4. Извлекаем год
        year = self._extract_year(clean_text)

        # 5. Остальные параметры остаются без изменений
        doi = None
        isbn = None
        publisher = None
        journal = None

        # Извлекаем DOI
        doi_patterns = [
            r'doi:\s*([^\s,.;]+)',
            r'DOI:\s*([^\s,.;]+)',
            r'https?://doi\.org/([^\s]+)',
            r'\b10\.\d{4,9}/[^\s]+'
        ]
        for pattern in doi_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                doi = match.group(1).strip()
                break

        # Извлекаем ISBN
        isbn_patterns = [
            r'ISBN[\s:-]*([\d\-X]{10,17})',
            r'ISBN\s+([\d\-X]{10,17})',
            r'\b[\d\-X]{10,17}\b(?=.*ISBN)',
        ]
        for pattern in isbn_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                isbn = match.group(1).strip()
                break

        # Извлекаем издательство
        publisher_patterns = [
            r'—\s*[^:]*:\s*([^.,;]+?)(?=\.|,|;|\s*\d|$)',
            r':\s*([^.,;]+?)(?=\.|,|;|\s*\d|$)',
            r'изд-во\s+([^.,;]+)',
            r'издательство\s+([^.,;]+)',
        ]
        for pattern in publisher_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                publisher = match.group(1).strip()
                break

        # Извлекаем журнал
        journal_patterns = [
            r'//\s*([^.,]+?)(?=\.|,|\s*\d|$)',
            r'журнал\s+([^.,;]+)',
            r'Журнал\s+([^.,;]+)',
        ]
        for pattern in journal_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                journal = match.group(1).strip()
                break

        result = {
            'title': full_title,
            'authors': authors,
            'year': year,
            'doi': doi,
            'isbn': isbn,
            'publisher': publisher,
            'journal': journal,
            'original_text': clean_text
        }

        print(f"        📊 Параметры поиска:")
        print(f"          📖 Заголовок: {full_title}")
        print(f"          👥 Авторы: {authors}")
        print(f"          📅 Год: {year}")
        print(f"          🔗 DOI: {doi}")
        print(f"          📘 ISBN: {isbn}")
        print(f"          🏢 Издательство: {publisher}")
        print(f"          📰 Журнал: {journal}")

        return result

    def _extract_complete_title(self, text: str) -> Optional[str]:
        """Извлекает полное название работы из библиографической записи"""
        if not text:
            return None

        # Очищаем текст
        text = re.sub(r'\s+', ' ', text.strip())

        print(f"        🔍 Извлекаем полный заголовок из: '{text[:100]}...'")

        # 1. Пытаемся найти название между авторами и технической информацией
        # Паттерн: авторы [название] : тип / редакторы и т.д.

        # Убираем авторов (все до первой точки, двоеточия или года)
        text_without_authors = text

        # Ищем конец авторского блока
        author_end_patterns = [
            r'^[^.]*\.\s*',  # Заканчивается точкой
            r'^[^:]*:\s*',  # Заканчивается двоеточием
            r'^[^/]*/\s*',  # Заканчивается слешем
        ]

        for pattern in author_end_patterns:
            match = re.match(pattern, text)
            if match:
                text_without_authors = text[len(match.group(0)):].strip()
                break

        # 2. Теперь ищем конец названия
        # Название обычно заканчивается перед:
        # - ": учебник", ": пособие" и т.д.
        # - " / " (редакторы)
        # - ". — " (издательство)
        # - ", " (продолжение описания)

        title_end_patterns = [
            r'^([^:]+?)(?=:\s*(?:учебник|пособие|монография|учебное\s+пособие|учебно-методическое))',
            r'^([^/]+?)(?=/\s*[А-ЯЁA-Z])',  # Перед редакторами
            r'^([^.]+?)(?=\.\s*—)',  # Перед издательством
            r'^([^,]+?)(?=,\s*\d{4})',  # Перед годом
            r'^([^;]+)',  # До точки с запятой
            r'^([^.]+)',  # До точки
        ]

        for pattern in title_end_patterns:
            match = re.search(pattern, text_without_authors)
            if match:
                title = match.group(1).strip()
                # Очищаем от лишних символов
                title = re.sub(r'^[.,:;\s]+', '', title)
                title = re.sub(r'[.,:;\s]+$', '', title)

                if title and len(title) > 5:
                    # Проверяем, что это не слишком короткий и не технический текст
                    if (len(title) >= 10 and
                            not any(word in title.lower() for word in ['т.', 'вып.', 'с.', 'г.', 'изд-во']) and
                            re.search(r'[а-яА-ЯёЁa-zA-Z]', title)):
                        print(f"        ✅ Найден полный заголовок: '{title}'")
                        return title

        # 3. Если не нашли по паттернам, используем первые значимые слова
        words = text_without_authors.split()
        meaningful_words = []

        # Ищем первые 5-10 значимых слов
        for word in words[:15]:
            # Пропускаем короткие и служебные слова
            if (len(word) > 2 and
                    not word.lower() in ['под', 'ред', 'ред.', 'изд-во', 'издательство'] and
                    not re.match(r'^[A-Z]\.$', word) and  # Пропускаем инициалы
                    not re.match(r'^\d+$', word)):  # Пропускаем числа
                meaningful_words.append(word)

            if len(meaningful_words) >= 8:
                break

        if meaningful_words:
            title = ' '.join(meaningful_words)
            # Очищаем от технических символов
            title = re.sub(r'[.,:;—/]$', '', title).strip()

            if len(title) > 10:
                print(f"        📝 Заголовок из первых слов: '{title}'")
                return title

        print(f"        ⚠ Не удалось извлечь полный заголовок")
        return None

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

    def _extract_search_params_from_entry(self, entry_text: str) -> Dict[str, Any]:
        """Извлекает параметры поиска из библиографической записи - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        # Очищаем текст
        clean_text = re.sub(r'\s+', ' ', entry_text.strip())
        print(f"\n        📝 Оригинальный текст: '{clean_text[:100]}...'")

        # 1. Извлекаем заголовок
        title = self._extract_title(clean_text)

        # 2. Извлекаем авторы (список фамилий)
        authors = self._extract_authors_list(clean_text)

        # 3. Извлекаем год
        year = self._extract_year(clean_text)

        # 4. Извлекаем DOI
        doi = None
        doi_patterns = [
            r'doi:\s*([^\s,.;]+)',
            r'DOI:\s*([^\s,.;]+)',
            r'https?://doi\.org/([^\s]+)',
            r'\b10\.\d{4,9}/[^\s]+'
        ]
        for pattern in doi_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                doi = match.group(1).strip()
                break

        # 5. Извлекаем ISBN
        isbn = None
        isbn_patterns = [
            r'ISBN[\s:-]*([\d\-X]{10,17})',
            r'ISBN\s+([\d\-X]{10,17})',
            r'\b[\d\-X]{10,17}\b(?=.*ISBN)',
        ]
        for pattern in isbn_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                isbn = match.group(1).strip()
                break

        # 6. Извлекаем издательство
        publisher = None
        publisher_patterns = [
            r'—\s*[^:]*:\s*([^.,;]+?)(?=\.|,|;|\s*\d|$)',
            r':\s*([^.,;]+?)(?=\.|,|;|\s*\d|$)',
            r'изд-во\s+([^.,;]+)',
            r'издательство\s+([^.,;]+)',
        ]
        for pattern in publisher_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                publisher = match.group(1).strip()
                break

        # 7. Извлекаем журнал
        journal = None
        journal_patterns = [
            r'//\s*([^.,]+?)(?=\.|,|\s*\d|$)',
            r'журнал\s+([^.,;]+)',
            r'Журнал\s+([^.,;]+)',
        ]
        for pattern in journal_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                journal = match.group(1).strip()
                break

        result = {
            'title': title,
            'authors': authors,  # Теперь это список фамилий
            'year': year,
            'doi': doi,
            'isbn': isbn,
            'publisher': publisher,
            'journal': journal,
            'original_text': clean_text
        }

        print(f"        📊 Параметры поиска:")
        print(f"          📖 Заголовок: {title}")
        print(f"          👥 Авторы: {authors}")
        print(f"          📅 Год: {year}")
        print(f"          🔗 DOI: {doi}")
        print(f"          📘 ISBN: {isbn}")
        print(f"          🏢 Издательство: {publisher}")
        print(f"          📰 Журнал: {journal}")

        return result

    def _normalize_author_name(self, author: str) -> str:
        """Нормализует имя автора для сравнения"""
        if not author:
            return ""

        # Приводим к нижнему регистру
        author = author.lower().strip()

        # Удаляем инициалы и точки
        author = re.sub(r'[а-я]\.\s*', '', author)  # русские инициалы
        author = re.sub(r'[a-z]\.\s*', '', author)  # английские инициалы
        author = re.sub(r'\.', '', author)  # все оставшиеся точки

        # Удаляем лишние пробелы
        author = re.sub(r'\s+', ' ', author).strip()

        # Берем только фамилию (первое слово)
        parts = author.split()
        if parts:
            return parts[0]

        return author

    def _extract_authors_list(self, text: str) -> List[str]:
        """
        Извлекает список фамилий авторов из библиографической записи.
        РАБОЧАЯ ВЕРСИЯ.
        """
        authors = []

        print(f"        🔍 Анализируем текст для авторов: '{text[:100]}...'")

        # 1. Ищем паттерн: Фамилия, И. О. (русские авторы)
        # Пример: "Лопарева, А. М." или "Грачев, С. А., Гундорова, М. А."
        pattern_russian = r'([А-ЯЁ][а-яё]+),\s*[А-ЯЁ]\.\s*[А-ЯЁ]\.'

        matches = re.findall(pattern_russian, text)
        if matches:
            print(f"        ✅ Найдены авторы (паттерн русский): {matches}")
            return matches  # Возвращаем список фамилий

        # 2. Если не нашли, ищем другой паттерн: Фамилия И.О.
        pattern_russian2 = r'([А-ЯЁ][а-яё]+)\s+[А-ЯЁ]\.[А-ЯЁ]\.'
        matches = re.findall(pattern_russian2, text)
        if matches:
            print(f"        ✅ Найдены авторы (паттерн русский2): {matches}")
            return matches

        # 3. Если не нашли, ищем просто фамилии в начале строки
        # Берем первые 5-7 слов как возможный блок авторов
        words = text.split()
        potential_authors = []

        for i, word in enumerate(words[:7]):
            # Проверяем, похоже ли слово на фамилию
            if (re.match(r'^[А-ЯЁ][а-яё]+$', word) and
                    len(word) > 2 and
                    word.lower() not in ['изд', 'под', 'ред', 'авт', 'сост']):
                potential_authors.append(word)

        if potential_authors:
            print(f"        👤 Авторы (fallback): {potential_authors}")
            return potential_authors

        print(f"        ⚠ Авторы не найдены")
        return []

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
        """Извлекает название работы - ИСПРАВЛЕННАЯ"""
        if not text:
            return None

        # 1. Удаляем авторов в начале (всё до первого двоеточия или точки после авторов)
        # Простой паттерн: фамилия, инициалы
        text_without_authors = re.sub(
            r'^[А-ЯЁ][а-яё]+(?:,\s*[А-ЯЁ]\.[А-ЯЁ]\.)?(?:\s+и\s+[А-ЯЁ][а-яё]+(?:,\s*[А-ЯЁ]\.[А-ЯЁ]\.)?)*', '', text)

        # 2. Удаляем начальные знаки препинания
        text_without_authors = text_without_authors.lstrip('.,: ')

        # 3. Удаляем квадратные скобки
        text_without_authors = re.sub(r'\[.*?\]', '', text_without_authors)

        # 4. Ищем настоящий заголовок
        # Заголовок обычно до: ":", "/", " — ", "("
        patterns = [
            r'^([^:/—(]+?)(?=:\s*(?:учебник|пособие|учебное|практикум))',
            r'^([^:/—(]+?)(?=/\s*[А-ЯЁA-Z])',
            r'^([^:/—(]+?)(?=—)',
            r'^([^:/—(]+?)(?=\()',
        ]

        for pattern in patterns:
            match = re.search(pattern, text_without_authors)
            if match:
                title = match.group(1).strip()
                # Очищаем от лишнего
                title = re.sub(r'[.,:;—/]$', '', title).strip()

                if title and len(title) > 3:
                    # Удаляем инициалы в начале заголовка
                    title = re.sub(r'^[А-ЯЁ]\.\s*[А-ЯЁ]\.\s*', '', title)
                    return title

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

    def find_citation_in_sources(self, citation_text: str, context: str, source_texts: List[Dict]) -> Dict:
        """Ищет конкретную цитату в текстах источников"""
        results = []

        for source in source_texts:
            source_content = source.get('full_content', '')
            if not source_content:
                continue

            # Упрощенная проверка: ищем ключевые слова из контекста цитаты
            search_keywords = self._extract_keywords_from_context(context)

            matches = []
            for keyword in search_keywords[:5]:  # Проверяем первые 5 ключевых слов
                if keyword and len(keyword) > 3:  # Только слова длиной > 3 символов
                    if keyword.lower() in source_content.lower():
                        matches.append(keyword)

            if matches:
                # Находим фрагмент с максимальным количеством совпадений
                best_snippet = self._find_best_snippet(source_content, matches)
                match_score = len(matches)

                results.append({
                    'source_id': source.get('id'),
                    'source_title': source.get('title'),
                    'match_score': match_score,
                    'matched_keywords': matches,
                    'snippet': best_snippet,
                    'full_content_preview': source_content[:500] + "..." if len(
                        source_content) > 500 else source_content
                })

        # Сортируем по количеству совпадений
        results.sort(key=lambda x: x['match_score'], reverse=True)

        return {
            'citation_text': citation_text,
            'context': context,
            'found_in_sources': results[:3] if results else [],  # Топ-3 результатов
            'total_matches': len(results)
        }

    def _extract_keywords_from_context(self, context: str) -> List[str]:
        """Извлекает ключевые слова из контекста цитаты"""
        # Убираем стоп-слова и короткие слова
        stop_words = {'и', 'в', 'на', 'по', 'с', 'из', 'для', 'что', 'как', 'это', 'то', 'же', 'все', 'его', 'их'}

        words = re.findall(r'\b[а-яА-ЯёЁ]{4,}\b', context.lower())
        keywords = [word for word in words if word not in stop_words]

        return list(set(keywords))  # Убираем дубликаты

    def _find_best_snippet(self, text: str, keywords: List[str]) -> str:
        """Находит лучший фрагмент текста с ключевыми словами"""
        sentences = re.split(r'(?<=[.!?])\s+', text)

        if not sentences:
            return text[:300] + "..." if len(text) > 300 else text

        # Оцениваем каждое предложение по количеству ключевых слов
        scored_sentences = []
        for sentence in sentences:
            score = 0
            for keyword in keywords:
                if keyword.lower() in sentence.lower():
                    score += 1

            if score > 0:
                scored_sentences.append((score, sentence))

        if scored_sentences:
            # Сортируем по количеству совпадений
            scored_sentences.sort(key=lambda x: x[0], reverse=True)

            # Берем лучшее предложение и контекст вокруг него
            best_sentence = scored_sentences[0][1]

            # Находим индекс этого предложения
            for i, sent in enumerate(sentences):
                if sent == best_sentence:
                    start = max(0, i - 1)
                    end = min(len(sentences), i + 2)
                    return " ".join(sentences[start:end])

        return text[:300] + "..." if len(text) > 300 else text

    def verify_citation_with_source(self, citation_text: str, citation_context: str,
                                    source_content: str, source_title: str) -> Dict[str, Any]:
        """Проверяет, содержит ли источник данную цитату"""
        if not source_content:
            return {
                'found': False,
                'reason': 'Нет доступа к тексту источника',
                'confidence': 0
            }

        # Очищаем текст цитаты
        clean_citation = self._clean_citation_text(citation_text, citation_context)

        # 1. Проверяем точное совпадение
        if clean_citation in source_content:
            return {
                'found': True,
                'confidence': 100,
                'match_type': 'exact',
                'position': source_content.find(clean_citation),
                'matched_text': clean_citation[:200] + "..." if len(clean_citation) > 200 else clean_citation
            }

        # 2. Ищем похожие фразы
        similar_matches = self._find_similar_phrases(clean_citation, source_content)

        if similar_matches:
            best_match = similar_matches[0]
            return {
                'found': True,
                'confidence': min(best_match['similarity'] * 100, 95),
                'match_type': 'similar',
                'similar_matches': similar_matches[:3],
                'best_match': best_match['text'][:200] + "..." if len(best_match['text']) > 200 else best_match['text']
            }

        # 3. Ищем по ключевым словам
        keywords = self._extract_keywords(clean_citation)
        keyword_matches = self._find_keyword_matches(keywords, source_content)

        if keyword_matches:
            return {
                'found': True,
                'confidence': min(keyword_matches['score'] * 100, 80),
                'match_type': 'keywords',
                'matched_keywords': keyword_matches['matched_keywords'],
                'total_keywords': len(keywords)
            }

        return {
            'found': False,
            'confidence': 0,
            'reason': 'Цитата не найдена в источнике'
        }

    def _clean_citation_text(self, text: str, context: str) -> str:
        """Очищает текст цитаты для поиска"""
        # Объединяем текст и контекст
        full_text = f"{text or ''} {context or ''}".strip()

        # Убираем номера цитат
        full_text = re.sub(r'\[\d+\]', '', full_text)

        # Убираем лишние пробелы
        full_text = re.sub(r'\s+', ' ', full_text)

        # Оставляем разумную длину
        return full_text[:500]

    def _find_similar_phrases(self, citation: str, source: str, min_length: int = 20) -> List[Dict]:
        """Находит семантически похожие фразы в источнике"""
        # Разбиваем на предложения
        sentences = re.split(r'(?<=[.!?])\s+', citation)
        matches = []

        for sentence in sentences:
            if len(sentence) < min_length:
                continue

            # Ищем похожие предложения в источнике
            # (здесь можно использовать более сложную логику сравнения)
            words = set(sentence.lower().split())

            # Ищем в источнике предложения с общими словами
            source_sentences = re.split(r'(?<=[.!?])\s+', source)

            for source_sentence in source_sentences:
                source_words = set(source_sentence.lower().split())
                common_words = words.intersection(source_words)

                if len(common_words) >= max(2, len(words) * 0.3):  # Хотя бы 30% общих слов
                    similarity = len(common_words) / max(len(words), len(source_words))

                    if similarity > 0.3:  # Порог схожести
                        matches.append({
                            'text': source_sentence,
                            'similarity': similarity,
                            'common_words': list(common_words)
                        })

        # Сортируем по схожести
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        return matches

    def verify_citation_semantically(self, citation_data: Dict[str, Any],
                                     source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Семантическая проверка цитаты в источнике.
        """
        try:
            print(f"Семантическая проверка цитаты в источнике {source_data.get('id')}")

            # Получаем полный текст цитаты с контекстом
            citation_text = citation_data.get('full_paragraph', '') or citation_data.get('text', '')
            citation_context = citation_data.get('context', '')

            # Получаем текст источника
            source_content = source_data.get('full_content', '')

            if not source_content:
                return {
                    'success': False,
                    'verified': False,
                    'reason': 'Текст источника недоступен для семантического анализа',
                    'confidence': 0
                }

            # Извлекаем ключевые фразы из цитаты
            key_phrases = self.semantic_matcher.extract_key_phrases(
                f"{citation_text} {citation_context}".strip(),
                max_phrases=15
            )

            # Ищем ключевые фразы в источнике
            found_phrases = []
            source_lower = source_content.lower()
            for phrase in key_phrases:
                if phrase.lower() in source_lower:
                    found_phrases.append(phrase)

            # Семантическая проверка
            verification_result = self.semantic_matcher.verify_citation_in_source(
                citation_data, source_data
            )

            # Форматируем результат
            result = {
                'success': True,
                'verified': verification_result['verified'],
                'confidence': verification_result['confidence'],
                'verification_level': verification_result.get('verification_level'),
                'best_match': verification_result.get('best_match'),
                'analysis_details': verification_result.get('analysis_details'),
                'key_phrases': {
                    'total': len(key_phrases),
                    'found': found_phrases,
                    'found_count': len(found_phrases)
                },
                'source_info': {
                    'id': source_data.get('id'),
                    'title': source_data.get('title'),
                    'authors': source_data.get('authors', []),
                    'year': source_data.get('year')
                }
            }

            if not verification_result['verified']:
                result['reason'] = 'Семантически похожий текст не найден в источнике'

            print(
                f"Результат семантической проверки: verified={result['verified']}, confidence={result['confidence']}, found_phrases={len(found_phrases)}/{len(key_phrases)}")

            return result

        except Exception as e:
            print(f"Ошибка при семантической проверке: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'verified': False,
                'reason': f'Ошибка анализа: {str(e)}',
                'confidence': 0,
                'key_phrases': {'total': 0, 'found': [], 'found_count': 0}
            }

    async def verify_citation_content(self, user_id: str, citation_text: str,
                                source_id: str) -> Dict[str, Any]:
        """Улучшенная проверка соответствия цитаты содержанию источника"""
        try:
            # Получаем содержание источника
            content_result = await self.library_service.get_source_content(user_id, source_id)
            if not content_result['success'] or not content_result['content']:
                return {
                    "success": False,
                    "message": "Содержание источника недоступно для проверки"
                }

            source = content_result['source']
            source_content = content_result['content']

            # Старая проверка (точные совпадения)
            verification_result = self._check_content_matches(citation_text, source_content)

            # Новая семантическая проверка
            semantic_result = self.verify_citation_semantically(
                {'text': citation_text},
                {'full_content': source_content, **source}
            )

            # Объединяем результаты
            combined_result = {
                "success": True,
                "citation_text": citation_text,
                "source_id": source_id,
                "exact_matches": verification_result,
                "semantic_verification": semantic_result,
                "combined_confidence": self._calculate_combined_confidence(
                    verification_result, semantic_result
                ),
                "recommendation": self._generate_verification_recommendation(
                    verification_result, semantic_result
                )
            }

            return combined_result

        except Exception as e:
            logger.error(f"Error verifying citation content: {e}")
            return {
                "success": False,
                "message": f"Ошибка при проверке содержания: {str(e)}"
            }

    def _calculate_combined_confidence(self, exact_matches: Dict,
                                       semantic_result: Dict) -> float:
        """Рассчитывает общую уверенность на основе точных и семантических совпадений"""
        exact_confidence = exact_matches.get('confidence_score', 0)
        semantic_confidence = semantic_result.get('confidence', 0)

        # Весовые коэффициенты
        exact_weight = 0.4 if exact_matches.get('exact_match') else 0.2
        semantic_weight = 0.6

        combined = (exact_confidence * exact_weight +
                    semantic_confidence * semantic_weight)

        return min(combined, 100)

    def _generate_verification_recommendation(self, exact_matches: Dict,
                                              semantic_result: Dict) -> str:
        """Генерирует рекомендацию на основе результатов проверки"""
        if exact_matches.get('exact_match'):
            return "✅ Цитата точно найдена в источнике"

        semantic_verified = semantic_result.get('verified', False)
        semantic_confidence = semantic_result.get('confidence', 0)

        if semantic_verified and semantic_confidence > 70:
            return "✅ Цитата семантически соответствует источнику (высокая уверенность)"
        elif semantic_verified and semantic_confidence > 50:
            return "⚠️ Цитата частично соответствует источнику (средняя уверенность)"
        elif semantic_confidence > 30:
            return "⚠️ Возможно соответствие, требуется проверка"
        else:
            return "❌ Цитата, вероятно, не соответствует источнику"