from typing import List, Dict, Any, Optional, Tuple
import re
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class MissingCitationChecker:
    """
    Проверяет, действительно ли цитата присутствует в указанном источнике.
    Использует несколько методов для повышения точности.
    """

    def __init__(self, min_confidence_threshold: float = 0.5):
        self.min_confidence = min_confidence_threshold
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            stop_words=['и', 'в', 'на', 'с', 'по', 'для', 'что', 'как']
        )

    def check_missing_citations(
            self,
            citations: List[Dict[str, Any]],
            source_contents: Dict[str, str],
            bibliography_matches: Dict[int, str]  # {citation_number: source_id}
    ) -> List[Dict[str, Any]]:
        """
        Для каждой цитаты проверяет, есть ли она в соответствующем источнике

        Args:
            citations: список цитат
            source_contents: словарь {source_id: текст_источника}
            bibliography_matches: словарь {номер_цитаты: id_источника}

        Returns:
            список проблем с отсутствующими цитатами
        """
        issues = []

        print(f"\n ПРОВЕРКА ОТСУТСТВУЮЩИХ В ИСТОЧНИКЕ ЦИТАТ")
        print(f"   Всего цитат: {len(citations)}")
        print(f"   Найдено соответствий библиографии: {len(bibliography_matches)}")

        for citation in citations:
            citation_num = citation.get('citation_number')
            if not citation_num:
                continue

            citation_text = citation.get('full_paragraph', '') or citation.get('text', '')
            citation_context = citation.get('context', '')

            # Объединяем текст цитаты и контекст
            full_citation = f"{citation_text} {citation_context}".strip()
            if not full_citation:
                continue

            # Получаем ID источника из сопоставления библиографии
            source_id = bibliography_matches.get(citation_num)

            if source_id and source_id in source_contents:
                source_content = source_contents[source_id]

                # Проверяем, есть ли цитата в источнике
                found, confidence, details = self._find_citation_in_source(
                    full_citation, source_content
                )

                if not found:
                    print(f"   ❌ Цитата [{citation_num}] не найдена в источнике {source_id}")
                    issues.append({
                        'type': 'citation_not_found_in_source',
                        'citation_number': citation_num,
                        'citation_text': full_citation[:200] + '...',
                        'source_id': source_id,
                        'source_title': self._get_source_title(source_id),
                        'confidence': confidence * 100,
                        'description': f'Цитата [{citation_num}] не найдена в указанном источнике',
                        'severity': 'high' if confidence < 0.3 else 'medium',
                        'details': details,
                        'suggestion': 'Проверьте, действительно ли эта цитата содержится в источнике'
                    })
                elif confidence < 0.7:
                    print(f"   ⚠️ Цитата [{citation_num}] найдена с низкой уверенностью ({confidence:.2f})")
                    issues.append({
                        'type': 'low_confidence_citation',
                        'citation_number': citation_num,
                        'citation_text': full_citation[:200] + '...',
                        'source_id': source_id,
                        'source_title': self._get_source_title(source_id),
                        'confidence': confidence * 100,
                        'description': f'Цитата [{citation_num}] найдена в источнике с низкой уверенностью ({confidence:.0f}%)',
                        'severity': 'medium',
                        'details': details,
                        'suggestion': 'Проверьте точность цитирования'
                    })
                else:
                    print(f"   Цитата [{citation_num}] найдена в источнике (уверенность: {confidence:.2f})")

        print(f"   Найдено проблем: {len([i for i in issues if i['type'] == 'citation_not_found_in_source'])}")
        print(f"   Проблем с низкой уверенностью: {len([i for i in issues if i['type'] == 'low_confidence_citation'])}")

        return issues

    def _find_citation_in_source(
            self,
            citation_text: str,
            source_content: str
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Ищет цитату в тексте источника, возвращает (найдено, уверенность, детали)
        """
        if not citation_text or not source_content:
            return False, 0.0, {}

        details = {
            'methods': {}
        }

        # 1. Точное совпадение
        exact_match = self._check_exact_match(citation_text, source_content)
        details['methods']['exact_match'] = exact_match

        if exact_match['found']:
            return True, 1.0, details

        # 2. Совпадение после очистки
        clean_match = self._check_clean_match(citation_text, source_content)
        details['methods']['clean_match'] = clean_match

        if clean_match['found']:
            return True, 0.95, details

        # 3. Поиск ключевых фраз
        phrase_matches = self._check_key_phrases(citation_text, source_content)
        details['methods']['phrase_matches'] = phrase_matches

        # 4. TF-IDF схожесть
        tfidf_similarity = self._calculate_tfidf_similarity(citation_text, source_content)
        details['methods']['tfidf_similarity'] = tfidf_similarity

        # 5. Совпадение предложений
        sentence_matches = self._check_sentence_matches(citation_text, source_content)
        details['methods']['sentence_matches'] = sentence_matches

        # Комбинируем результаты
        confidence = self._combine_confidence(
            exact_match['found'],
            clean_match['found'],
            phrase_matches,
            tfidf_similarity,
            sentence_matches
        )

        details['combined_confidence'] = confidence

        found = confidence >= self.min_confidence

        return found, confidence, details

    def _check_exact_match(self, citation: str, source: str) -> Dict[str, Any]:
        """Проверяет точное совпадение текста"""
        citation_clean = citation.strip()

        if citation_clean in source:
            return {
                'found': True,
                'text': citation_clean[:100] + '...' if len(citation_clean) > 100 else citation_clean,
                'position': source.find(citation_clean)
            }

        return {'found': False}

    def _check_clean_match(self, citation: str, source: str) -> Dict[str, Any]:
        """Проверяет совпадение после очистки текста"""
        # Убираем знаки препинания, лишние пробелы, приводим к нижнему регистру
        citation_clean = re.sub(r'[^\w\s]', '', citation.lower())
        citation_clean = re.sub(r'\s+', ' ', citation_clean).strip()

        source_clean = re.sub(r'[^\w\s]', '', source.lower())
        source_clean = re.sub(r'\s+', ' ', source_clean).strip()

        if citation_clean in source_clean:
            return {
                'found': True,
                'text': citation_clean[:100] + '...',
                'position': source_clean.find(citation_clean)
            }

        return {'found': False}

    def _check_key_phrases(self, citation: str, source: str, min_phrase_length: int = 4) -> Dict[str, Any]:
        """Проверяет наличие ключевых фраз"""
        # Разбиваем на фразы (по 3-4 слова)
        words = citation.split()
        phrases = []

        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i + 3])
            if len(phrase) > min_phrase_length * 3:  # Примерно 12+ символов
                phrases.append(phrase.lower())

        if not phrases:
            return {'found': False, 'matches': [], 'count': 0}

        source_lower = source.lower()
        matches = []

        for phrase in phrases:
            if phrase in source_lower:
                matches.append(phrase)

        match_ratio = len(matches) / len(phrases) if phrases else 0

        return {
            'found': len(matches) > 0,
            'matches': matches[:5],
            'count': len(matches),
            'total_phrases': len(phrases),
            'ratio': match_ratio
        }

    def _calculate_tfidf_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет TF-IDF схожесть двух текстов"""
        try:
            if not text1 or not text2:
                return 0.0

            # Очищаем тексты
            text1_clean = re.sub(r'[^\w\s]', ' ', text1.lower())
            text2_clean = re.sub(r'[^\w\s]', ' ', text2.lower())

            text1_clean = re.sub(r'\s+', ' ', text1_clean).strip()
            text2_clean = re.sub(r'\s+', ' ', text2_clean).strip()

            # Если тексты слишком короткие, используем другой метод
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
        """Вычисляет Jaccard similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def _check_sentence_matches(self, citation: str, source: str) -> Dict[str, Any]:
        """Проверяет совпадения отдельных предложений"""
        citation_sentences = self._split_into_sentences(citation)
        source_sentences = self._split_into_sentences(source)

        if not citation_sentences or not source_sentences:
            return {'found': False, 'matches': [], 'count': 0}

        matches = []

        for c_sent in citation_sentences:
            c_sent_clean = re.sub(r'[^\w\s]', '', c_sent.lower())
            c_sent_clean = re.sub(r'\s+', ' ', c_sent_clean).strip()

            if len(c_sent_clean) < 20:  # Слишком короткие предложения пропускаем
                continue

            for s_sent in source_sentences:
                s_sent_clean = re.sub(r'[^\w\s]', '', s_sent.lower())
                s_sent_clean = re.sub(r'\s+', ' ', s_sent_clean).strip()

                if c_sent_clean in s_sent_clean or s_sent_clean in c_sent_clean:
                    matches.append({
                        'citation_sentence': c_sent[:100],
                        'source_sentence': s_sent[:100]
                    })
                    break

        return {
            'found': len(matches) > 0,
            'matches': matches[:3],
            'count': len(matches),
            'total_sentences': len([s for s in citation_sentences if len(s) > 20])
        }

    def _combine_confidence(
            self,
            exact_match: bool,
            clean_match: bool,
            phrase_matches: Dict,
            tfidf_similarity: float,
            sentence_matches: Dict
    ) -> float:
        """Комбинирует результаты разных методов для получения общей уверенности"""
        confidence = 0.0

        # Точное совпадение - максимальная уверенность
        if exact_match:
            return 1.0

        # Совпадение после очистки - почти максимальная уверенность
        if clean_match:
            confidence += 0.9

        # Учитываем совпадение фраз
        if phrase_matches.get('found'):
            phrase_ratio = phrase_matches.get('ratio', 0)
            confidence += phrase_ratio * 0.5

        # Учитываем TF-IDF схожесть
        confidence += tfidf_similarity * 0.3

        # Учитываем совпадение предложений
        if sentence_matches.get('found'):
            sentence_ratio = sentence_matches.get('count', 0) / max(sentence_matches.get('total_sentences', 1), 1)
            confidence += sentence_ratio * 0.4

        return min(confidence, 1.0)

    def _split_into_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_source_title(self, source_id: str) -> str:
        """Получает название источника по ID"""
        # В реальности нужно получать из библиотеки
        return f"Source {source_id}"