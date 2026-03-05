from typing import List, Dict, Any, Optional, Tuple
import re
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class MisreferenceChecker:
    """
    Проверяет, соответствуют ли номера цитат реальным источникам.
    Например: в тексте ссылка [1], а на самом деле цитата из источника [2]
    """

    def __init__(self, similarity_threshold: float = 0.3):
        self.similarity_threshold = similarity_threshold
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words=['и', 'в', 'на', 'с', 'по', 'для', 'что', 'как', 'это']
        )

    def check_misreferences(
            self,
            citations: List[Dict[str, Any]],
            bibliography: List[Dict[str, Any]],
            source_contents: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Проверяет на некорректные ссылки

        Args:
            citations: список цитат с контекстом
            bibliography: список записей библиографии
            source_contents: словарь {source_id: текст_источника}

        Returns:
            список проблем с некорректными ссылками
        """
        issues = []

        print(f"\n ПРОВЕРКА НЕКОРРЕКТНЫХ ССЫЛОК")
        print(f"   Всего цитат: {len(citations)}")
        print(f"   Всего источников в библиотеке: {len(source_contents)}")

        for citation in citations:
            citation_num = citation.get('citation_number')
            if not citation_num:
                continue

            citation_text = citation.get('full_paragraph', '') or citation.get('text', '')
            if not citation_text:
                continue

            # Если у нас есть библиографическая запись под этим номером
            if citation_num <= len(bibliography):
                bib_entry = bibliography[citation_num - 1]
                bib_text = bib_entry.get('text', '')

                # Находим наиболее подходящий источник для этой цитаты
                best_match = self._find_best_source_match(
                    citation_text,
                    source_contents
                )

                if best_match and best_match['confidence'] > 0.5:
                    # Проверяем, совпадает ли найденный источник с тем, что в библиографии
                    expected_source_id = self._extract_source_id_from_bib(bib_text)

                    # Если ожидаемый источник не совпадает с найденным
                    if expected_source_id and expected_source_id != best_match['source_id']:
                        print(f"   Некорректная ссылка [{citation_num}]")
                        print(f"      Ожидаемый: {expected_source_id}")
                        print(f"      Фактический: {best_match['source_id']}")

                        issues.append({
                            'type': 'misreferenced_citation',
                            'citation_number': citation_num,
                            'citation_text': citation_text[:200] + '...',
                            'expected_source': bib_text[:100] + '...',
                            'expected_source_id': expected_source_id,
                            'actual_source': best_match['title'],
                            'actual_source_id': best_match['source_id'],
                            'confidence': best_match['confidence'] * 100,
                            'description': f'Цитата [{citation_num}] вероятно относится к источнику "{best_match["title"]}", а не к указанному в библиографии',
                            'severity': 'high',
                            'suggestion': 'Проверьте номер ссылки - возможно, она должна указывать на другой источник'
                        })

        print(f"   Найдено проблем: {len(issues)}")
        return issues

    def _find_best_source_match(
            self,
            citation_text: str,
            source_contents: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Находит наиболее подходящий источник для цитаты"""
        if not source_contents:
            return None

        best_match = None
        best_score = 0

        # Разбиваем цитату на предложения
        citation_sentences = self._split_into_sentences(citation_text)

        for source_id, content in source_contents.items():
            if not content:
                continue

            # Разбиваем источник на chunks
            chunks = self._split_into_chunks(content, chunk_size=300)

            for chunk in chunks:
                # Вычисляем схожесть разными методами

                # 1. Прямое совпадение текста
                exact_matches = self._check_exact_matches(citation_text, chunk)

                # 2. Совпадение предложений
                sentence_matches = self._check_sentence_matches(
                    citation_sentences, chunk
                )

                # 3. TF-IDF схожесть
                tfidf_score = self._calculate_tfidf_similarity(citation_text, chunk)

                # Комбинированная оценка
                combined_score = (
                        exact_matches * 0.3 +
                        sentence_matches * 0.4 +
                        tfidf_score * 0.3
                )

                if combined_score > best_score and combined_score > self.similarity_threshold:
                    best_score = combined_score
                    best_match = {
                        'source_id': source_id,
                        'title': self._get_source_title(source_id),  # Нужно получать из metadata
                        'confidence': combined_score,
                        'matched_chunk': chunk[:200]
                    }

        return best_match

    def _check_exact_matches(self, citation: str, chunk: str) -> float:
        """Проверяет точные совпадения текста"""
        citation_clean = self._clean_text(citation)
        chunk_clean = self._clean_text(chunk)

        # Ищем точные вхождения
        if citation_clean in chunk_clean:
            return 1.0

        # Ищем совпадения длинных фраз (>20 символов)
        words = citation_clean.split()
        for i in range(len(words) - 3):
            phrase = ' '.join(words[i:i + 4])
            if len(phrase) > 20 and phrase in chunk_clean:
                return 0.8

        return 0.0

    def _check_sentence_matches(
            self,
            citation_sentences: List[str],
            chunk: str
    ) -> float:
        """Проверяет совпадения отдельных предложений"""
        if not citation_sentences:
            return 0.0

        chunk_lower = chunk.lower()
        matches = 0

        for sentence in citation_sentences:
            sentence_clean = self._clean_text(sentence)
            if len(sentence_clean) > 20:  # Только длинные предложения
                if sentence_clean in chunk_lower:
                    matches += 1

        return matches / len(citation_sentences) if citation_sentences else 0

    def _calculate_tfidf_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет TF-IDF схожесть двух текстов"""
        try:
            if not text1 or not text2:
                return 0.0

            # Очищаем тексты
            text1_clean = self._clean_text(text1)
            text2_clean = self._clean_text(text2)

            # Если тексты слишком короткие, используем Jaccard
            if len(text1_clean.split()) < 5 or len(text2_clean.split()) < 5:
                return self._jaccard_similarity(text1_clean, text2_clean)

            # Вычисляем TF-IDF
            tfidf_matrix = self.vectorizer.fit_transform([text1_clean, text2_clean])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

            return float(similarity)

        except Exception as e:
            logger.error(f"Error calculating TF-IDF similarity: {e}")
            return 0.0

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет Jaccard similarity для коротких текстов"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def _extract_source_id_from_bib(self, bib_text: str) -> Optional[str]:
        """
        Пытается извлечь ID источника из библиографической записи
        В реальности нужно сравнивать с метаданными источников
        """
        # Здесь должна быть более сложная логика..
        # Пока возвращаем None
        return None

    def _get_source_title(self, source_id: str) -> str:
        """Получает название источника по ID"""
        # В реальности нужно получать из библиотеки
        return f"Source {source_id}"

    def _split_into_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _split_into_chunks(self, text: str, chunk_size: int = 300) -> List[str]:
        """Разбивает текст на перекрывающиеся chunks"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size // 2):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)

        return chunks

    def _clean_text(self, text: str) -> str:
        """Очищает текст для сравнения"""
        # Убираем номера цитат
        text = re.sub(r'\[\d+\]', '', text)
        # Приводим к нижнему регистру
        text = text.lower()
        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        return text