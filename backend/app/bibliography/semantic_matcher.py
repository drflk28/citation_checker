import re
import string
from typing import Dict, List, Tuple, Optional, Any, Set
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Настройка логирования
logger = logging.getLogger(__name__)


class FixedSemanticCitationMatcher:
    """
    ИСПРАВЛЕННАЯ версия: исключает метаданные источника из поиска
    """

    def __init__(self, language: str = 'russian'):
        self.language = language

        # Инициализация TF-IDF с русскими стоп-словами (как у вас)
        russian_stop_words = {
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то',
            'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за',
            'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет',
            'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если',
            'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять',
            'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они',
            'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была',
            'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет',
            'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем',
            'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас',
            'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два',
            'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас',
            'про', 'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем',
            'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя',
            'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между'
        }

        self.vectorizer = TfidfVectorizer(
            max_features=7000,
            stop_words=list(russian_stop_words),
            ngram_range=(1, 3),
            min_df=1,
            max_df=0.9,
            sublinear_tf=True
        )

    def preprocess_text(self, text: str, preserve_keywords: bool = True) -> str:
        """Предобработка текста (как у вас)"""
        if not text:
            return ""

        text = text.lower()

        if preserve_keywords:
            text = re.sub(r'(\w+)-(\w+)', r'\1_\2', text)
            text = re.sub(r'[^\w\s.,!?;:()"\'_\-]', ' ', text)
            text = text.replace('_', '-')
        else:
            text = re.sub(r'[^\w\s]', ' ', text)

        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def extract_key_phrases(self, text: str, max_phrases: int = 10) -> List[str]:
        """Извлечение ключевых фраз (как у вас)"""
        if not text:
            return []

        text_clean = self.preprocess_text(text, preserve_keywords=True)
        words = text_clean.split()

        russian_stop_words = {
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то',
            'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за',
            'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет'
        }

        filtered_words = []
        for w in words:
            w_clean = w.strip('.,!?;:()"\'')
            if w_clean and w_clean not in russian_stop_words and len(w_clean) > 2:
                filtered_words.append(w_clean)

        if len(filtered_words) < 2:
            return filtered_words

        phrases = []
        phrases.extend([w for w in filtered_words if len(w) > 3])

        for i in range(len(filtered_words) - 1):
            bigram = f"{filtered_words[i]} {filtered_words[i + 1]}"
            if len(bigram) > 5:
                phrases.append(bigram)

        for i in range(len(filtered_words) - 2):
            trigram = f"{filtered_words[i]} {filtered_words[i + 1]} {filtered_words[i + 2]}"
            if len(trigram) > 8:
                phrases.append(trigram)

        phrase_counter = Counter(phrases)
        sorted_phrases = sorted(
            phrase_counter.items(),
            key=lambda x: (x[1], len(x[0].split())),
            reverse=True
        )

        return [phrase for phrase, count in sorted_phrases[:max_phrases]]

    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Вычисление семантической схожести (как у вас)"""
        if not text1 or not text2:
            return 0.0

        text1_clean = self.preprocess_text(text1)
        text2_clean = self.preprocess_text(text2)

        if len(text1_clean.split()) < 5 or len(text2_clean.split()) < 5:
            return self._calculate_jaccard_similarity(text1_clean, text2_clean)

        try:
            if hasattr(self.vectorizer, 'vocabulary_'):
                vec1 = self.vectorizer.transform([text1_clean])
                vec2 = self.vectorizer.transform([text2_clean])
            else:
                tfidf_matrix = self.vectorizer.fit_transform([text1_clean, text2_clean])
                vec1 = tfidf_matrix[0:1]
                vec2 = tfidf_matrix[1:2]

            similarity = cosine_similarity(vec1, vec2)[0][0]

            if len(text1_clean.split()) < 10 or len(text2_clean.split()) < 10:
                jaccard = self._calculate_jaccard_similarity(text1_clean, text2_clean)
                similarity = 0.6 * similarity + 0.4 * jaccard

            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return self._calculate_jaccard_similarity(text1_clean, text2_clean)

    def _calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity (как у вас)"""
        words1 = {w for w in text1.split() if len(w) > 2}
        words2 = {w for w in text2.split() if len(w) > 2}

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        return intersection / union if union > 0 else 0.0

    def find_semantic_matches(self, citation_text: str, source_content: str,
                              source_metadata: Optional[Dict[str, Any]] = None,
                              context_window: int = 500) -> List[Dict[str, Any]]:
        """
        ИСПРАВЛЕННАЯ версия: игнорирует слишком короткие строки
        """
        if not citation_text or not source_content:
            return []

        # 🔍 ДОПОЛНИТЕЛЬНАЯ ОТЛАДКА
        print(f"\n🔍 find_semantic_matches получил:")
        print(f"   Цитата: {citation_text[:100]}...")
        print(f"   Размер источника: {len(source_content)} символов")
        print(f"   Первые 200 символов источника: {source_content[:200]}")

        # Извлекаем ключевые фразы из цитаты
        key_phrases = self.extract_key_phrases(citation_text)
        print(f"   Ключевые фразы: {key_phrases[:10]}")

        # ВАЖНО: сначала разбиваем на абзацы, а потом на предложения внутри абзацев
        paragraphs = self._split_into_smart_paragraphs(source_content)

        # Для отладки
        logger.debug(f"📑 Создано {len(paragraphs)} абзацев для анализа:")
        for idx, para in enumerate(paragraphs[:5]):  # Показываем первые 5
            logger.debug(f"   Абзац {idx + 1}: {len(para.split())} слов, {len(para)} символов")
            logger.debug(f"      {para[:100]}...")

        matches = []

        for i, paragraph in enumerate(paragraphs):
            # ПРОПУСКАЕМ КОРОТКИЕ СТРОКИ (меньше 50 символов или 10 слов)
            word_count = len(paragraph.split())
            char_count = len(paragraph)

            if word_count < 10 or char_count < 50:
                logger.debug(f"🚫 Пропускаем слишком короткий фрагмент ({word_count} слов, {char_count} символов)")
                continue

            # Вычисляем схожесть
            similarity = self.calculate_semantic_similarity(citation_text, paragraph)

            # Проверяем наличие ключевых фраз
            key_phrase_matches = []
            paragraph_lower = paragraph.lower()

            for phrase in key_phrases:
                phrase_lower = phrase.lower()
                # Игнорируем слишком короткие фразы (1-2 буквы)
                if len(phrase_lower) < 3:
                    continue
                if phrase_lower in paragraph_lower:
                    key_phrase_matches.append(phrase)

            # Если фрагмент слишком короткий, но содержит много ключевых фраз - возможно, это заголовок
            if word_count < 20 and len(key_phrase_matches) >= 2:
                # Проверяем, не является ли это заголовком
                if self._looks_like_title(paragraph):
                    logger.debug(f"🚫 Пропускаем заголовок: {paragraph[:50]}...")
                    continue

            # Взвешенная оценка
            if similarity > 0.2 or len(key_phrase_matches) >= 2:
                # 🔍 Показываем найденное совпадение
                print(f"\n✅ НАЙДЕНО СОВПАДЕНИЕ #{len(matches) + 1}:")
                print(f"   Абзац {i + 1} ({word_count} слов, схожесть {similarity:.3f})")
                print(f"   Найдено фраз: {key_phrase_matches[:5]}")
                print(f"   Текст: {paragraph[:200]}...")

                matches.append({
                    'fragment': paragraph[:500] + ('...' if len(paragraph) > 500 else ''),
                    'fragment_full': paragraph,
                    'similarity_score': similarity,
                    'raw_similarity': similarity,
                    'key_phrase_matches': key_phrase_matches,
                    'key_phrase_count': len(key_phrase_matches),
                    'word_count': word_count,
                    'char_count': char_count,
                    'fragment_index': i
                })

        # Сортируем по количеству слов (чем длиннее, тем лучше) и схожести
        for match in matches:
            # Применяем штраф за название
            penalty = self._penalize_title_paragraph(match['fragment_full'])
            match['penalized_score'] = match['similarity_score'] * (1 - penalty)

        # Сортируем по штрафованному score
        matches.sort(key=lambda x: x['penalized_score'], reverse=True)

        print(f"\n📊 ВСЕГО НАЙДЕНО СОВПАДЕНИЙ: {len(matches)}")
        if matches:
            print(f"🏆 ЛУЧШЕЕ СОВПАДЕНИЕ:")
            print(f"   Слов: {matches[0]['word_count']}, схожесть: {matches[0]['similarity_score']:.3f}")
            print(f"   Фразы: {matches[0]['key_phrase_matches'][:5]}")
            print(f"   Текст: {matches[0]['fragment'][:200]}...")

        return matches

    def _looks_like_title(self, text: str) -> bool:
        """
        Улучшенная проверка, является ли текст заголовком
        """
        if not text or len(text) < 10:
            return True

        text_lower = text.lower()

        # Признаки заголовка
        title_indicators = [
            'глава', 'раздел', 'часть', 'параграф', '§',
            'учебник', 'пособие', 'издание', 'том',
            'введение', 'заключение', 'содержание',
            'приложение', 'список', 'литература',
            'библиография', 'references', 'index',
            'анна', 'михайловна', 'лопарева', 'автор'
        ]

        for indicator in title_indicators:
            if indicator in text_lower:
                return True

        # Если текст короткий и написан заглавными
        if len(text) < 100 and text.isupper():
            return True

        # Если текст содержит номер главы
        if re.search(r'глава\s+\d+|^\d+\.\d+', text_lower):
            return True

        # Если текст не содержит знаков препинания и короткий
        if len(text) < 100 and not any(p in text for p in '.!?;:'):
            return True

        return False

    def _split_into_smart_paragraphs(self, text: str) -> List[str]:
        """
        Разбивает текст на абзацы по пустым строкам (реальные абзацы)
        """
        # Разбиваем по двойным переносам строк (реальные абзацы)
        raw_paragraphs = re.split(r'\n\s*\n', text)

        paragraphs = []
        for para in raw_paragraphs:
            # Убираем лишние пробелы и переносы внутри абзаца
            lines = para.split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            if cleaned_lines:
                # Объединяем строки внутри абзаца в один текст
                paragraph_text = ' '.join(cleaned_lines)
                paragraphs.append(paragraph_text)

        # Если нет пустых строк, используем старый метод как fallback
        if len(paragraphs) <= 1:
            lines = text.split('\n')
            lines = [line.strip() for line in lines if line.strip()]

            if not lines:
                return []

            # Группируем по смыслу (каждые 5-7 строк)
            paragraphs = []
            current_paragraph = []

            for line in lines:
                current_paragraph.append(line)
                # Признак конца абзаца: строка заканчивается точкой и следующая начинается с заглавной
                if line.endswith(('.', '!', '?')) and len(current_paragraph) >= 3:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []

            if current_paragraph:
                if paragraphs and len(current_paragraph) < 3:
                    paragraphs[-1] = paragraphs[-1] + ' ' + ' '.join(current_paragraph)
                else:
                    paragraphs.append(' '.join(current_paragraph))

        # Для отладки
        print(f"\n📑 РАЗБИЕНИЕ НА АБЗАЦЫ:")
        for i, para in enumerate(paragraphs):
            words = len(para.split())
            chars = len(para)
            print(f"   Абзац {i + 1}: {words} слов, {chars} символов")
            print(f"      {para[:100]}...")

        return paragraphs

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Группирует строки в осмысленные абзацы (минимум 50 слов или 300 символов)
        """
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]

        if not lines:
            return []

        # Группируем строки в абзацы
        paragraphs = []
        current_paragraph = []
        current_length = 0

        for line in lines:
            current_paragraph.append(line)
            current_length += len(line)

            # Если накопили достаточно текста, сохраняем как абзац
            if current_length >= 300 or len(current_paragraph) >= 5:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
                current_length = 0

        # Добавляем остаток
        if current_paragraph:
            # Если остаток слишком маленький, присоединяем к предыдущему абзацу
            if paragraphs and current_length < 100:
                paragraphs[-1] = paragraphs[-1] + ' ' + ' '.join(current_paragraph)
            else:
                paragraphs.append(' '.join(current_paragraph))

        # Логируем для отладки
        logger.debug(f"📑 Создано {len(paragraphs)} абзацев:")
        for i, para in enumerate(paragraphs):
            logger.debug(f"   Абзац {i + 1}: {len(para.split())} слов, {len(para)} символов")
            logger.debug(f"      {para[:100]}...")

        return paragraphs

    def _remove_common_metadata_words(self, citation_text: str, paragraph: str) -> tuple:
        """
        Удаляет из рассмотрения общие слова из метаданных и возвращает очищенные версии
        """
        common_metadata_words = {
            'лопарева', 'бизнес', 'планирование', 'учебник', 'вузов', 'издание',
            'перераб', 'доп', 'анна', 'михайловна', 'глава', 'резюме', 'проекта'
        }

        # Очищаем цитату от общих слов
        citation_words = set(citation_text.lower().split())
        citation_filtered = citation_words - common_metadata_words

        # Очищаем абзац от общих слов
        paragraph_words = set(paragraph.lower().split())
        paragraph_filtered = paragraph_words - common_metadata_words

        return citation_filtered, paragraph_filtered

    def _find_position_in_source(self, full_text: str, fragment: str) -> Dict[str, int]:
        """Находит позицию фрагмента в исходном тексте"""
        try:
            start_pos = full_text.find(fragment[:100])  # Ищем начало фрагмента
            if start_pos >= 0:
                return {
                    'start': start_pos,
                    'end': start_pos + len(fragment)
                }
        except:
            pass
        return {'start': 0, 'end': 0}

    def verify_citation_in_source(self, citation_data: Dict[str, Any],
                                  source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        ИСПРАВЛЕННАЯ версия: проверяет реальный текст источника, исключая метаданные
        """
        citation_text = citation_data.get('full_paragraph', '') or citation_data.get('text', '')
        citation_context = citation_data.get('context', '')
        source_content = source_data.get('full_content', '')

        if not source_content:
            return {
                'verified': False,
                'confidence': 0,
                'reason': 'Текст источника недоступен для проверки',
                'matches': []
            }

        # Объединяем текст цитаты и контекст
        full_citation_text = f"{citation_text} {citation_context}".strip()
        if not full_citation_text:
            full_citation_text = citation_text

        # Подготавливаем метаданные для исключения
        source_metadata = {
            'title': source_data.get('title', ''),
            'authors': source_data.get('authors', []),
            'publisher': source_data.get('publisher', ''),
            'year': source_data.get('year', '')
        }

        # ========== УЛУЧШЕННАЯ ОБРАБОТКА ТЕКСТА ==========

        # 1. Извлекаем ТОЛЬКО реальный контент, удаляя метаданные
        clean_content = self._extract_main_content(source_content, source_metadata)

        # 2. Разбиваем на реальные абзацы (не по словам, а по структуре)
        paragraphs = self._split_into_paragraphs(clean_content)

        # 3. Извлекаем ключевые фразы из цитаты
        key_phrases = self.extract_key_phrases(full_citation_text, max_phrases=15)

        # 4. Создаем список стоп-слов из метаданных для фильтрации
        stop_words = self._get_stop_words_from_metadata(source_metadata)

        # 5. Анализируем каждый абзац
        best_match = None
        best_score = 0
        all_matches = []

        for paragraph in paragraphs:
            # Пропускаем слишком короткие абзацы
            if len(paragraph.split()) < 15 or len(paragraph) < 100:
                continue

            # Пропускаем абзацы, которые выглядят как метаданные
            if self._looks_like_title(paragraph) or self._is_metadata_paragraph(paragraph):
                continue

            # Вычисляем семантическую схожесть
            similarity = self.calculate_semantic_similarity(full_citation_text, paragraph)

            # Проверяем наличие ключевых фраз (исключая стоп-слова)
            paragraph_lower = paragraph.lower()
            meaningful_phrases = []

            for phrase in key_phrases:
                phrase_lower = phrase.lower()
                # Пропускаем фразы, состоящие только из стоп-слов
                if any(stop_word in phrase_lower for stop_word in stop_words):
                    continue
                if phrase_lower in paragraph_lower:
                    meaningful_phrases.append(phrase)

            # Взвешенная оценка
            phrase_score = len(meaningful_phrases) / max(len(key_phrases), 1) * 0.4
            similarity_score = similarity * 0.6

            total_score = phrase_score + similarity_score

            # Бонус за длину абзаца (чем длиннее, тем вероятнее, что это реальный текст)
            length_bonus = min(len(paragraph.split()) / 500, 0.2)
            total_score += length_bonus

            match_info = {
                'text': paragraph[:500] + ('...' if len(paragraph) > 500 else ''),
                'full_text': paragraph,
                'similarity': similarity,
                'phrase_matches': meaningful_phrases,
                'phrase_count': len(meaningful_phrases),
                'score': total_score,
                'word_count': len(paragraph.split())
            }

            all_matches.append(match_info)

            if total_score > best_score:
                best_score = total_score
                best_match = match_info

        # Сортируем все совпадения по убыванию
        all_matches.sort(key=lambda x: x['score'], reverse=True)

        # Определяем результат
        if best_match and best_score > 0.3:  # Порог уверенности
            confidence = min(best_score * 100, 95)

            # Определяем уровень верификации
            if confidence > 70:
                level = 'high'
            elif confidence > 50:
                level = 'medium'
            else:
                level = 'low'

            return {
                'verified': True,
                'confidence': round(confidence, 1),
                'verification_level': level,
                'reason': f'Найдено совпадение с уверенностью {round(confidence, 1)}%',
                'best_match': {
                    'text': best_match['text'],
                    'similarity': best_match['similarity'],
                    'key_phrases_matched': best_match['phrase_matches'],
                    'key_phrase_count': best_match['phrase_count'],
                    'word_count': best_match['word_count']
                },
                'all_matches': [
                    {
                        'text': m['text'][:200] + ('...' if len(m['text']) > 200 else ''),
                        'similarity': m['similarity'],
                        'key_phrases': m['phrase_matches'][:3],
                        'score': m['score']
                    }
                    for m in all_matches[:3]
                ],
                'analysis_details': {
                    'citation_length': len(full_citation_text),
                    'source_length': len(source_content),
                    'clean_content_length': len(clean_content),
                    'total_matches_found': len(all_matches),
                    'key_phrases_extracted': len(key_phrases)
                }
            }

        return {
            'verified': False,
            'confidence': 0,
            'reason': 'Совпадения не найдены в реальном тексте источника',
            'matches': []
        }

    def _extract_main_content(self, source_content: str, metadata: Dict[str, Any]) -> str:
        """
        Извлекает только реальный текст, удаляя метаданные
        """
        if not source_content:
            return ""

        # Получаем стоп-слова из метаданных
        stop_words = self._get_stop_words_from_metadata(metadata)

        # Разбиваем на строки
        lines = source_content.split('\n')
        lines = [line.strip() for line in lines if line.strip()]

        # Ищем начало реального текста
        content_start = 0
        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Пропускаем строки, состоящие только из стоп-слов
            words = line_lower.split()
            if words and all(word in stop_words for word in words):
                continue

            # Пропускаем строки с признаками метаданных
            if self._looks_like_title(line):
                continue

            # Если строка достаточно длинная и содержит знаки препинания
            if len(line) > 50 and any(p in line for p in '.!?;:'):
                content_start = i
                break

            # Если нашли начало главы/раздела
            if re.search(r'глава\s+\d+|^\d+\.\d+', line_lower):
                content_start = i
                break

        # Объединяем оставшиеся строки
        if content_start > 0:
            return '\n'.join(lines[content_start:])
        return source_content

    def _get_stop_words_from_metadata(self, metadata: Dict[str, Any]) -> set:
        """
        Создает набор стоп-слов из метаданных
        """
        stop_words = set()

        # Добавляем слова из названия
        if metadata.get('title'):
            title_words = re.findall(r'\w+', metadata['title'].lower())
            stop_words.update(title_words)

        # Добавляем фамилии авторов
        if metadata.get('authors'):
            for author in metadata['authors']:
                if isinstance(author, str):
                    author_words = re.findall(r'\w+', author.lower())
                    stop_words.update(author_words)

        # Добавляем общие слова из издательства
        if metadata.get('publisher'):
            publisher_words = re.findall(r'\w+', metadata['publisher'].lower())
            stop_words.update(publisher_words)

        # Добавляем год
        if metadata.get('year'):
            stop_words.add(str(metadata['year']))

        return stop_words

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Разбивает текст на абзацы по пустым строкам или логическим разделителям
        """
        # Сначала пробуем разбить по двойным переносам (реальные абзацы)
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # Если получилось больше 1 абзаца, возвращаем их
        if len(paragraphs) > 1:
            return paragraphs

        # Иначе разбиваем по предложениям и группируем
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        paragraphs = []
        current_paragraph = []
        current_length = 0

        for sentence in sentences:
            current_paragraph.append(sentence)
            current_length += len(sentence)

            # Если набрали достаточно текста (больше 300 символов или 3+ предложения)
            if current_length > 300 or len(current_paragraph) >= 3:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
                current_length = 0

        # Добавляем остаток
        if current_paragraph:
            if paragraphs and current_length < 100:
                paragraphs[-1] = paragraphs[-1] + ' ' + ' '.join(current_paragraph)
            else:
                paragraphs.append(' '.join(current_paragraph))

        return paragraphs

    def _determine_verification_level(self, match: Dict[str, Any]) -> str:
        """Определяет уровень верификации"""
        similarity = match.get('similarity_score', 0)
        key_phrases = match.get('key_phrase_count', 0)

        if similarity > 0.6 or (similarity > 0.4 and key_phrases >= 3):
            return 'high'
        elif similarity > 0.4 or key_phrases >= 2:
            return 'medium'
        elif similarity > 0.25 or key_phrases >= 1:
            return 'low'
        else:
            return 'very_low'

    def _is_metadata_paragraph(self, paragraph: str) -> bool:
        """
        Определяет, является ли абзац метаданными
        """
        if not paragraph or len(paragraph) < 20:
            return True

        paragraph_lower = paragraph.lower()

        # Паттерны метаданных
        metadata_patterns = [
            r'^анна|александр|владимир|иван|петр|сергей|дмитрий',
            r'лопарева|иванов|петров|сидоров|смирнов|кузнецов',
            r'учебник|пособие|издание|изд\.|издательство',
            r'минобрнауки|министерство|университет|академия|институт',
            r'санкт-петербург|москва|лэти|юургу|влгу',
        ]

        for pattern in metadata_patterns:
            if re.search(pattern, paragraph_lower):
                return True

        return False

    def debug_paragraph_splitting(self, source_content: str):
        """
        Подробно показывает, как разбивается текст на абзацы
        """
        print("\n" + "=" * 80)
        print("🔍 ДЕТАЛЬНАЯ ОТЛАДКА РАЗБИЕНИЯ ТЕКСТА")
        print("=" * 80)

        # Показываем исходный текст
        print(f"\n📄 ИСХОДНЫЙ ТЕКСТ ({len(source_content)} символов):")
        print("-" * 40)
        lines = source_content.split('\n')
        for i, line in enumerate(lines):
            if line.strip():
                print(f"  {i + 1}: '{line}'")

        # Показываем, как работает _split_into_smart_paragraphs
        print(f"\n📑 РАЗБИЕНИЕ НА АБЗАЦЫ:")
        print("-" * 40)

        # Используем тот же метод, что и в алгоритме
        paragraphs = self._split_into_smart_paragraphs(source_content)

        for i, para in enumerate(paragraphs):
            word_count = len(para.split())
            char_count = len(para)
            print(f"\n  Абзац {i + 1}:")
            print(f"    Слов: {word_count}, символов: {char_count}")
            print(f"    Текст: {para[:200]}..." if len(para) > 200 else f"    Текст: {para}")

            # Проверяем, проходит ли фильтр
            if word_count < 10 or char_count < 50:
                print(f"    ⚠️ НЕ ПРОХОДИТ фильтр (слишком короткий)")
            else:
                print(f"    ✅ ПРОХОДИТ фильтр")

        return paragraphs

    def debug_citation_comparison(self, citation_text: str, paragraphs: List[str]):
        """
        Подробно показывает сравнение цитаты с каждым абзацем
        """
        print("\n" + "=" * 80)
        print("🔍 ДЕТАЛЬНОЕ СРАВНЕНИЕ ЦИТАТЫ С АБЗАЦАМИ")
        print("=" * 80)

        print(f"\n📝 ЦИТАТА:")
        print(f"  {citation_text[:200]}...")

        # Извлекаем ключевые фразы из цитаты
        key_phrases = self.extract_key_phrases(citation_text)
        print(f"\n🔑 КЛЮЧЕВЫЕ ФРАЗЫ ИЗ ЦИТАТЫ:")
        for i, phrase in enumerate(key_phrases[:10]):
            print(f"  {i + 1}. '{phrase}'")

        print(f"\n📊 СРАВНЕНИЕ С КАЖДЫМ АБЗАЦЕМ:")
        print("-" * 80)

        for i, para in enumerate(paragraphs):
            word_count = len(para.split())
            char_count = len(para)

            # Пропускаем короткие абзацы
            if word_count < 10 or char_count < 50:
                continue

            print(f"\n📑 АБЗАЦ {i + 1} ({word_count} слов, {char_count} символов):")

            # Вычисляем схожесть
            similarity = self.calculate_semantic_similarity(citation_text, para)
            print(f"  📊 Семантическая схожесть: {similarity:.3f}")

            # Проверяем ключевые фразы
            para_lower = para.lower()
            found_phrases = []

            for phrase in key_phrases:
                phrase_lower = phrase.lower()
                if phrase_lower in para_lower:
                    found_phrases.append(phrase)
                    print(f"  ✅ Найдена фраза: '{phrase}'")

            if not found_phrases:
                print(f"  ❌ Ключевые фразы не найдены")

            # Показываем часть текста для проверки
            print(f"  📖 Текст абзаца:")
            print(f"    {para[:300]}...")
            print(f"  {'=' * 40}")

# Глобальный экземпляр для использования
semantic_matcher = FixedSemanticCitationMatcher(language='russian')