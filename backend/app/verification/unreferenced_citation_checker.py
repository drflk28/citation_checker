import re
import hashlib
from collections import defaultdict
from typing import List, Dict, Any, Set, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class UnreferencedCitationChecker:
    """
    Ищет в документе текст, который похож на содержимое источников,
    но не имеет ссылок. Учитывает контекст абзаца.
    """

    def __init__(self, min_similarity_threshold: float = 0.5):
        self.min_similarity = min_similarity_threshold
        self.shingle_size = 5
        self.min_sentence_length = 50
        self.min_matched_shingles = 2

        # Паттерны для поиска ссылок
        self.citation_patterns = [
            r'\[\d+\]',  # [1]
            r'\[\d+\s*-\s*\d+\]',  # [1-3]
            r'\[\d+(?:\s*,\s*\d+)*\]',  # [1,2,3]
            r'\(\d{4}\)',  # (2020)
            r'\([А-ЯЁ][а-яё]+,\s*\d{4}\)',  # (Иванов, 2020)
            r'см\.?\s*\[?\d+\]?',  # см. [1]
            r'с\.?\s*\d+',  # с. 15
            r'стр\.?\s*\d+',  # стр. 15
            r'page\s*\d+',  # page 15
            r'p\.?\s*\d+'  # p. 15
        ]

        # Объединяем паттерны
        self.citation_regex = re.compile('|'.join(self.citation_patterns), re.IGNORECASE)

    def find_unreferenced_citations(
            self,
            document_text: str,
            sources: List[Dict[str, Any]],
            existing_citations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Находит потенциальные цитаты без ссылок
        """
        issues = []

        print(f"\n{'=' * 60}")
        print("🔍 ПОИСК ЦИТАТ БЕЗ ССЫЛОК")
        print(f"{'=' * 60}")
        print(f"   Длина документа: {len(document_text)} символов")
        print(f"   Источников для проверки: {len(sources)}")

        if not sources:
            print("   ⚠️ Нет источников для проверки")
            return issues

        # 1. Разбиваем документ на абзацы
        paragraphs = self._split_into_paragraphs(document_text)
        print(f"   Найдено абзацев: {len(paragraphs)}")

        # 2. Определяем, какие абзацы уже содержат ссылки
        paragraphs_with_citations = self._find_paragraphs_with_citations(paragraphs, existing_citations)
        print(f"   Абзацев с цитатами: {len(paragraphs_with_citations)}")

        # Выводим информацию об абзацах с цитатами для отладки
        for para_idx in sorted(paragraphs_with_citations):
            print(f"      📌 Абзац {para_idx + 1} содержит ссылки")

        # 3. Строим индекс источников
        source_index = self._build_source_index(sources)
        source_sentences_map = self._build_source_sentences_map(sources)
        print(f"   Построен индекс: {len(source_index)} уникальных шинглов")

        issue_count = 0

        # 4. Анализируем ТОЛЬКО абзацы БЕЗ ссылок
        for para_idx, paragraph in enumerate(paragraphs):
            # Пропускаем абзацы, которые УЖЕ содержат ссылки
            if para_idx in paragraphs_with_citations:
                continue

            # Пропускаем слишком короткие абзацы
            if len(paragraph) < 100:
                continue

            # Проверяем, не является ли абзац библиографией
            if self._is_bibliography_paragraph(paragraph):
                print(f"   📚 Абзац {para_idx + 1} пропущен (библиография)")
                continue

            # Разбиваем абзац на предложения
            sentences = self._split_into_sentences(paragraph)

            for sent_idx, sentence in enumerate(sentences):
                if len(sentence) < self.min_sentence_length:
                    continue

                # Проверяем предложение на соответствие источникам
                matches = self._check_sentence_against_sources(sentence, source_index)

                if matches:
                    issue_count += 1

                    context_before, context_after = self._get_sentence_context(
                        paragraph, sent_idx, sentences
                    )

                    detailed_matches = self._create_detailed_matches(
                        matches, sentence, source_sentences_map
                    )

                    print(f"\n   {'-' * 50}")
                    print(f"   🎯 ПРОБЛЕМА #{issue_count} (абзац {para_idx + 1}, предложение {sent_idx + 1})")
                    print(f"      Текст: {sentence[:150]}...")

                    issues.append({
                        'type': 'unreferenced_citation',
                        'sentence': sentence,
                        'sentence_preview': sentence[:200] + '...' if len(sentence) > 200 else sentence,
                        'paragraph_idx': para_idx,
                        'sentence_idx': sent_idx,
                        'paragraph': paragraph[:500] + '...' if len(paragraph) > 500 else paragraph,
                        'context_before': context_before[:200] + '...' if len(context_before) > 200 else context_before,
                        'context_after': context_after[:200] + '...' if len(context_after) > 200 else context_after,
                        'matches': detailed_matches,
                        'matches_count': len(detailed_matches),
                        'description': f'Текст похож на содержание источника "{detailed_matches[0]["source_title"] if detailed_matches else "Unknown"}"',
                        'severity': 'high' if (
                                    detailed_matches and detailed_matches[0]['confidence'] > 70) else 'medium',
                        'suggestion': 'Добавьте ссылку на источник, если это цитата или заимствование'
                    })

        print(f"\n   Найдено проблем: {len(issues)}")
        return issues

    def _is_bibliography_paragraph(self, text: str) -> bool:
        """
        Проверяет, является ли абзац библиографической записью
        """
        if not text:
            return False

        text_lower = text.lower()

        # Признаки библиографии
        indicators = [
            # Начинается с номера и точки
            bool(re.match(r'^\d+\.\s+[А-ЯЁA-Z]', text)),

            # Содержит типичные библиографические элементы
            any(word in text_lower for word in ['изд-во', 'издательство', 'учебник', 'учебное пособие']),

            # Содержит год и обозначение страниц
            (bool(re.search(r'\b\d{4}\b', text)) and ('с.' in text_lower or 'с.' in text_lower)),

            # Содержит ISBN
            'isbn' in text_lower,

            # Типичный формат: Фамилия, И.О. Название
            bool(re.match(r'^[А-ЯЁ][а-яё]+,\s*[А-ЯЁ]\.[А-ЯЁ]\.', text)),

            # Содержит "—" (тире) и год
            ('—' in text and bool(re.search(r'\b\d{4}\b', text))),

            # Содержит место издания (М., СПб., и т.д.)
            bool(re.search(r'\b[ММ]\.|[Сс][Пп]б\.|[Кк]иев\.|[Мм]инск\.', text))
        ]

        # Если хотя бы 2 признака совпадают - это библиография
        return sum(indicators) >= 2

    def _create_issue(self, sentence: str, para_idx: int, sent_idx: int,
                      paragraph: str, context_before: str, context_after: str,
                      detailed_matches: List[Dict]) -> Dict:
        """Создает объект проблемы"""
        return {
            'type': 'unreferenced_citation',
            'sentence': sentence,
            'sentence_preview': sentence[:200] + '...' if len(sentence) > 200 else sentence,
            'paragraph_idx': para_idx,
            'sentence_idx': sent_idx,
            'paragraph': paragraph[:500] + '...' if len(paragraph) > 500 else paragraph,
            'context_before': context_before[:200] + '...' if len(context_before) > 200 else context_before,
            'context_after': context_after[:200] + '...' if len(context_after) > 200 else context_after,
            'matches': detailed_matches,
            'matches_count': len(detailed_matches),
            'description': f'Текст похож на содержание источника "{detailed_matches[0]["source_title"] if detailed_matches else "Unknown"}"',
            'severity': 'high' if (detailed_matches and detailed_matches[0]['confidence'] > 70) else 'medium',
            'suggestion': 'Добавьте ссылку на источник, если это цитата или заимствование'
        }

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Разбивает текст на абзацы более интеллектуально.
        Поддерживает разные форматы: одиночные переносы строк, множественные переносы, маркированные списки.
        """
        if not text:
            return []

        print(f"\n📄 РАЗБИЕНИЕ ТЕКСТА НА АБЗАЦЫ")
        print(f"   Длина текста: {len(text)} символов")

        # 1. Сначала пробуем разбить по двойным переносам (реальные абзацы)
        paragraphs = re.split(r'\n\s*\n', text)

        # Если получилось больше 1 абзаца, используем их
        if len(paragraphs) > 1:
            cleaned = []
            for p in paragraphs:
                # Объединяем строки внутри абзаца
                lines = p.split('\n')
                combined = ' '.join(line.strip() for line in lines if line.strip())
                if combined:
                    cleaned.append(combined)
            print(f"   ✅ Найдено {len(cleaned)} абзацев по двойным переносам")
            return cleaned

        # 2. Если нет двойных переносов, пробуем разбить по одиночным переносам
        #    но группируем связанные строки
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]

        if not lines:
            return []

        print(f"   📝 Найдено {len(lines)} непустых строк")

        paragraphs = []
        current_paragraph = []

        for i, line in enumerate(lines):
            # Признаки начала нового абзаца:
            # 1. Строка начинается с цифры и точки (нумерованный список)
            # 2. Строка начинается с маркера списка (•, -, *)
            # 3. Предыдущая строка заканчивалась точкой и это новый раздел
            # 4. Строка полностью заглавными (возможно заголовок)

            is_new_paragraph = False

            # Проверка на начало нумерованного списка
            if re.match(r'^\d+\.', line):
                is_new_paragraph = True

            # Проверка на маркированный список
            elif re.match(r'^[•\-*]', line):
                is_new_paragraph = True

            # Проверка на заголовок (короткая строка, может быть заглавными)
            elif len(line) < 100 and (line.isupper() or re.match(r'^[А-ЯЁA-Z]', line)):
                # Если предыдущая строка была не пустой и не заголовком
                if current_paragraph and not current_paragraph[-1].isupper():
                    is_new_paragraph = True

            # Проверка на начало нового раздела
            elif any(keyword in line.lower() for keyword in [
                'резюме', 'введение', 'глава', 'раздел', 'часть',
                'анализ', 'план', 'стратегия', 'таблица', 'рисунок'
            ]) and len(line) < 150:
                is_new_paragraph = True

            # Если это новый абзац, сохраняем текущий и начинаем новый
            if is_new_paragraph and current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []

            current_paragraph.append(line)

            # Если строка заканчивается точкой и следующая строка начинается с заглавной
            if line.endswith(('.', '!', '?')) and i < len(lines) - 1:
                next_line = lines[i + 1]
                if next_line and next_line[0].isupper() and len(next_line) < 100:
                    # Это может быть конец абзаца, но проверяем, не список ли это
                    if not re.match(r'^\d+\.', next_line) and not re.match(r'^[•\-*]', next_line):
                        paragraphs.append(' '.join(current_paragraph))
                        current_paragraph = []

        # Добавляем последний абзац
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))

        # 3. Если всё еще только один абзац, пробуем разбить по предложениям
        if len(paragraphs) <= 1:
            print(f"   ⚠️ Не удалось найти явные разделители абзацев")
            print(f"   🔄 Пробуем разбить по предложениям и сгруппировать...")

            sentences = self._split_into_sentences(text)

            # Группируем предложения в абзацы (по 3-5 предложений)
            grouped_paragraphs = []
            chunk_size = 4  # количество предложений в абзаце

            for i in range(0, len(sentences), chunk_size):
                chunk = sentences[i:i + chunk_size]
                if chunk:
                    grouped_paragraphs.append(' '.join(chunk))

            if len(grouped_paragraphs) > 1:
                paragraphs = grouped_paragraphs
                print(f"   ✅ Создано {len(paragraphs)} абзацев группировкой предложений")

        # 4. Если всё еще один абзац, но он очень большой, разбиваем принудительно
        if len(paragraphs) == 1 and len(paragraphs[0]) > 2000:
            print(f"   ⚠️ Очень длинный абзац ({len(paragraphs[0])} символов)")
            print(f"   🔄 Принудительно разбиваем на части...")

            text = paragraphs[0]
            # Разбиваем по маркерам списка
            parts = re.split(r'(?=\n?\d+\.|\n?[•\-*])', text)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) > 1:
                paragraphs = parts
                print(f"   ✅ Разбито на {len(paragraphs)} частей по маркерам списка")

        print(f"   📊 ИТОГО: {len(paragraphs)} абзацев")
        for i, p in enumerate(paragraphs[:5]):  # Показываем первые 5
            print(f"      Абзац {i + 1}: {len(p)} символов, {len(p.split())} слов")
            print(f"         {p[:100]}...")

        return paragraphs

    def _find_paragraphs_with_citations(self, paragraphs: List[str], existing_citations: List[Dict]) -> Set[int]:
        """
        Определяет, какие абзацы уже содержат цитаты
        """
        paragraphs_with_citations = set()

        print(f"\n🔍 ПОИСК АБЗАЦЕВ С ЦИТАТАМИ")

        # 1. Проверяем по паттернам ссылок
        for i, paragraph in enumerate(paragraphs):
            # Ищем любые ссылки вида [1], [2,3], (2020) и т.д.
            if self.citation_regex.search(paragraph):
                paragraphs_with_citations.add(i)
                # Извлекаем номера для отладки
                numbers = re.findall(r'\[(\d+)\]', paragraph)
                if numbers:
                    print(f"    Абзац {i + 1} содержит ссылки: [{', '.join(numbers)}]")

        # 2. Проверяем по существующим цитатам из анализа (на всякий случай)
        for citation in existing_citations:
            citation_text = citation.get('full_paragraph', '') or citation.get('text', '')
            citation_num = citation.get('citation_number')

            if not citation_text:
                continue

            for i, paragraph in enumerate(paragraphs):
                if citation_text in paragraph or paragraph in citation_text:
                    if i not in paragraphs_with_citations:
                        paragraphs_with_citations.add(i)
                        print(f"    Абзац {i + 1} содержит цитату [{citation_num}] (по тексту)")

        print(f"    Всего абзацев с цитатами: {len(paragraphs_with_citations)}")
        return paragraphs_with_citations

    def _paragraph_has_citation(self, paragraph: str, paragraphs_with_citations: Set[int], para_idx: int) -> bool:
        """
        Проверяет, есть ли в абзаце ссылки
        """
        # Проверяем по индексу
        if para_idx in paragraphs_with_citations:
            return True

        # Проверяем по паттернам
        if self.citation_regex.search(paragraph):
            return True

        return False

    def _is_near_citation(self, sentence: str, paragraph: str,
                          paragraphs_with_citations: Set[int], para_idx: int) -> bool:
        """
        Проверяет, находится ли предложение рядом с цитатой в том же абзаце
        """
        # Если абзац не содержит цитат, то и предложение не рядом
        if para_idx not in paragraphs_with_citations:
            return False

        # Проверяем, есть ли в этом же абзаце предложение с цитатой
        sentences = self._split_into_sentences(paragraph)

        for s in sentences:
            if self.citation_regex.search(s):
                # Если в абзаце есть цитата, то любое предложение в этом абзаце
                # считается рядом с цитатой
                return True

        return False

    def _create_detailed_matches(self, matches: List[Dict], sentence: str,
                                 source_sentences_map: Dict[str, List[str]]) -> List[Dict]:
        """Создает детальную информацию о совпадениях"""
        detailed_matches = []

        for match in matches[:3]:  # Берем топ-3
            source_id = match['source_id']

            # Находим наиболее похожее предложение из источника
            best_source_sentence = self._find_best_matching_sentence(
                sentence,
                source_sentences_map.get(source_id, [])
            )

            # Выделяем совпадающие части
            highlighted_sentence, highlighted_source = self._highlight_matches(
                sentence,
                best_source_sentence
            )

            detailed_matches.append({
                **match,
                'source_sentence': best_source_sentence,
                'source_sentence_preview': best_source_sentence[:200] + '...' if len(
                    best_source_sentence) > 200 else best_source_sentence,
                'highlighted_sentence': highlighted_sentence,
                'highlighted_source': highlighted_source,
                'similarity_details': self._calculate_similarity_details(sentence, best_source_sentence)
            })

        return detailed_matches

    def _build_source_index(self, sources: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Строит индекс для быстрого поиска по источникам"""
        index = defaultdict(list)

        for source in sources:
            source_id = source.get('id')
            source_title = source.get('title', 'Unknown')
            content = source.get('full_content', '')

            if not content:
                continue

            # Разбиваем на предложения
            sentences = self._split_into_sentences(content)

            for sentence in sentences:
                if len(sentence) < 50:
                    continue

                shingles = self._create_shingles(sentence, n=self.shingle_size)

                for shingle in shingles:
                    shingle_hash = hashlib.md5(shingle.encode('utf-8')).hexdigest()
                    index[shingle_hash].append({
                        'source_id': source_id,
                        'source_title': source_title,
                        'sentence': sentence,
                        'sentence_preview': sentence[:200] + '...' if len(sentence) > 200 else sentence,
                        'shingle': shingle
                    })

        return dict(index)

    def _build_source_sentences_map(self, sources: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Создает карту предложений для каждого источника"""
        source_sentences = defaultdict(list)

        for source in sources:
            source_id = source.get('id')
            content = source.get('full_content', '')

            if content:
                sentences = self._split_into_sentences(content)
                source_sentences[source_id] = sentences

        return dict(source_sentences)

    def _check_sentence_against_sources(self, sentence: str, source_index: Dict[str, List[Dict]]) -> List[Dict]:
        """Проверяет предложение на соответствие источникам"""
        sentence_shingles = self._create_shingles(sentence, n=self.shingle_size)

        if not sentence_shingles:
            return []

        matches_by_source = defaultdict(lambda: {
            'source_id': None,
            'source_title': None,
            'matched_shingles': set(),
            'matched_sentences': set()
        })

        for shingle in sentence_shingles:
            shingle_hash = hashlib.md5(shingle.encode('utf-8')).hexdigest()

            if shingle_hash in source_index:
                for source_info in source_index[shingle_hash]:
                    source_id = source_info['source_id']

                    if matches_by_source[source_id]['source_id'] is None:
                        matches_by_source[source_id]['source_id'] = source_id
                        matches_by_source[source_id]['source_title'] = source_info['source_title']

                    matches_by_source[source_id]['matched_shingles'].add(shingle)
                    matches_by_source[source_id]['matched_sentences'].add(
                        source_info['sentence_preview']
                    )

        significant_matches = []

        for source_id, match_info in matches_by_source.items():
            matched_count = len(match_info['matched_shingles'])

            if matched_count >= self.min_matched_shingles:
                confidence = min(100, (matched_count / max(len(sentence_shingles), 1)) * 150)
                jaccard = self._calculate_jaccard_similarity(
                    sentence,
                    ' '.join(match_info['matched_sentences'])
                )

                combined_confidence = (confidence * 0.7 + jaccard * 0.3)

                significant_matches.append({
                    'source_id': source_id,
                    'source_title': match_info['source_title'],
                    'matched_shingles_count': matched_count,
                    'total_shingles': len(sentence_shingles),
                    'confidence': combined_confidence,
                    'matched_sentences': list(match_info['matched_sentences'])[:3],
                    'jaccard_similarity': jaccard
                })

        significant_matches.sort(key=lambda x: x['confidence'], reverse=True)
        return significant_matches

    def _find_best_matching_sentence(self, query: str, sentences: List[str]) -> str:
        """Находит наиболее похожее предложение из списка"""
        if not sentences:
            return ""

        best_sentence = ""
        best_score = 0

        query_words = set(re.findall(r'\b\w+\b', query.lower()))

        for sentence in sentences:
            sentence_words = set(re.findall(r'\b\w+\b', sentence.lower()))
            common = query_words.intersection(sentence_words)

            if common:
                score = len(common) / max(len(query_words), len(sentence_words))
                if score > best_score:
                    best_score = score
                    best_sentence = sentence

        return best_sentence or sentences[0]

    def _get_sentence_context(self, paragraph: str, sentence_idx: int, sentences: List[str]) -> Tuple[str, str]:
        """
        Получает контекст до и после указанного предложения
        """
        context_before = ""
        context_after = ""

        # Берем до 2 предложений до
        if sentence_idx > 0:
            context_before = ' '.join(sentences[max(0, sentence_idx - 2):sentence_idx])

        # Берем до 2 предложений после
        if sentence_idx < len(sentences) - 1:
            context_after = ' '.join(sentences[sentence_idx + 1:min(len(sentences), sentence_idx + 3)])

        return context_before, context_after

    def _highlight_matches(self, text1: str, text2: str) -> Tuple[str, str]:
        """Выделяет совпадающие части текста"""
        if not text2:
            return text1, ""

        words1 = text1.split()
        words2 = text2.split()

        # Простое выделение - в реальности нужно более сложное
        return text1, text2

    def _calculate_similarity_details(self, text1: str, text2: str) -> Dict[str, Any]:
        """Вычисляет детали схожести двух текстов"""
        words1 = set(re.findall(r'\b\w+\b', text1.lower()))
        words2 = set(re.findall(r'\b\w+\b', text2.lower()))

        common = words1.intersection(words2)

        return {
            'common_words': list(common)[:10],
            'common_count': len(common),
            'words1_count': len(words1),
            'words2_count': len(words2),
            'jaccard': len(common) / max(len(words1.union(words2)), 1)
        }

    def _create_shingles(self, text: str, n: int) -> Set[str]:
        """Создает набор шинглов из текста"""
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()

        words = text.split()
        shingles = set()

        if len(words) < n:
            return shingles

        for i in range(len(words) - n + 1):
            shingle = ' '.join(words[i:i + n])
            shingles.add(shingle)

        return shingles

    def _calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет Jaccard similarity"""
        words1 = set(re.findall(r'\b\w+\b', text1.lower()))
        words2 = set(re.findall(r'\b\w+\b', text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def _split_into_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения"""
        # Защита от разбиения внутри сокращений
        abbreviations = [
            'т.е.', 'т.д.', 'т.п.', 'и т.д.', 'и т.п.',
            'др.', 'пр.', 'см.', 'рис.', 'табл.', 'гл.',
            'т.р.', 'руб.', 'тыс.', 'млн.', 'млрд.'
        ]

        # Временно заменяем сокращения
        placeholders = {}
        for i, abbr in enumerate(abbreviations):
            placeholder = f"__ABBR_{i}__"
            placeholders[placeholder] = abbr
            text = text.replace(abbr, placeholder)

        # Разбиваем на предложения
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Возвращаем сокращения на место
        result = []
        for sentence in sentences:
            for placeholder, abbr in placeholders.items():
                sentence = sentence.replace(placeholder, abbr)
            result.append(sentence.strip())

        return [s for s in result if s.strip()]