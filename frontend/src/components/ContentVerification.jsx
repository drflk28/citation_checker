// frontend/src/components/ContentVerification.jsx
import React, { useState } from 'react';
import axios from 'axios';

const ContentVerification = ({ citation, onClose }) => {
    const [verificationResult, setVerificationResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [selectedSource, setSelectedSource] = useState('');

    const handleVerify = async () => {
        if (!selectedSource) {
            alert('Выберите источник для проверки');
            return;
        }

        setLoading(true);
        try {
            const response = await axios.post('http://localhost:8001/api/library/verify-citation', {
                citation_text: citation.text,
                source_id: selectedSource
            });

            if (response.data.success) {
                setVerificationResult(response.data);
            } else {
                alert('Ошибка при проверке: ' + response.data.message);
            }
        } catch (error) {
            console.error('Verification error:', error);
            alert('Ошибка при проверке содержания');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="content-verification-modal">
            <div className="modal-content">
                <h3>Проверка соответствия цитаты источнику</h3>

                <div className="citation-preview">
                    <strong>Цитата:</strong> "{citation.text}"
                </div>

                <div className="source-selection">
                    <label>Выберите источник для проверки:</label>
                    <select
                        value={selectedSource}
                        onChange={(e) => setSelectedSource(e.target.value)}
                    >
                        <option value="">-- Выберите источник --</option>
                        {/* Здесь нужно передать список источников с контентом */}
                    </select>
                </div>

                <div className="verification-actions">
                    <button onClick={handleVerify} disabled={loading || !selectedSource}>
                        {loading ? 'Проверка...' : 'Проверить соответствие'}
                    </button>
                    <button onClick={onClose}>Отмена</button>
                </div>

                {verificationResult && (
                    <div className="verification-result">
                        <h4>Результат проверки:</h4>
                        <div className="confidence-score">
                            Уверенность: {Math.round(verificationResult.verification.confidence_score * 100)}%
                        </div>

                        {verificationResult.verification.exact_match && (
                            <div className="exact-match success">
                                ✅ Найдено точное совпадение
                            </div>
                        )}

                        {verificationResult.verification.similar_matches.length > 0 && (
                            <div className="similar-matches">
                                <h5>Похожие фразы в источнике:</h5>
                                {verificationResult.verification.similar_matches.map((match, index) => (
                                    <div key={index} className="similar-match">
                                        "{match.text}" (схожесть: {Math.round(match.similarity * 100)}%)
                                    </div>
                                ))}
                            </div>
                        )}

                        {verificationResult.verification.issues.length > 0 && (
                            <div className="issues-warning">
                                <h5>⚠️ Возможные проблемы:</h5>
                                <ul>
                                    {verificationResult.verification.issues.map((issue, index) => (
                                        <li key={index}>{issue}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ContentVerification;