import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../css/CitationSourceVerifier.css';

const CitationSourceVerifier = ({ documentId, analysis }) => {
    const [verificationResults, setVerificationResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedResult, setSelectedResult] = useState(null);
    const [progress, setProgress] = useState(0);
    const [librarySources, setLibrarySources] = useState([]);

    // Загружаем источники из библиотеки
    useEffect(() => {
        loadLibrarySources();
    }, []);

    // Загружаем библиографию из анализа
    const bibliography = analysis?.bibliography_entries || [];

    // Загружаем цитаты из анализа
    const citations = analysis?.citations || [];

    const loadLibrarySources = async () => {
        try {
            const response = await axios.get('http://localhost:8001/api/library/sources');
            if (response.data.success) {
                setLibrarySources(response.data.sources || []);
            }
        } catch (error) {
            console.error('Error loading library sources:', error);
        }
    };

    const verifyAllCitations = async () => {
    setLoading(true);
    setVerificationResults([]);
    setProgress(0);

    try {
        const matchedPairs = matchCitationsWithSources(citations, bibliography);
        console.log('Найдено пар для проверки:', matchedPairs.length);

        if (matchedPairs.length === 0) {
            alert('Нет пар для проверки. Убедитесь, что в документе есть цитаты и библиография.');
            setLoading(false);
            return;
        }

        const results = [];
        for (let i = 0; i < matchedPairs.length; i++) {
            const pair = matchedPairs[i];

            // Обновляем прогресс
            setProgress(Math.round(((i + 1) / matchedPairs.length) * 100));

            try {
                // Таймаут для каждой проверки
                const timeoutPromise = new Promise((_, reject) =>
                    setTimeout(() => reject(new Error(`Таймаут проверки пары ${i + 1}/${matchedPairs.length}`)), 10000)
                );

                const verificationPromise = verifyCitationSourcePair(pair);
                const result = await Promise.race([verificationPromise, timeoutPromise]);

                if (result) {
                    results.push(result);
                    setVerificationResults([...results]); // Постепенное обновление UI
                }
            } catch (pairError) {
                console.error(`Ошибка проверки пары ${i + 1}:`, pairError);
                // Добавляем запись об ошибке
                results.push({
                    citation_number: pair.citation_number,
                    citation_text: pair.citation?.text || 'Нет текста',
                    source_title: pair.source?.text?.substring(0, 100) || 'Неизвестный источник',
                    verification: {
                        found: false,
                        reason: `Ошибка проверки: ${pairError.message}`,
                        confidence: 0
                    },
                    has_source_content: false
                });
                setVerificationResults([...results]);
            }
        }

        setProgress(100);
        showVerificationSummary(results);

    } catch (error) {
        console.error('Ошибка верификации:', error);
        alert(`Ошибка при проверке: ${error.message}`);
    } finally {
        setLoading(false);
        setProgress(0);
    }
};

    const matchCitationsWithSources = (citations, bibliography) => {
        const pairs = [];

        // Ищем в библиографии источники, упомянутые в цитатах
        citations.forEach(citation => {
            // Извлекаем номер цитаты
            const citationNumber = extractCitationNumber(citation.text);

            if (citationNumber !== null) {
                // Ищем источник с этим номером в библиографии
                const sourceIndex = citationNumber - 1; // [1] соответствует индексу 0

                if (sourceIndex >= 0 && sourceIndex < bibliography.length) {
                    const source = bibliography[sourceIndex];

                    pairs.push({
                        citation: citation,
                        citation_number: citationNumber,
                        source: source,
                        source_text: source.text,
                        source_metadata: source.online_metadata || source.library_match
                    });
                } else {
                    console.log(`Не найден источник для цитаты [${citationNumber}]`);
                }
            }
        });

        return pairs;
    };

    const verifyCitationSourcePair = async (pair) => {
    console.log(`🔍 Начинаем проверку пары: цитата [${pair.citation_number}]`);

    try {
        const { citation, source, citation_number } = pair;

        // Получаем полный текст цитаты
        const getCitationText = () => {
            // Пробуем разные поля в порядке приоритета
            const possibleFields = [
                citation.context,
                citation.full_paragraph,
                citation.text
            ];

            for (const field of possibleFields) {
                if (field && field.trim() !== '' && !/^\[\d+\]$/.test(field.trim())) {
                    return field;
                }
            }

            return `[${citation_number}]`;
        };

        const full_citation_text = getCitationText();
        console.log(`   📝 Текст цитаты: "${full_citation_text.substring(0, 100)}..."`);

        // Получаем текст источника из библиотеки
        let sourceContent = '';
        let sourceTitle = '';
        let sourceId = null;

        console.log(`   🔍 Проверяем библиотечный источник:`, source.library_match);

        // Пробуем найти источник в библиотеке
        if (source.library_match?.source_id) {
            sourceId = source.library_match.source_id;
            console.log(`   📚 Источник найден в библиотеке: ${sourceId}`);

            try {
                const response = await axios.get(
                    `http://localhost:8001/api/library/sources/${sourceId}/full-content`,
                    { timeout: 10000 }
                );

                console.log(`   📡 Ответ API:`, response.status);

                if (response.data.success) {
                    sourceContent = response.data.full_content || '';
                    sourceTitle = response.data.title || source.text?.substring(0, 100) || 'Источник из библиотеки';
                    console.log(`   ✅ Получен контент длиной: ${sourceContent.length}`);
                } else {
                    console.log(`   ❌ API вернул ошибку:`, response.data.message);
                }
            } catch (apiError) {
                console.error(`   ❌ Ошибка API запроса:`, apiError.message);
            }
        }
        // Если нет library_match, проверяем online_metadata
        else if (source.online_metadata?.title) {
            sourceTitle = source.online_metadata.title;
            console.log(`   🌐 Используем онлайн источник: ${sourceTitle}`);
        }
        // Если ничего нет, используем текст из библиографии
        else {
            sourceTitle = source.text?.substring(0, 100) || 'Неизвестный источник';
            console.log(`   📄 Используем текст из библиографии: ${sourceTitle}`);
        }

        // Проверяем, содержит ли источник эту цитату
        // ИСПРАВЛЕНО: передаем full_citation_text вместо citation.context
        const verificationResult = await checkCitationInSource(
            full_citation_text,  // ← было citation.context, теперь full_citation_text
            sourceContent,
            sourceTitle
        );

        return {
            citation_number: citation_number,
            citation_text: full_citation_text,
            source_title: sourceTitle,
            source_content: sourceContent,
            source_id: sourceId,
            verification: verificationResult,
            has_source_content: sourceContent.length > 0
        };

    } catch (error) {
        console.error(`❌ Ошибка в verifyCitationSourcePair:`, error);
        return null;
    }
};

    const checkCitationInSource = async (citationText, sourceContent, sourceTitle) => {
    if (!sourceContent) {
        return {
            found: false,
            reason: 'Нет доступа к тексту источника',
            confidence: 0
        };
    }

    // Проверяем входные данные
    if (!citationText || typeof citationText !== 'string') {
        console.error('checkCitationInSource: citationText is invalid', citationText);
        return {
            found: false,
            reason: 'Некорректный текст цитаты',
            confidence: 0
        };
    }

    if (!sourceTitle || typeof sourceTitle !== 'string') {
        sourceTitle = ''; // Если нет названия, используем пустую строку
    }

    // 1. Извлекаем ключевые слова из текста цитаты
    const keywords = extractKeywordsFromContext(citationText); // ← используем citationText вместо context

    // 2. Создаем копию контента без названия для поиска
    let searchableContent = sourceContent;

    // Удаляем название из поиска, если оно есть в начале текста
    if (sourceTitle && typeof sourceTitle === 'string') {
        const titleWords = sourceTitle.split(' ').filter(w => w && w.length > 3);
        titleWords.forEach(word => {
            if (word && typeof word === 'string') {
                // Заменяем слова из названия на пустоту, чтобы они не учитывались
                try {
                    const regex = new RegExp(word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
                    searchableContent = searchableContent.replace(regex, '');
                } catch (e) {
                    console.error('Error creating regex for word:', word, e);
                }
            }
        });
    }

    // 3. Ищем ключевые слова в источнике
    const keywordMatches = findKeywordMatches(keywords, searchableContent);

    if (keywordMatches.length === 0) {
        // Если в основном тексте не найдено, проверяем исключая стоп-слова
        const importantKeywords = keywords.filter(k =>
            !['бизнес', 'планирование', 'учебник', 'вузов', 'лопарева'].includes(k)
        );

        if (importantKeywords.length > 0) {
            const importantMatches = findKeywordMatches(importantKeywords, searchableContent);
            if (importantMatches.length === 0) {
                return {
                    found: false,
                    reason: 'Ключевые слова цитаты не найдены в основном тексте источника',
                    confidence: 0
                };
            }
        } else {
            return {
                found: false,
                reason: 'Ключевые слова цитаты не найдены в источнике',
                confidence: 0
            };
        }
    }

    // 4. Оцениваем уверенность на основе количества совпадений
    const confidence = calculateConfidence(keywordMatches.length, keywords.length);

    // 5. Находим лучший фрагмент текста (исключая название)
    const bestSnippet = findBestSnippet(searchableContent, keywordMatches);

    return {
        found: true,
        confidence: Math.min(confidence, 100),
        match_type: 'semantic',
        keyword_matches: keywordMatches,
        best_snippet: bestSnippet,
        total_keywords_found: keywordMatches.length,
        total_keywords_searched: keywords.length
    };
};

    const extractKeywordsFromContext = (text) => {
    if (!text || typeof text !== 'string') {
        console.warn('extractKeywordsFromContext: text is invalid', text);
        return [];
    }

    // Убираем стоп-слова
    const stopWords = new Set([
        'и', 'в', 'на', 'по', 'с', 'из', 'для', 'что', 'как', 'это', 'то',
        'же', 'все', 'его', 'их', 'от', 'о', 'у', 'к', 'за', 'так', 'но',
        'а', 'или', 'бы', 'ли', 'же', 'ну', 'вот', 'не', 'ни', 'да', 'нет'
    ]);

    // Извлекаем слова длиной > 3 символов
    const words = text.toLowerCase().match(/[а-яё]{4,}/g) || [];

    // Фильтруем стоп-слова
    const keywords = words.filter(word => !stopWords.has(word));

    // Убираем дубликаты
    return [...new Set(keywords)].slice(0, 10); // Берем до 10 ключевых слов
};
    const findKeywordMatches = (keywords, sourceContent) => {
        const sourceLower = sourceContent.toLowerCase();
        const matches = [];

        keywords.forEach(keyword => {
            if (sourceLower.includes(keyword)) {
                matches.push({
                    keyword: keyword,
                    positions: findAllPositions(sourceLower, keyword)
                });
            }
        });

        return matches;
    };

    const findAllPositions = (text, word) => {
    const positions = [];
    let index = text.indexOf(word);
    let count = 0; // Счетчик для предотвращения бесконечного цикла

    while (index !== -1 && count < 100) { // Ограничиваем 100 совпадениями
        positions.push(index);
        index = text.indexOf(word, index + 1);
        count++;
    }

    return positions;
};

const calculateConfidence = (foundCount, totalCount) => {
    if (totalCount === 0) return 0;

    // Базовый процент совпадений
    const matchRatio = foundCount / totalCount;

    // Усиливаем оценку при хорошем совпадении
    if (matchRatio > 0.7) return 90;
    if (matchRatio > 0.5) return 75;
    if (matchRatio > 0.3) return 60;
    if (matchRatio > 0.2) return 40;
    return 20;
};

const findBestSnippet = (sourceContent, keywordMatches) => {
    if (keywordMatches.length === 0 || !sourceContent) {
        return sourceContent.substring(0, 300) + '...';
    }

    // Упрощаем логику для больших текстов
    const positions = keywordMatches.flatMap(match => match.positions.slice(0, 10)); // Берем только первые 10 позиций

    if (positions.length === 0) {
        return sourceContent.substring(0, 300) + '...';
    }

    // Быстрый алгоритм - берем первую кластерную позицию
    positions.sort((a, b) => a - b);

    let bestStart = positions[0];
    let bestEnd = positions[0];
    let maxClusterSize = 1;
    let currentClusterSize = 1;

    for (let i = 1; i < Math.min(positions.length, 100); i++) { // Ограничиваем до 100 позиций
        if (positions[i] - positions[i-1] < 500) { // Если позиции близко
            currentClusterSize++;
            if (currentClusterSize > maxClusterSize) {
                maxClusterSize = currentClusterSize;
                bestStart = positions[i - currentClusterSize + 1];
                bestEnd = positions[i];
            }
        } else {
            currentClusterSize = 1;
        }
    }

    // Вырезаем фрагмент с контекстом
    const snippetStart = Math.max(0, bestStart - 150);
    const snippetEnd = Math.min(sourceContent.length, bestEnd + 150);

    let snippet = sourceContent.substring(snippetStart, snippetEnd);
    if (snippetStart > 0) snippet = '...' + snippet;
    if (snippetEnd < sourceContent.length) snippet = snippet + '...';

    return snippet;
};

    const extractCitationNumber = (text) => {
        if (!text) return null;
        const match = text.match(/\[(\d+)\]/);
        return match ? parseInt(match[1]) : null;
    };

    const showVerificationSummary = (results) => {
        const verified = results.filter(r => r?.verification?.found).length;
        const total = results.length;

        alert(`✅ Проверено ${total} пар цитат и источников\n` +
              `📊 Найдено соответствий: ${verified}\n` +
              `❌ Не найдено: ${total - verified}`);
    };

    const renderVerificationResult = (result, index) => {
    const { verification, citation_text, source_title, has_source_content, source_content } = result;

    return (
        <div key={index} className={`verification-result ${verification.found ? 'result-verified' : 'result-not-found'}`}>
            <div className="result-header">
                <div className="citation-info">
                    <span className="citation-number">
                        Цитата [{result.citation_number}]
                    </span>
                    <span className="source-title">
                        Источник: {source_title}
                    </span>
                </div>
                <div className={`status-badge ${verification.found ? 'status-success' : 'status-error'}`}>
                    {verification.found ? '✅ Найдено' : '❌ Не найдено'}
                </div>
            </div>

            <div className="citation-preview">
                <strong>Контекст цитаты:</strong>
                <p className="citation-text">{citation_text || 'Нет контекста'}</p>
            </div>

            {verification.found ? (
                <div className="match-details">
                    <p className="confidence">
                        <strong>Уверенность:</strong> {verification.confidence}%
                    </p>
                    <p className="match-type">
                        <strong>Совпадений:</strong> {verification.total_keywords_found} из {verification.total_keywords_searched} ключевых слов
                    </p>

                    <div className="semantic-match">
                        <strong>Релевантный фрагмент источника:</strong>
                        <div className="source-snippet">
                            {/* ИСПРАВЛЕНО: используем реальный текст источника */}
                            {verification.found && verification.best_snippet && verification.best_snippet !== source_title ? (
                                // Если есть найденный фрагмент и он не равен названию
                                verification.best_snippet
                            ) : (
                                // Если нет фрагмента или это название, показываем первые 500 символов источника
                                source_content ? (
                                    <div className="source-content-preview">
                                        {source_content.substring(0, 500)}...
                                        <div className="preview-note">
                                            <small>⚠️ Показано начало текста источника</small>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="no-content">
                                        Текст источника отсутствует
                                    </div>
                                )
                            )}
                        </div>
                    </div>

                    {verification.keyword_matches && verification.keyword_matches.length > 0 && (
                        <div className="keyword-matches">
                            <strong>Найденные ключевые слова:</strong>
                            <div className="keyword-list">
                                {verification.keyword_matches.map((match, idx) => (
                                    <span key={idx} className="keyword-tag">
                                        {match.keyword}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            ) : (
                <div className="no-match-details">
                    <p><strong>Причина:</strong> {verification.reason || 'Связь с источником не обнаружена'}</p>

                    {!has_source_content && (
                        <div className="suggestion">
                            <p>📌 Для точной проверки нужен полный текст источника в библиотеке</p>
                            <button
                                className="find-source-btn"
                                onClick={() => alert('Загрузите полный текст источника для детальной проверки')}
                            >
                                📚 Добавить текст источника
                            </button>
                        </div>
                    )}
                </div>
            )}

            <div className="result-actions">
                <button
                    className="view-details-btn"
                    onClick={() => setSelectedResult(result)}
                >
                    🔍 Подробнее
                </button>
            </div>
        </div>
    );
};

    const showInContext = (result) => {
        if (result.verification.position !== undefined) {
            const start = Math.max(0, result.verification.position - 200);
            const end = Math.min(result.source_content.length, result.verification.position + 200);
            const context = result.source_content.substring(start, end);

            alert(`Контекст цитаты в источнике:\n\n...${context}...`);
        }
    };

    return (
        <div className="citation-source-verifier">
            <div className="verifier-header">
                <h2>🔍 Проверка соответствия цитат источникам</h2>
                <p className="description">
                    Проверяет, действительно ли цитаты из документа взяты из указанных источников
                </p>
            </div>

            <div className="summary-stats">
                <div className="stat-item">
                    <span className="stat-value">{citations.length}</span>
                    <span className="stat-label">Цитат в документе</span>
                </div>
                <div className="stat-item">
                    <span className="stat-value">{bibliography.length}</span>
                    <span className="stat-label">Источников в библиографии</span>
                </div>
                <div className="stat-item">
                    <span className="stat-value">{librarySources.length}</span>
                    <span className="stat-label">Источников в библиотеке</span>
                </div>
            </div>

            {loading && (
            <div className="progress-container">
                <div className="progress-bar">
                    <div
                        className="progress-fill"
                        style={{ width: `${progress}%` }}
                    ></div>
                </div>
                <div className="progress-text">
                    Проверка: {progress}%
                </div>
            </div>
            )}

            <div className="main-controls">
                <button
                    className="verify-button"
                    onClick={verifyAllCitations}
                    disabled={loading || citations.length === 0}
                >
                    {loading ? (
                        <>
                            <div className="spinner"></div>
                            Проверка соответствия...
                        </>
                    ) : (
                        '🔍 Проверить соответствие цитат и источников'
                    )}
                </button>

                <p className="control-info">
                    Система проверит, содержатся ли цитаты из документа в указанных источниках
                </p>
            </div>

            {verificationResults.length > 0 && (
                <div className="verification-results">
                    <h3>Результаты проверки</h3>

                    <div className="results-summary">
                        <div className="summary-item verified">
                            <span className="summary-count">
                                {verificationResults.filter(r => r.verification.found).length}
                            </span>
                            <span className="summary-label">Подтверждено</span>
                        </div>
                        <div className="summary-item not-verified">
                            <span className="summary-count">
                                {verificationResults.filter(r => !r.verification.found).length}
                            </span>
                            <span className="summary-label">Не подтверждено</span>
                        </div>
                    </div>

                    <div className="results-list">
                        {verificationResults.map((result, index) =>
                            renderVerificationResult(result, index)
                        )}
                    </div>
                </div>
            )}

            {/* Модальное окно с деталями */}
            {selectedResult && (
                <VerificationDetailsModal
                    result={selectedResult}
                    onClose={() => setSelectedResult(null)}
                />
            )}
        </div>
    );
};

const VerificationDetailsModal = ({ result, onClose }) => {
    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>Детали проверки цитаты [{result.citation_number}]</h3>
                    <button className="close-btn" onClick={onClose}>✕</button>
                </div>

                <div className="modal-body">
                    <div className="section">
                        <h4>Цитата из документа</h4>
                        <div className="citation-box">
                            {result.citation_text}
                        </div>
                    </div>

                    <div className="section">
                        <h4>Источник</h4>
                        <div className="source-box">
                            {result.source_title}
                        </div>
                    </div>

                    <div className="section">
                        <h4>Результат проверки</h4>
                        <div className={`verification-box ${result.verification.found ? 'verified' : 'not-verified'}`}>
                            <p><strong>Статус:</strong> {result.verification.found ? 'Найдено в источнике' : 'Не найдено'}</p>
                            <p><strong>Уверенность:</strong> {result.verification.confidence}%</p>
                            <p><strong>Тип совпадения:</strong> {result.verification.match_type}</p>
                        </div>
                    </div>

                    {result.verification.similar_phrases && result.verification.similar_phrases.length > 0 && (
                        <div className="section">
                            <h4>Похожие фразы</h4>
                            {result.verification.similar_phrases.map((phrase, idx) => (
                                <div key={idx} className="similar-phrase">
                                    <p>{phrase.snippet}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default CitationSourceVerifier;