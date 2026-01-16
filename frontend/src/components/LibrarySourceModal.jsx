import React from 'react';
import axios from 'axios';
import '../css/LibrarySourceModal.css';

const LibrarySourceModal = ({ source, onClose }) => {
    const [loading, setLoading] = useState(false);
    const [fullContent, setFullContent] = useState(null);

    const loadFullContent = async () => {
        if (!source.has_content || fullContent) return;

        setLoading(true);
        try {
            const response = await axios.get(`http://localhost:8001/api/library/sources/${source.id}/full-content`);
            if (response.data.success) {
                setFullContent(response.data.full_content);
            }
        } catch (error) {
            console.error('Error loading full content:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatAuthors = (authors) => {
        if (!authors || authors.length === 0) return 'Авторы не указаны';
        return authors.join(', ');
    };

    const getSourceTypeName = (type) => {
        const types = {
            'book': '📘 Книга',
            'article': '📄 Статья',
            'thesis': '🎓 Диссертация',
            'conference': '👥 Конференция',
            'web': '🌐 Веб-сайт',
            'other': '📁 Другое'
        };
        return types[type] || type;
    };

    return (
        <div className="modal-overlay library-source-modal" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h2 className="modal-title">
                        {source.title}
                    </h2>
                    <button className="close-btn" onClick={onClose}>✕</button>
                </div>

                <div className="modal-body">
                    <div className="source-info-grid">
                        <div className="info-section">
                            <h3>📋 Основная информация</h3>
                            <div className="info-grid">
                                <div className="info-item">
                                    <label>Тип:</label>
                                    <span>{getSourceTypeName(source.source_type)}</span>
                                </div>
                                <div className="info-item">
                                    <label>Авторы:</label>
                                    <span>{formatAuthors(source.authors)}</span>
                                </div>
                                <div className="info-item">
                                    <label>Год:</label>
                                    <span>{source.year || 'Не указан'}</span>
                                </div>
                                <div className="info-item">
                                    <label>Добавлен:</label>
                                    <span>{new Date(source.created_at).toLocaleDateString('ru-RU')}</span>
                                </div>
                            </div>
                        </div>

                        {(source.journal || source.publisher) && (
                            <div className="info-section">
                                <h3>📖 Публикация</h3>
                                <div className="info-grid">
                                    {source.journal && (
                                        <div className="info-item">
                                            <label>Журнал/Сборник:</label>
                                            <span>{source.journal}</span>
                                        </div>
                                    )}
                                    {source.publisher && (
                                        <div className="info-item">
                                            <label>Издательство:</label>
                                            <span>{source.publisher}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {(source.doi || source.isbn || source.url) && (
                            <div className="info-section">
                                <h3>🔗 Идентификаторы и ссылки</h3>
                                <div className="info-grid">
                                    {source.doi && (
                                        <div className="info-item">
                                            <label>DOI:</label>
                                            <span className="identifier">{source.doi}</span>
                                        </div>
                                    )}
                                    {source.isbn && (
                                        <div className="info-item">
                                            <label>ISBN:</label>
                                            <span className="identifier">{source.isbn}</span>
                                        </div>
                                    )}
                                    {source.url && (
                                        <div className="info-item">
                                            <label>URL:</label>
                                            <a href={source.url} target="_blank" rel="noopener noreferrer">
                                                {source.url}
                                            </a>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {source.has_content && (
                            <div className="info-section">
                                <h3>📄 Содержание</h3>
                                <div className="content-section">
                                    {source.content_preview && !fullContent && (
                                        <div className="content-preview">
                                            <p>{source.content_preview}</p>
                                            <button
                                                onClick={loadFullContent}
                                                className="show-more-btn"
                                                disabled={loading}
                                            >
                                                {loading ? 'Загрузка...' : 'Показать полный текст'}
                                            </button>
                                        </div>
                                    )}

                                    {fullContent && (
                                        <div className="full-content">
                                            <textarea
                                                readOnly
                                                value={fullContent}
                                                rows="10"
                                                className="content-textarea"
                                            />
                                        </div>
                                    )}

                                    {source.text_length && (
                                        <div className="content-stats">
                                            <span>Длина текста: {source.text_length} символов</span>
                                            {source.has_file && (
                                                <span> • Есть файл</span>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="modal-actions">
                    {source.has_file && (
                        <a
                            href={`http://localhost:8001/api/library/sources/${source.id}/download`}
                            className="btn-download-large"
                            download
                        >
                            📥 Скачать файл источника
                        </a>
                    )}

                    {source.custom_citation && (
                        <button
                            onClick={() => navigator.clipboard.writeText(source.custom_citation)}
                            className="btn-copy-citation"
                        >
                            📋 Копировать библиографическую запись
                        </button>
                    )}

                    <button onClick={onClose} className="btn-close">
                        Закрыть
                    </button>
                </div>
            </div>
        </div>
    );
};

export default LibrarySourceModal;