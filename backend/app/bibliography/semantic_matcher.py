import re
import string
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Настройка логирования
logger = logging.getLogger(__name__)


class SemanticCitationMatcher:
    """
    Семантическое сопоставление цитат с текстом источника.
    Определяет, содержит ли источник текст, семантически похожий на цитату.
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
            max_features=5000,
            stop_words=list(russian_stop_words),
            ngram_range=(1, 2)
        )

    def preprocess_text(self, text: str) -> str:
        """Предобработка текста для семантического анализа"""
        if not text:
            return ""

        # Приведение к нижнему регистру
        text = text.lower()

        # Удаление специальных символов, но сохранение пунктуации внутри предложений
        text = re.sub(r'[^\w\s.,!?;:()\"\'\-]', ' ', text)

        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def extract_key_sentences(self, text: str, num_sentences: int = 5) -> List[str]:
        """Извлекает ключевые предложения из текста"""
        # Простая разбивка на предложения
        sentences = re.split(r'(?<=[.!?])\s+', text)

        if len(sentences) <= num_sentences:
            return sentences

        # Простой алгоритм извлечения ключевых предложений
        scored_sentences = []

        for i, sentence in enumerate(sentences):
            # Оценка предложения по длине и содержанию
            score = 0

            # Длинные предложения обычно более информативны
            words = sentence.split()
            if len(words) > 5 and len(words) < 50:
                score += 2

            # Предложения с цифрами часто важны
            if re.search(r'\d+', sentence):
                score += 1

            # Предложения с ключевыми словами
            key_terms = ['следовательно', 'таким образом', 'во-первых',
                         'во-вторых', 'вывод', 'результат', 'задача', 'цель']
            if any(term in sentence.lower() for term in key_terms):
                score += 2

            scored_sentences.append((score, sentence, i))

        # Сортируем по оценке и индексу (предпочтение ранним предложениям)
        scored_sentences.sort(key=lambda x: (x[0], -x[2]), reverse=True)

        # Возвращаем лучшие предложения в оригинальном порядке
        best_indices = sorted([idx for _, _, idx in scored_sentences[:num_sentences]])
        return [sentences[i] for i in best_indices]

    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет семантическую схожесть между двумя текстами с использованием TF-IDF и косинусного сходства"""
        if not text1 or not text2:
            return 0.0

        # Предобработка
        text1_clean = self.preprocess_text(text1)
        text2_clean = self.preprocess_text(text2)

        # Создание матрицы TF-IDF
        try:
            tfidf_matrix = self.vectorizer.fit_transform([text1_clean, text2_clean])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating TF-IDF similarity: {e}")

            # Fallback: Jaccard similarity
            return self._calculate_jaccard_similarity(text1_clean, text2_clean)

    def _calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity как fallback метод"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def find_semantic_matches(self, citation_text: str, source_content: str,
                              context_window: int = 300) -> List[Dict[str, Any]]:
        """
        Находит семантически похожие фрагменты в источнике для данной цитаты.

        Args:
            citation_text: Текст цитаты с контекстом
            source_content: Полный текст источника
            context_window: Размер окна для поиска совпадений

        Returns:
            Список совпадений с оценками схожести
        """
        if not citation_text or not source_content:
            return []

        # Извлекаем ключевые фразы из цитаты
        key_phrases = self._extract_key_phrases(citation_text)

        # Разбиваем источник на перекрывающиеся фрагменты
        fragments = self._create_text_fragments(source_content, context_window)

        matches = []

        for i, fragment in enumerate(fragments):
            # Вычисляем схожесть между цитатой и фрагментом
            similarity = self.calculate_semantic_similarity(citation_text, fragment)

            if similarity > 0.3:  # Порог схожести
                # Проверяем наличие ключевых фраз
                key_phrase_matches = []
                for phrase in key_phrases:
                    if phrase.lower() in fragment.lower():
                        key_phrase_matches.append(phrase)

                # Вычисляем позицию в исходном тексте
                start_pos = i * (context_window // 2)
                end_pos = min(start_pos + context_window, len(source_content))

                matches.append({
                    'fragment': fragment,
                    'similarity_score': similarity,
                    'key_phrase_matches': key_phrase_matches,
                    'position': {
                        'start': start_pos,
                        'end': end_pos
                    },
                    'fragment_index': i
                })

        # Сортируем по убыванию схожести
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)

        return matches

    def _extract_key_phrases(self, text: str, max_phrases: int = 5) -> List[str]:
        """Извлекает ключевые фразы из текста"""
        if not text:
            return []

        # Удаляем стоп-слова и короткие слова
        words = text.lower().split()
        russian_stop_words = {
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то',
            'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за',
            'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет'
        }
        words = [w for w in words if w not in russian_stop_words and len(w) > 2]

        # Создаем биграммы
        phrases = []

        # Биграммы
        for i in range(len(words) - 1):
            if words[i].isalpha() and words[i + 1].isalpha():
                phrases.append(f"{words[i]} {words[i + 1]}")

        # Подсчитываем частоту
        phrase_counter = Counter(phrases)

        # Возвращаем самые частые фразы
        return [phrase for phrase, _ in phrase_counter.most_common(max_phrases)]

    def _create_text_fragments(self, text: str, window_size: int = 300,
                               overlap: float = 0.5) -> List[str]:
        """Создает перекрывающиеся фрагменты текста для анализа"""
        if not text:
            return []

        fragments = []
        step = int(window_size * (1 - overlap))

        for i in range(0, len(text), step):
            fragment = text[i:i + window_size]
            if fragment.strip():
                fragments.append(fragment)

            if i + window_size >= len(text):
                break

        return fragments

    def verify_citation_in_source(self, citation_data: Dict[str, Any],
                                  source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной метод верификации цитаты в источнике.

        Args:
            citation_data: Данные цитаты (текст, контекст, номер)
            source_data: Данные источника (текст, метаданные)

        Returns:
            Результат верификации
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

        # Объединяем текст цитаты и контекст для лучшего анализа
        full_citation_text = f"{citation_text} {citation_context}"

        # Находим семантические совпадения
        semantic_matches = self.find_semantic_matches(full_citation_text, source_content)

        if not semantic_matches:
            return {
                'verified': False,
                'confidence': 0,
                'reason': 'Семантически похожие фрагменты не найдены',
                'matches': []
            }

        # Выбираем лучшее совпадение
        best_match = semantic_matches[0]
        confidence = min(best_match['similarity_score'] * 100, 95)

        # Определяем уровень верификации
        verification_level = self._determine_verification_level(best_match, citation_data)

        result = {
            'verified': confidence > 40,  # Порог верификации
            'confidence': confidence,
            'verification_level': verification_level,
            'best_match': {
                'text': best_match['fragment'][:500] + ('...' if len(best_match['fragment']) > 500 else ''),
                'similarity': best_match['similarity_score'],
                'position': best_match['position'],
                'key_phrases_matched': best_match['key_phrase_matches']
            },
            'all_matches': [
                {
                    'text': m['fragment'][:200] + ('...' if len(m['fragment']) > 200 else ''),
                    'similarity': m['similarity_score'],
                    'key_phrases': m['key_phrase_matches']
                }
                for m in semantic_matches[:3]  # Только топ-3 совпадения
            ],
            'analysis_details': {
                'citation_length': len(full_citation_text),
                'source_length': len(source_content),
                'total_matches_found': len(semantic_matches)
            }
        }

        return result

    def _determine_verification_level(self, match: Dict[str, Any],
                                      citation_data: Dict[str, Any]) -> str:
        """Определяет уровень верификации на основе качества совпадения"""
        similarity = match['similarity_score']
        key_phrases_matched = len(match.get('key_phrase_matches', []))

        if similarity > 0.7:
            return 'high'
        elif similarity > 0.5:
            return 'medium'
        elif similarity > 0.3 or key_phrases_matched >= 2:
            return 'low'
        else:
            return 'very_low'

    def batch_verify_citations(self, citations: List[Dict[str, Any]],
                               source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Пакетная верификация нескольких цитат для одного источника"""
        results = []
        verified_count = 0
        total_confidence = 0

        for i, citation in enumerate(citations):
            verification_result = self.verify_citation_in_source(citation, source_data)
            results.append({
                'citation_id': citation.get('id', f'cit_{i}'),
                'citation_number': citation.get('citation_number'),
                'citation_text_preview': citation.get('text', '')[:100],
                'verification': verification_result
            })

            if verification_result['verified']:
                verified_count += 1
                total_confidence += verification_result['confidence']

        avg_confidence = total_confidence / verified_count if verified_count > 0 else 0

        return {
            'source_id': source_data.get('id'),
            'source_title': source_data.get('title', 'Unknown'),
            'total_citations': len(citations),
            'verified_citations': verified_count,
            'verification_rate': verified_count / len(citations) if citations else 0,
            'average_confidence': avg_confidence,
            'results': results
        }


# Глобальный экземпляр для использования
semantic_matcher = SemanticCitationMatcher(language='russian')