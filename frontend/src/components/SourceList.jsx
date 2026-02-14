import React, { useState } from 'react';
import axios from 'axios';
import '../css/SourceList.css';

const SourceList = ({ sources, onDelete, onUpdate }) => {
    const [selectedSource, setSelectedSource] = useState(null);
    const [showDetails, setShowDetails] = useState(false);
    const [loading, setLoading] = useState(false);
    const [editing, setEditing] = useState(false);
    const [editFormData, setEditFormData] = useState({});
    const [saving, setSaving] = useState(false);

    if (!sources || sources.length === 0) {
        return (
            <div className="empty-library">
                <div className="empty-icon">📚</div>
                <h3>Библиотека пуста</h3>
                <p>Добавьте ваши первые источники для начала работы</p>
            </div>
        );
    }

    const handleViewDetails = async (sourceId) => {
        setLoading(true);
        try {
            const response = await axios.get(`http://localhost:8001/api/library/sources/${sourceId}`);
            if (response.data.success) {
                setSelectedSource(response.data.source);
                setShowDetails(true);
                // Сбрасываем режим редактирования при открытии нового источника
                setEditing(false);
                setEditFormData({});
            }
        } catch (error) {
            console.error('Error fetching source details:', error);
            alert('Ошибка при загрузке информации об источнике');
        } finally {
            setLoading(false);
        }
    };

    const handleStartEdit = () => {
        if (selectedSource) {
            setEditing(true);
            setEditFormData({
                title: selectedSource.title || '',
                authors: Array.isArray(selectedSource.authors) ? selectedSource.authors.join(', ') : selectedSource.authors || '',
                year: selectedSource.year || '',
                source_type: selectedSource.source_type || 'book',
                publisher: selectedSource.publisher || '',
                journal: selectedSource.journal || '',
                url: selectedSource.url || '',
                doi: selectedSource.doi || '',
                isbn: selectedSource.isbn || '',
                custom_citation: selectedSource.custom_citation || ''
            });
        }
    };

    const handleCancelEdit = () => {
        setEditing(false);
        setEditFormData({});
    };

    const handleSaveEdit = async () => {
        if (!selectedSource) return;

        setSaving(true);
        try {
            const response = await axios.put(
                `http://localhost:8001/api/library/sources/${selectedSource.id}`,
                editFormData
            );

            if (response.data.success) {
                setEditing(false);
                setSelectedSource(response.data.source);

                // Обновляем источник в списке
                if (onUpdate) {
                    onUpdate(response.data.source);
                }

                alert('Изменения сохранены успешно!');
            }
        } catch (error) {
            console.error('Error saving source:', error);
            alert('Ошибка при сохранении изменений');
        } finally {
            setSaving(false);
        }
    };

    const handleInputChange = (field, value) => {
        setEditFormData(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleDownload = async (sourceId, sourceTitle) => {
        try {
            const response = await fetch(`http://localhost:8001/api/library/sources/${sourceId}/download`);
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `${sourceTitle.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            } else {
                alert('Файл источника недоступен для скачивания');
            }
        } catch (error) {
            console.error('Download error:', error);
            alert('Ошибка при скачивании файла');
        }
    };

    const formatAuthors = (authors) => {
        if (!authors || authors.length === 0) return 'Авторы не указаны';
        return authors.join(', ');
    };

    const getSourceIcon = (sourceType) => {
        const icons = {
            'book': '📘',
            'article': '📄',
            'thesis': '🎓',
            'conference': '👥',
            'web': '🌐',
            'other': '📁'
        };
        return icons[sourceType] || '📁';
    };

    const renderEditableField = (label, field, value, type = 'text') => {
        if (!editing) {
            return (
                <div className="detail-item">
                    <label>{label}:</label>
                    <span>{value || 'Не указано'}</span>
                </div>
            );
        }

        return (
            <div className="detail-item editable">
                <label>{label}:</label>
                {type === 'textarea' ? (
                    <textarea
                        value={editFormData[field] || ''}
                        onChange={(e) => handleInputChange(field, e.target.value)}
                        className="edit-textarea"
                        rows="3"
                        placeholder={`Введите ${label.toLowerCase()}`}
                    />
                ) : type === 'select' ? (
                    <select
                        value={editFormData[field] || 'book'}
                        onChange={(e) => handleInputChange(field, e.target.value)}
                        className="edit-select"
                    >
                        <option value="book">Книга</option>
                        <option value="article">Статья</option>
                        <option value="thesis">Диссертация</option>
                        <option value="conference">Конференция</option>
                        <option value="web">Веб-сайт</option>
                        <option value="other">Другое</option>
                    </select>
                ) : (
                    <input
                        type={type}
                        value={editFormData[field] || ''}
                        onChange={(e) => handleInputChange(field, e.target.value)}
                        className="edit-input"
                        placeholder={`Введите ${label.toLowerCase()}`}
                    />
                )}
            </div>
        );
    };

    return (
        <>
            <div className="sources-grid">
                {sources.map(source => (
                    <div key={source.id} className="source-card">
                        <div className="source-header">
                            <div className="source-type-icon">
                                {getSourceIcon(source.source_type)}
                            </div>
                            <div className="source-title-wrapper">
                                <h3 className="source-title" title={source.title}>
                                    {source.title}
                                </h3>
                                <div className="source-meta">
                                    <span className="source-authors">
                                        {formatAuthors(source.authors)}
                                    </span>
                                    {source.year && (
                                        <span className="source-year">• {source.year}</span>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="source-details">
                            {source.journal && (
                                <div className="source-field">
                                    <span className="field-label">Журнал:</span>
                                    <span className="field-value">{source.journal}</span>
                                </div>
                            )}
                            {source.publisher && (
                                <div className="source-field">
                                    <span className="field-label">Издательство:</span>
                                    <span className="field-value">{source.publisher}</span>
                                </div>
                            )}
                            {source.doi && (
                                <div className="source-field">
                                    <span className="field-label">DOI:</span>
                                    <span className="field-value doi-link">{source.doi}</span>
                                </div>
                            )}
                        </div>

                        <div className="source-actions">
                            <button
                                onClick={() => handleViewDetails(source.id)}
                                className="btn-view"
                                disabled={loading}
                            >
                                {loading ? '⏳' : '👁'} Подробнее
                            </button>

                            {source.has_file && (
                                <button
                                    onClick={() => handleDownload(source.id, source.title)}
                                    className="btn-download"
                                >
                                    📥 Скачать
                                </button>
                            )}

                            {source.url && (
                                <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn-external"
                                >
                                    🔗 Открыть
                                </a>
                            )}

                            <button
                                onClick={() => onDelete(source.id)}
                                className="btn-delete"
                                title="Удалить источник"
                            >
                                🗑️
                            </button>
                        </div>

                        <div className="source-footer">
                            <span className="source-date">
                                Добавлен: {new Date(source.created_at).toLocaleDateString('ru-RU')}
                            </span>
                            {source.has_file && (
                                <span className="file-badge">📎 Есть файл</span>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* Модальное окно с деталями источника */}
            {showDetails && selectedSource && (
                <div className="modal-overlay" onClick={() => !editing && setShowDetails(false)}>
                    <div className="modal-content source-details-modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>
                                {editing ? 'Редактирование источника' : 'Детали источника'}
                            </h2>
                            <button
                                className="close-btn"
                                onClick={() => {
                                    if (!editing) {
                                        setShowDetails(false);
                                    }
                                }}
                                disabled={editing}
                            >
                                ✕
                            </button>
                        </div>

                        <div className="modal-body">
                            {renderEditableField('Название', 'title', selectedSource.title, 'text')}
                            {renderEditableField('Авторы', 'authors', formatAuthors(selectedSource.authors), 'textarea')}
                            {renderEditableField('Год', 'year', selectedSource.year, 'number')}
                            {renderEditableField('Тип', 'source_type',
                                selectedSource.source_type === 'book' ? 'Книга' :
                                selectedSource.source_type === 'article' ? 'Статья' :
                                selectedSource.source_type === 'thesis' ? 'Диссертация' :
                                selectedSource.source_type === 'conference' ? 'Конференция' :
                                selectedSource.source_type === 'web' ? 'Веб-сайт' : 'Другое',
                                'select'
                            )}

                            {(selectedSource.journal || editing) && (
                                <div className="detail-section">
                                    <h3>📖 Публикация</h3>
                                    {renderEditableField('Журнал/Сборник', 'journal', selectedSource.journal, 'text')}
                                    {renderEditableField('Издательство', 'publisher', selectedSource.publisher, 'text')}
                                </div>
                            )}

                            {(selectedSource.doi || selectedSource.isbn || selectedSource.url || editing) && (
                                <div className="detail-section">
                                    <h3>🔗 Идентификаторы и ссылки</h3>
                                    {renderEditableField('DOI', 'doi', selectedSource.doi, 'text')}
                                    {renderEditableField('ISBN', 'isbn', selectedSource.isbn, 'text')}
                                    {renderEditableField('URL', 'url', selectedSource.url, 'text')}
                                </div>
                            )}

                            {selectedSource.content_preview && (
                                <div className="detail-section">
                                    <h3>📄 Содержание</h3>
                                    <div className="content-preview">
                                        <p>{selectedSource.content_preview}</p>
                                        {selectedSource.content && selectedSource.content.length > 500 && (
                                            <div className="content-more">
                                                <em>... полный текст доступен в файле источника</em>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {selectedSource.custom_citation && (
                                <div className="detail-section">
                                    <h3>📝 Библиографическая запись</h3>
                                    {renderEditableField('Библиографическая запись', 'custom_citation', selectedSource.custom_citation, 'textarea')}
                                </div>
                            )}
                        </div>

                        <div className="modal-actions">
                            {editing ? (
                                <>
                                    <button
                                        onClick={handleSaveEdit}
                                        className="btn-save"
                                        disabled={saving}
                                    >
                                        {saving ? '⏳ Сохранение...' : '💾 Сохранить'}
                                    </button>
                                    <button
                                        onClick={handleCancelEdit}
                                        className="btn-cancel"
                                        disabled={saving}
                                    >
                                        ❌ Отмена
                                    </button>
                                </>
                            ) : (
                                <>
                                    <button
                                        onClick={handleStartEdit}
                                        className="btn-edit"
                                    >
                                        ✏️ Редактировать
                                    </button>
                                    {selectedSource.has_file && (
                                        <button
                                            onClick={() => handleDownload(selectedSource.id, selectedSource.title)}
                                            className="btn-download-large"
                                        >
                                            📥 Скачать файл
                                        </button>
                                    )}
                                    <button
                                        onClick={() => setShowDetails(false)}
                                        className="btn-close"
                                    >
                                        Закрыть
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default SourceList;