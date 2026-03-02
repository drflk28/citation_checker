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
    поиск и верификация цитат
    TF-IDF векторизация для семантического сравнения текстов
    Извлечение ключевых фраз для точного совпадения
    Фильтрация метаданных (исключает названия, ФИО авторов и т.д.)
    """

    def __init__(self, language: str = 'russian'):
        self.language = language

        # Инициализация TF-IDF с русскими стоп-словами
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
        """Предобработка текста (к нижнему регистру, удаление спец символов и тд)"""
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

    def extract_key_phrases(self, text: str, max_phrases: int = 15) -> List[str]:
        """Извлечение ключевых слов - ТОЛЬКО СЛОВА!"""
        if not text:
            return []

        text_clean = self.preprocess_text(text, preserve_keywords=True)
        words = text_clean.split()

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

        # ✅ ИЗВЛЕКАЕМ ТОЛЬКО СЛОВА ДЛИННЕЕ 3 СИМВОЛОВ
        important_words = []
        for w in words:
            w_clean = w.strip('.,!?;:()"\'')
            if (w_clean and
                    w_clean not in russian_stop_words and
                    len(w_clean) > 3 and
                    not w_clean.isdigit()):
                important_words.append(w_clean)

        # ✅ УБИРАЕМ ДУБЛИКАТЫ, но сохраняем порядок по частоте
        word_counter = Counter(important_words)

        # Сортируем по частоте (самые частые слова важнее)
        sorted_words = sorted(
            word_counter.items(),
            key=lambda x: (x[1], len(x[0])),
            reverse=True
        )

        result = [word for word, count in sorted_words[:max_phrases]]

        print(f"📊 EXTRACTED KEYWORDS: {len(result)}")
        print(f"   {result[:15]}")

        return result

    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        print(f"📏 CALCULATE SEMANTIC SIMILARITY")
        print(f"   Text1 length: {len(text1)} chars, {len(text1.split())} words")
        print(f"   Text2 length: {len(text2)} chars, {len(text2.split())} words")

        if not text1 or not text2:
            print("   ❌ Empty text")
            return 0.0

        text1_clean = self.preprocess_text(text1)
        text2_clean = self.preprocess_text(text2)

        print(f"   Clean text1: {text1_clean[:100]}...")
        print(f"   Clean text2: {text2_clean[:100]}...")

        if len(text1_clean.split()) < 5 or len(text2_clean.split()) < 5:
            print(f"   📊 Using Jaccard (short texts)")
            jaccard = self._calculate_jaccard_similarity(text1_clean, text2_clean)
            print(f"   📊 Jaccard similarity: {jaccard:.3f}")
            return jaccard

        try:
            if hasattr(self.vectorizer, 'vocabulary_'):
                print("   🔄 Using existing vectorizer")
                vec1 = self.vectorizer.transform([text1_clean])
                vec2 = self.vectorizer.transform([text2_clean])
            else:
                print("   🔄 Fitting new vectorizer")
                tfidf_matrix = self.vectorizer.fit_transform([text1_clean, text2_clean])
                vec1 = tfidf_matrix[0:1]
                vec2 = tfidf_matrix[1:2]

            similarity = cosine_similarity(vec1, vec2)[0][0]
            print(f"   📊 Cosine similarity: {similarity:.3f}")

            if len(text1_clean.split()) < 10 or len(text2_clean.split()) < 10:
                jaccard = self._calculate_jaccard_similarity(text1_clean, text2_clean)
                print(f"   📊 Jaccard similarity: {jaccard:.3f}")
                similarity = 0.6 * similarity + 0.4 * jaccard
                print(f"   📊 Combined similarity: {similarity:.3f}")

            return float(similarity)
        except Exception as e:
            print(f"   ❌ Error calculating similarity: {e}")
            import traceback
            traceback.print_exc()
            jaccard = self._calculate_jaccard_similarity(text1_clean, text2_clean)
            print(f"   📊 Fallback Jaccard: {jaccard:.3f}")
            return jaccard

    def _calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity = (пересечение множеств) / (объединение множеств)"""
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
        поиск совпадений
        """
        if not citation_text or not source_content:
            return []

        print(f"\n find_semantic_matches получил:")
        print(f"   Цитата: {citation_text[:100]}...")
        print(f"   Размер источника: {len(source_content)} символов")
        print(f"   Первые 200 символов источника: {source_content[:200]}")

        # Извлекаем ключевые фразы из цитаты
        key_phrases = self.extract_key_phrases(citation_text)
        print(f"   Ключевые фразы: {key_phrases[:10]}")

        # сначала разбиваем на абзацы, а потом на предложения внутри абзацев
        paragraphs = self._split_into_smart_paragraphs(source_content)

        # Для отладки
        logger.debug(f" Создано {len(paragraphs)} абзацев для анализа:")
        for idx, para in enumerate(paragraphs[:5]):  # Показываем первые 5
            logger.debug(f"   Абзац {idx + 1}: {len(para.split())} слов, {len(para)} символов")
            logger.debug(f"      {para[:100]}...")

        matches = []

        for i, paragraph in enumerate(paragraphs):
            # ПРОПУСКАЕМ КОРОТКИЕ СТРОКИ (меньше 50 символов или 10 слов)
            word_count = len(paragraph.split())
            char_count = len(paragraph)

            if word_count < 10 or char_count < 50:
                logger.debug(f" Пропускаем слишком короткий фрагмент ({word_count} слов, {char_count} символов)")
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
                    logger.debug(f" Пропускаем заголовок: {paragraph[:50]}...")
                    continue

            # Взвешенная оценка
            if similarity > 0.2 or len(key_phrase_matches) >= 2:
                # Показываем найденное совпадение
                print(f"\n НАЙДЕНО СОВПАДЕНИЕ #{len(matches) + 1}:")
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

        print(f"\n ВСЕГО НАЙДЕНО СОВПАДЕНИЙ: {len(matches)}")
        if matches:
            print(f" ЛУЧШЕЕ СОВПАДЕНИЕ:")
            print(f"   Слов: {matches[0]['word_count']}, схожесть: {matches[0]['similarity_score']:.3f}")
            print(f"   Фразы: {matches[0]['key_phrase_matches'][:5]}")
            print(f"   Текст: {matches[0]['fragment'][:200]}...")

        return matches

    def _looks_like_title(self, text: str) -> bool:
        """
        проверка, является ли текст заголовком
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
        ]

        # Проверяем на явные заголовки
        for indicator in title_indicators:
            if indicator in text_lower and len(text) < 100:
                return True

        # Если текст короткий и написан заглавными
        if len(text) < 100 and text.isupper():
            return True

        # Если текст содержит номер главы в начале
        if re.match(r'^(глава|раздел|часть)\s+\d+', text_lower):
            return True

        # Если текст очень короткий (меньше 30 символов) и не содержит знаков препинания
        if len(text) < 30 and not any(p in text for p in '.!?;:'):
            return True

        # НЕ считаем заголовком длинные тексты с содержанием
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
        print(f"\n РАЗБИЕНИЕ НА АБЗАЦЫ:")
        for i, para in enumerate(paragraphs):
            words = len(para.split())
            chars = len(para)
            print(f"   Абзац {i + 1}: {words} слов, {chars} символов")
            print(f"      {para[:100]}...")

        return paragraphs

    def _remove_common_metadata_words(self, citation_text: str, paragraph: str) -> tuple:
        """
        Позже переделать
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
        проверяет реальный текст источника, исключая метаданные
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

        print(f"\n🔍 ПРОВЕРКА ЦИТАТЫ:")
        print(f"   Текст цитаты: {full_citation_text[:200]}...")

        # Подготавливаем метаданные для исключения
        source_metadata = {
            'title': source_data.get('title', ''),
            'authors': source_data.get('authors', []),
            'publisher': source_data.get('publisher', ''),
            'year': source_data.get('year', '')
        }

        # ========== ОБРАБОТКА ТЕКСТА ==========

        # 1. Извлекаем реальный контент, удаляя метаданные
        clean_content = self._extract_main_content(source_content, source_metadata)
        print(f"\n📄 ОЧИЩЕННЫЙ КОНТЕНТ:")
        print(f"   Длина: {len(clean_content)} символов")
        print(f"   Первые 200 символов: {clean_content[:200]}...")

        # 2. Разбиваем на реальные абзацы
        paragraphs = self._split_into_paragraphs(clean_content)
        print(f"\n📑 НАЙДЕНО АБЗАЦЕВ: {len(paragraphs)}")

        # 3. Извлекаем ключевые слова из цитаты (ТОЛЬКО СЛОВА, без фраз)
        key_words = self.extract_keywords_only(full_citation_text, max_words=15)
        print(f"\n📊 КЛЮЧЕВЫЕ СЛОВА ИЗ ЦИТАТЫ: {len(key_words)}")
        for i, word in enumerate(key_words[:10]):
            print(f"   {i + 1}. '{word}'")

        # 4. Создаем список стоп-слов из метаданных
        stop_words = self._get_stop_words_from_metadata(source_metadata)
        print(f"\n🚫 СТОП-СЛОВА ИЗ МЕТАДАННЫХ: {len(stop_words)}")
        print(f"   {list(stop_words)[:10]}...")

        # 5. Анализируем каждый абзац
        best_match = None
        best_score = 0
        all_matches = []

        # Множество для сбора ВСЕХ найденных слов из ВСЕХ абзацев
        all_found_words = set()

        # Если нет абзацев, создаем хотя бы один из всего текста
        if not paragraphs and clean_content.strip():
            paragraphs = [clean_content]
            print(f"\n⚠️ Нет абзацев, используем весь текст как один абзац")

        for i, paragraph in enumerate(paragraphs):
            print(f"\n--- АБЗАЦ {i + 1}/{len(paragraphs)} ---")
            print(f"   Длина: {len(paragraph.split())} слов, {len(paragraph)} символов")
            print(f"   Текст: {paragraph[:150]}...")

            # Пропускаем слишком короткие абзацы
            word_count = len(paragraph.split())
            char_count = len(paragraph)

            if word_count < 15 or char_count < 100:
                print(f"   ⚠️ ПРОПУЩЕН: слишком короткий ({word_count} слов, {char_count} символов)")
                continue

            # Пропускаем абзацы, которые выглядят как метаданные
            if self._looks_like_title(paragraph):
                print(f"   ⚠️ ПРОПУЩЕН: похож на заголовок")
                continue
            if self._is_metadata_paragraph(paragraph):
                print(f"   ⚠️ ПРОПУЩЕН: похож на метаданные")
                continue

            print(f"   ✅ ПРОШЕЛ фильтры")

            # Вычисляем семантическую схожесть
            similarity = self.calculate_semantic_similarity(full_citation_text, paragraph)
            print(f"   📊 СЕМАНТИЧЕСКАЯ СХОЖЕСТЬ: {similarity:.3f}")

            # Проверяем наличие ключевых слов (исключая стоп-слова)
            paragraph_lower = paragraph.lower()
            found_words_in_paragraph = []

            for word in key_words:
                word_lower = word.lower()
                # Убрали фильтрацию по стоп-словам для ключевых слов!
                if word_lower in paragraph_lower:
                    found_words_in_paragraph.append(word)
                    all_found_words.add(word)

            # Выводим найденные слова в этом абзаце
            print(f"   🔍 НАЙДЕНО СЛОВ В ЭТОМ АБЗАЦЕ: {len(found_words_in_paragraph)}/{len(key_words)}")
            if found_words_in_paragraph:
                print(f"      Примеры: {found_words_in_paragraph[:10]}")

            # РАСЧЕТ ИТОГОВОГО SCORE для этого абзаца
            word_ratio = len(found_words_in_paragraph) / max(len(key_words), 1)

            if similarity > 0:
                word_score = word_ratio * 0.4
                similarity_score = similarity * 0.6
                total_score = word_score + similarity_score
                print(f"   📊 WORD SCORE: {word_score:.3f} ({len(found_words_in_paragraph)}/{len(key_words)} слов)")
                print(f"   📊 SIMILARITY SCORE: {similarity_score:.3f} (similarity={similarity:.3f})")
            else:
                # Если семантика не работает, используем только ключевые слова
                total_score = word_ratio
                print(
                    f"   📊 USING ONLY KEYWORDS: {total_score:.3f} ({len(found_words_in_paragraph)}/{len(key_words)} слов)")

            print(f"   📊 ИТОГОВЫЙ SCORE ДЛЯ АБЗАЦА: {total_score:.3f}")

            # Сохраняем информацию о совпадении
            match_info = {
                'text': paragraph[:500] + ('...' if len(paragraph) > 500 else ''),
                'full_text': paragraph,
                'similarity': similarity,
                'word_matches': found_words_in_paragraph,
                'word_count': len(found_words_in_paragraph),
                'score': total_score,
                'paragraph_word_count': word_count
            }

            all_matches.append(match_info)

            if total_score > best_score:
                best_score = total_score
                best_match = match_info
                print(f"   🎯 НОВЫЙ ЛУЧШИЙ SCORE: {best_score:.3f}")

        # ПОСЛЕ цикла по всем абзацам - выводим общую статистику
        total_found_words = len(all_found_words)
        print(f"\n📊 ВСЕГО НАЙДЕНО УНИКАЛЬНЫХ СЛОВ: {total_found_words}/{len(key_words)}")
        if all_found_words:
            print(f"   Найденные слова: {sorted(list(all_found_words))[:15]}")

        # Сортируем все совпадения по убыванию
        all_matches.sort(key=lambda x: x['score'], reverse=True)

        print(f"\n📊 ВСЕГО НАЙДЕНО СОВПАДЕНИЙ (абзацев): {len(all_matches)}")
        print(f"🏆 ЛУЧШИЙ SCORE: {best_score:.3f}")

        # ОПРЕДЕЛЯЕМ РЕЗУЛЬТАТ
        if best_match and best_score > 0.05:  # Порог 5%
            confidence = min(best_score * 100, 95)

            # Определяем уровень верификации
            if confidence > 70:
                level = 'high'
            elif confidence > 50:
                level = 'medium'
            else:
                level = 'low'

            print(f"\n✅ ВЕРИФИКАЦИЯ УСПЕШНА!")
            print(f"   Уверенность: {confidence:.1f}%")
            print(f"   Найдено уникальных слов: {total_found_words}/{len(key_words)}")

            return {
                'verified': True,
                'confidence': round(confidence, 1),
                'verification_level': level,
                'reason': f'Найдено совпадение с уверенностью {round(confidence, 1)}%',
                'best_match': {
                    'text': best_match['text'],
                    'similarity': best_match['similarity'],
                    'key_words_matched': best_match['word_matches'],
                    'key_word_count': best_match['word_count'],
                    'word_count': best_match['paragraph_word_count']
                },
                'all_matches': [
                    {
                        'text': m['text'][:200] + ('...' if len(m['text']) > 200 else ''),
                        'similarity': m['similarity'],
                        'key_words': m['word_matches'][:3],
                        'score': m['score']
                    }
                    for m in all_matches[:3]
                ],
                'analysis_details': {
                    'citation_length': len(full_citation_text),
                    'source_length': len(source_content),
                    'clean_content_length': len(clean_content),
                    'total_matches_found': len(all_matches),
                    'key_words_extracted': len(key_words),
                    'key_words_found_total': total_found_words,
                    'paragraphs_analyzed': len(paragraphs)
                }
            }

        print(f"\n❌ ВЕРИФИКАЦИЯ НЕ УДАЛАСЬ")
        print(f"   Причина: best_score={best_score:.3f} < 0.05")

        return {
            'verified': False,
            'confidence': 0,
            'reason': 'Совпадения не найдены в реальном тексте источника',
            'best_match': best_match,
            'all_matches': all_matches[:3] if all_matches else [],
            'analysis_details': {
                'citation_length': len(full_citation_text),
                'source_length': len(source_content),
                'clean_content_length': len(clean_content),
                'total_matches_found': len(all_matches),
                'key_words_extracted': len(key_words),
                'key_words_found_total': len(all_found_words),
                'paragraphs_analyzed': len(paragraphs)
            }
        }

    def extract_keywords_only(self, text: str, max_words: int = 20) -> List[str]:
        """Извлекает только ключевые слова (без фраз) - УЛУЧШЕННАЯ ВЕРСИЯ"""
        if not text:
            return []

        # Убираем номер цитаты в квадратных скобках
        text = re.sub(r'\[\d+\]', '', text)

        text_clean = self.preprocess_text(text, preserve_keywords=True)
        words = text_clean.split()

        # Расширенный список стоп-слов
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
            'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между',
            # Добавляем служебные слова
            'данные', 'этого', 'раздела', 'получены', 'это', 'что', 'как', 'так', 'также'
        }

        # Извлекаем ВСЕ слова длиннее 2 символов
        important_words = []
        for w in words:
            w_clean = w.strip('.,!?;:()"\'')
            if (w_clean and
                    w_clean not in russian_stop_words and
                    len(w_clean) > 2 and  # ← уменьшили с 3 до 2
                    not w_clean.isdigit()):
                important_words.append(w_clean)

        # Считаем частоту
        word_counter = Counter(important_words)

        # Сортируем по частоте (самые частые - важнее)
        sorted_words = sorted(
            word_counter.items(),
            key=lambda x: (x[1], len(x[0])),
            reverse=True
        )

        result = [word for word, count in sorted_words[:max_words]]

        print(f"📊 EXTRACTED KEYWORDS: {len(result)}")
        print(f"   {result[:15]}")

        return result

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
        """Определяет уровень верификации (удалить?)"""
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

        # Паттерны метаданных - только для очень коротких текстов
        if len(paragraph) < 50:
            metadata_patterns = [
                r'^анна|александр|владимир|иван|петр|сергей|дмитрий',
                r'лопарева|иванов|петров|сидоров|смирнов|кузнецов',
                r'учебник|пособие|издание|изд\.|издательство',
                r'минобрнауки|министерство|университет|академия|институт',
            ]

            for pattern in metadata_patterns:
                if re.search(pattern, paragraph_lower):
                    return True

        return False

# Глобальный экземпляр для использования
semantic_matcher = FixedSemanticCitationMatcher(language='russian')