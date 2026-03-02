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
                    const result = await verifyCitationSourcePair(pair);
                    if (result) {
                        results.push(result);
                        setVerificationResults([...results]);
                    }
                } catch (pairError) {
                    console.error(`Ошибка проверки пары ${i + 1}:`, pairError);
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

        citations.forEach(citation => {
            const citationNumber = extractCitationNumber(citation.text);

            if (citationNumber !== null) {
                const sourceIndex = citationNumber - 1;

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

        console.log('   📦 Данные пары:', { citation, source, citation_number });

        const full_citation_text = getCitationText(citation, citation_number);
        console.log(`   📝 Текст цитаты: "${full_citation_text?.substring(0, 100)}..."`);

        let sourceContent = '';
        let sourceId = null;
        let sourceTitle = '';

        console.log('   🔍 library_match:', source.library_match);

        if (source.library_match?.id) {
            sourceId = source.library_match.id;
            console.log(`   📚 Источник найден в библиотеке: ${sourceId}`);

            try {
                const response = await axios.get(
                    `http://localhost:8001/api/library/sources/${sourceId}/full-content`,
                    { timeout: 10000 }
                );

                console.log(`   📡 Статус ответа:`, response.status);
                console.log(`   📡 Данные ответа:`, response.data);

                if (response.data.success) {
                    sourceContent = response.data.full_content || '';
                    sourceTitle = response.data.title || source.text?.substring(0, 100);
                    console.log(`   ✅ Получен контент длиной: ${sourceContent.length}`);
                    console.log(`   📖 Заголовок: ${sourceTitle}`);
                } else {
                    console.log(`   ❌ Ошибка API:`, response.data.message);
                }
            } catch (apiError) {
                console.error(`   ❌ Ошибка запроса:`, apiError.message);
                if (apiError.response) {
                    console.error(`   📊 Статус:`, apiError.response.status);
                    console.error(`   📝 Данные:`, apiError.response.data);
                }
            }
        } else {
            console.log(`   ⚠️ Нет library_match для источника`);
        }

        if (!sourceContent) {
            console.log(`   ⚠️ Нет контента источника, возвращаем ошибку`);
            return {
                citation_number,
                citation_text: full_citation_text,
                source_title: sourceTitle || source.text?.substring(0, 100),
                verification: {
                    found: false,
                    reason: 'Нет доступа к тексту источника',
                    confidence: 0
                },
                has_source_content: false
            };
        }

        console.log(`   🔄 Отправляем на семантическую проверку...`);

        const verificationResult = await checkCitationInSource(
            full_citation_text,
            sourceContent,
            sourceTitle,
            sourceId
        );

        console.log(`   ✅ Результат проверки:`, verificationResult);

        return {
            citation_number,
            citation_text: full_citation_text,
            source_title: sourceTitle,
            source_content: sourceContent,
            source_id: sourceId,
            verification: verificationResult,
            has_source_content: true
        };

    } catch (error) {
        console.error(`❌ Ошибка в verifyCitationSourcePair:`, error);
        return null;
    }
};

    const checkCitationInSource = async (citationText, sourceContent, sourceTitle, sourceId) => {
    try {
        const response = await axios.post('http://localhost:8001/api/verify-citation-semantically', {
            citation_data: {
                text: citationText,
                context: citationText,
                full_paragraph: citationText
            },
            source_id: sourceId,
            source_content: sourceContent
        });

        if (response.data.success && response.data.verification_result) {
            const vr = response.data.verification_result;
            return {
                found: vr.verified,
                confidence: vr.confidence,
                reason: vr.reason,
                match_type: vr.verification_level || 'semantic',
                best_match: vr.best_match,
                // ✅ ВАЖНО: эти поля должны быть!
                total_keywords_found: vr.analysis_details?.key_words_found_total || 0,
                total_keywords_searched: vr.analysis_details?.key_words_extracted || 0,
                keyword_matches: vr.best_match?.key_words_matched || []
            };
        }
        return {
            found: false,
            reason: 'Ошибка при проверке',
            confidence: 0
        };
    } catch (error) {
        console.error('❌ Error calling semantic verification:', error);
        if (error.response) {
            console.error('   📊 Статус:', error.response.status);
            console.error('   📝 Данные:', error.response.data);
        }
        return {
            found: false,
            reason: `Ошибка API: ${error.message}`,
            confidence: 0
        };
    }
};

    const getCitationText = (citation, citation_number) => {
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
                            {verification.best_snippet && verification.best_snippet !== source_title ? (
                                verification.best_snippet
                            ) : (
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

                    {verification.keyword_matches && verification.keyword_matches.length > 0 ? (
                        <div className="keyword-matches">
                            <strong>Найденные ключевые слова:</strong>
                            <div className="keyword-list">
                                {verification.keyword_matches.map((match, idx) => (
                                    <span key={idx} className="keyword-tag">
                                        {typeof match === 'string' ? match : match.keyword}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ) : verification.total_keywords_found > 0 ? (
                        <div className="keyword-matches">
                            <strong>Статистика совпадений:</strong>
                            <p>Найдено {verification.total_keywords_found} из {verification.total_keywords_searched} ключевых слов</p>
                        </div>
                    ) : null}

                    <div className="result-actions">
                        <button
                            className="view-details-btn"
                            onClick={() => setSelectedResult(result)}
                        >
                            🔍 Подробнее
                        </button>
                    </div>
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

    // ✅ ЭТОТ return должен быть ТОЛЬКО ОДИН раз в файле!
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
                        <div className="progress-fill" style={{ width: `${progress}%` }}></div>
                    </div>
                    <div className="progress-text">Проверка: {progress}%</div>
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
                        {verificationResults.map((result, index) => renderVerificationResult(result, index))}
                    </div>
                </div>
            )}

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
                            {/* ✅ ИСПРАВЛЕНО: показываем и название, и текст */}
                            <div className="source-title">
                                <strong>Название:</strong> {result.source_title}
                            </div>
                            {result.source_content && (
                                <div className="source-content">
                                    <strong>Текст источника:</strong>
                                    <div className="content-preview">
                                        {result.source_content.substring(0, 500)}
                                        {result.source_content.length > 500 && '...'}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="section">
                        <h4>Результат проверки</h4>
                        <div className={`verification-box ${result.verification.found ? 'verified' : 'not-verified'}`}>
                            <p><strong>Статус:</strong> {result.verification.found ? 'Найдено в источнике' : 'Не найдено'}</p>
                            <p><strong>Уверенность:</strong> {result.verification.confidence}%</p>
                            <p><strong>Тип совпадения:</strong> {result.verification.match_type || 'semantic'}</p>
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