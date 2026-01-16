// frontend/src/components/AddSourceForm.jsx
import React, { useState } from 'react';
import axios from 'axios';
import '../css/AddSourceForm.css';

const AddSourceForm = ({ onSourceAdded }) => {
    const [formData, setFormData] = useState({
        title: '',
        authors: [''],
        year: '',
        source_type: 'article',
        publisher: '',
        journal: '',
        url: '',
        doi: '',
        isbn: '',
        custom_citation: ''
    });
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [activeTab, setActiveTab] = useState('manual');
    const [extractedMetadata, setExtractedMetadata] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [uploadedFileId, setUploadedFileId] = useState(null);

    const handleInputChange = (field, value) => {
        setFormData(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleAuthorChange = (index, value) => {
        const newAuthors = [...formData.authors];
        newAuthors[index] = value;
        setFormData(prev => ({
            ...prev,
            authors: newAuthors
        }));
    };

    const addAuthorField = () => {
        setFormData(prev => ({
            ...prev,
            authors: [...prev.authors, '']
        }));
    };

    const removeAuthorField = (index) => {
        if (formData.authors.length > 1) {
            const newAuthors = formData.authors.filter((_, i) => i !== index);
            setFormData(prev => ({
                ...prev,
                authors: newAuthors
            }));
        }
    };

    const handleSubmitFromUpload = async (sourceId) => {
        // Для загруженных файлов используем данные из extractedMetadata
        const submitData = {
            ...formData,
            source_id: sourceId, // Используем ID из ответа сервера
            extracted_from_file: true
        };

        if (onSourceAdded) {
            onSourceAdded(submitData);
        }

        // Показываем сообщение об успехе
        alert('Источник успешно добавлен в библиотеку из файла!');

        // Сбрасываем форму
        resetForm();
    };

    const handleManualSubmit = async (e) => {
        e.preventDefault();

        const filteredAuthors = formData.authors.filter(author => author.trim() !== '');

        if (!formData.title.trim()) {
            alert('Пожалуйста, заполните название');
            return;
        }

        if (filteredAuthors.length === 0) {
            alert('Пожалуйста, укажите хотя бы одного автора');
            return;
        }

        // Определяем, какой endpoint использовать
        let endpoint = 'http://localhost:8001/api/library/sources/manual';
        let submitData = {
            ...formData,
            authors: filteredAuthors
        };

        // Если у нас есть ID загруженного файла, обновляем его, а не создаем новый
        if (uploadedFileId && activeTab === 'upload') {
            endpoint = `http://localhost:8001/api/library/sources/${uploadedFileId}`;
        }

        try {
            let response;

            if (uploadedFileId && activeTab === 'upload') {
                // Обновляем существующий источник
                response = await axios.put(endpoint, submitData);
            } else {
                // Создаем новый источник
                response = await axios.post(endpoint, submitData);
            }

            if (response.data.success) {
                if (onSourceAdded) {
                    onSourceAdded({ ...submitData, id: response.data.source_id });
                }
                alert('Источник успешно добавлен в библиотеку!');
                resetForm();
                setUploadedFileId(null); // Сбрасываем ID после успешного сохранения
            } else {
                throw new Error(response.data.message);
            }
        } catch (error) {
            console.error('Error adding manual source:', error);
            alert('Ошибка при добавлении источника: ' + (error.response?.data?.detail || error.message));
        }
    };

    const resetForm = () => {
        setFormData({
            title: '',
            authors: [''],
            year: '',
            source_type: 'article',
            publisher: '',
            journal: '',
            url: '',
            doi: '',
            isbn: '',
            custom_citation: ''
        });
        setExtractedMetadata(null);
        setUploadedFileId(null);
    };

    const handleFileUpload = async (file) => {
        if (!file) return;

        const allowedTypes = ['.pdf', '.docx', '.doc'];
        const fileExtension = file.name.toLowerCase().slice(
            (file.name.lastIndexOf(".") - 1 >>> 0) + 2
        );

        if (!allowedTypes.includes(`.${fileExtension}`)) {
            alert('Пожалуйста, загружайте только PDF или DOCX файлы');
            return;
        }

        setIsUploading(true);
        setUploadProgress(0);

        const uploadData = new FormData();
        uploadData.append('file', file);

        try {
            const response = await axios.post('http://localhost:8001/api/library/sources/upload', uploadData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                onUploadProgress: (progressEvent) => {
                    const percentCompleted = Math.round(
                        (progressEvent.loaded * 100) / progressEvent.total
                    );
                    setUploadProgress(percentCompleted);
                },
            });

            if (response.data.success) {
                const metadata = response.data.metadata;
                setExtractedMetadata(metadata);

                // Сохраняем ID загруженного файла
                if (response.data.source_id) {
                    setUploadedFileId(response.data.source_id);
                }

                // Исправляем: если название из метаданных совпадает с именем файла, очищаем его
                let extractedTitle = metadata.title || '';
                const fileNameWithoutExt = file.name.replace(/\.[^/.]+$/, "");

                // Проверяем, не является ли извлеченное название просто именем файла
                if (extractedTitle === fileNameWithoutExt ||
                    extractedTitle.toLowerCase() === fileNameWithoutExt.toLowerCase()) {
                    extractedTitle = ''; // Сбрасываем название, если оно совпадает с именем файла
                }

                // Автоматически заполняем форму извлеченными данными
                setFormData(prev => ({
                    ...prev,
                    title: extractedTitle || prev.title,
                    authors: metadata.authors && metadata.authors.length > 0 ? metadata.authors : prev.authors,
                    year: metadata.year || prev.year,
                    publisher: metadata.publisher || prev.publisher,
                    journal: metadata.journal || prev.journal,
                    source_type: metadata.source_type || prev.source_type
                }));

                // Показываем информацию о извлеченных данных
                const extractedInfo = [];
                if (metadata.title !== file.name.replace(/\.[^/.]+$/, "")) {
                    extractedInfo.push('название');
                }
                if (metadata.authors.length > 0) {
                    extractedInfo.push('авторы');
                }
                if (metadata.year) {
                    extractedInfo.push('год');
                }

                if (extractedInfo.length > 0) {
                    alert(`Файл успешно загружен! Извлечены: ${extractedInfo.join(', ')}. Проверьте данные перед сохранением.`);
                } else {
                    alert('Файл загружен, но не удалось извлечь метаданные. Заполните информацию вручную.');
                }

            } else {
                throw new Error(response.data.message);
            }
        } catch (error) {
            console.error('File upload failed:', error);
            const errorMsg = error.response?.data?.detail || error.message;
            if (errorMsg.includes('datetime')) {
                alert('Ошибка сервера. Пожалуйста, попробуйте позже или добавьте источник вручную.');
            } else {
                alert('Ошибка при загрузке файла: ' + errorMsg);
            }
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            setIsDragging(false);
        }
    };

    const handleFileSelect = async (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            await handleFileUpload(files[0]);
        }
    };

    const handleDrop = async (e) => {
        e.preventDefault();
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            await handleFileUpload(files[0]);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const switchToManual = () => {
        setActiveTab('manual');
        setExtractedMetadata(null);
        setUploadedFileId(null);
    };

    return (
        <div className="add-source-form">
            <div className="form-header">
                <h3>📚 Добавить источник в библиотеку</h3>
                <p>Пополните вашу коллекцию академических материалов</p>
            </div>

            <div className="form-tabs">
                <button
                    className={`tab-button ${activeTab === 'manual' ? 'active' : ''}`}
                    onClick={() => setActiveTab('manual')}
                >
                    <span>✏️</span>
                    Ручной ввод
                </button>
                <button
                    className={`tab-button ${activeTab === 'upload' ? 'active' : ''}`}
                    onClick={() => setActiveTab('upload')}
                >
                    <span>📎</span>
                    Загрузить файл источника
                </button>
            </div>

            <div className="form-content">
                {activeTab === 'manual' ? (
                    <form onSubmit={handleManualSubmit} className="manual-form">
                        <div className="form-group">
                            <label>Название источника *</label>
                            <input
                                type="text"
                                value={formData.title}
                                onChange={(e) => handleInputChange('title', e.target.value)}
                                placeholder="Введите полное название источника..."
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label>Авторы *</label>
                            {formData.authors.map((author, index) => (
                                <div key={index} className="author-input-group">
                                    <input
                                        type="text"
                                        value={author}
                                        onChange={(e) => handleAuthorChange(index, e.target.value)}
                                        placeholder={`Фамилия И.О. автора ${index + 1}`}
                                    />
                                    {formData.authors.length > 1 && (
                                        <button
                                            type="button"
                                            onClick={() => removeAuthorField(index)}
                                            className="remove-author-btn"
                                            title="Удалить автора"
                                        >
                                            ✕
                                        </button>
                                    )}
                                </div>
                            ))}
                            <button
                                type="button"
                                onClick={addAuthorField}
                                className="add-author-btn"
                            >
                                <span>+</span>
                                Добавить автора
                            </button>
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Год публикации</label>
                                <input
                                    type="number"
                                    value={formData.year}
                                    onChange={(e) => handleInputChange('year', e.target.value)}
                                    placeholder="2023"
                                    min="1900"
                                    max={new Date().getFullYear()}
                                />
                            </div>

                            <div className="form-group">
                                <label>Тип источника</label>
                                <select
                                    value={formData.source_type}
                                    onChange={(e) => handleInputChange('source_type', e.target.value)}
                                >
                                    <option value="book">📘 Книга</option>
                                    <option value="article">📄 Научная статья</option>
                                    <option value="thesis">🎓 Диссертация</option>
                                    <option value="conference">👥 Конференция</option>
                                    <option value="web">🌐 Веб-сайт</option>
                                    <option value="other">📁 Другое</option>
                                </select>
                            </div>
                        </div>

                        {formData.source_type === 'book' && (
                            <div className="form-group">
                                <label>Издательство</label>
                                <input
                                    type="text"
                                    value={formData.publisher}
                                    onChange={(e) => handleInputChange('publisher', e.target.value)}
                                    placeholder="Название издательства..."
                                />
                            </div>
                        )}

                        {formData.source_type === 'article' && (
                            <div className="form-group">
                                <label>Журнал или сборник</label>
                                <input
                                    type="text"
                                    value={formData.journal}
                                    onChange={(e) => handleInputChange('journal', e.target.value)}
                                    placeholder="Название журнала..."
                                />
                            </div>
                        )}

                        <div className="form-row">
                            <div className="form-group">
                                <label>DOI идентификатор</label>
                                <input
                                    type="text"
                                    value={formData.doi}
                                    onChange={(e) => handleInputChange('doi', e.target.value)}
                                    placeholder="10.1234/example.2023"
                                />
                            </div>

                            <div className="form-group">
                                <label>ISBN</label>
                                <input
                                    type="text"
                                    value={formData.isbn}
                                    onChange={(e) => handleInputChange('isbn', e.target.value)}
                                    placeholder="978-5-12345-678-9"
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label>Ссылка на источник</label>
                            <input
                                type="url"
                                value={formData.url}
                                onChange={(e) => handleInputChange('url', e.target.value)}
                                placeholder="https://example.com/article"
                            />
                        </div>

                        <div className="form-group">
                            <label>Произвольная библиографическая запись</label>
                            <textarea
                                value={formData.custom_citation}
                                onChange={(e) => handleInputChange('custom_citation', e.target.value)}
                                placeholder="Иванов И.И., Петров П.П. (2023) Название статьи. Журнал, 1(1), 1-10."
                                rows="3"
                            />
                        </div>

                        <button type="submit" className="submit-btn">
                            💾 Добавить в библиотеку
                        </button>
                    </form>
                ) : (
                    <div className="upload-section">
                        {isUploading ? (
                            <div className="upload-progress">
                                <div className="progress-container">
                                    <div className="progress-bar">
                                        <div
                                            className="progress-fill"
                                            style={{ width: `${uploadProgress}%` }}
                                        ></div>
                                    </div>
                                    <p className="progress-text">
                                        {uploadProgress < 100 ? 'Загрузка и анализ...' : 'Завершение...'} {uploadProgress}%
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <>
                                <div
                                    className={`upload-zone ${isDragging ? 'upload-zone-dragging' : ''}`}
                                    onDrop={handleDrop}
                                    onDragOver={handleDragOver}
                                    onDragLeave={handleDragLeave}
                                >
                                    <div className="upload-icon">
                                        <svg
                                            className="upload-svg"
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 48 48"
                                        >
                                            <path
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={2}
                                                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                                            />
                                        </svg>
                                    </div>
                                    <p className="upload-instruction">
                                        <span className="upload-highlight">
                                            Перетащите файл источника сюда
                                        </span>
                                    </p>
                                    <p className="upload-formats">
                                        Поддерживаемые форматы: PDF, DOCX, DOC (до 50MB)
                                    </p>
                                </div>

                                <input
                                    type="file"
                                    id="file-upload"
                                    className="file-input"
                                    accept=".pdf,.docx,.doc"
                                    onChange={handleFileSelect}
                                />
                                <label
                                    htmlFor="file-upload"
                                    className="upload-button"
                                >
                                    📁 Выбрать файл на компьютере
                                </label>

                                {extractedMetadata && (
                                    <div className="extracted-metadata">
                                        <h4>Метаданные успешно извлечены!</h4>
                                        <div className="metadata-preview">
                                            <p>
                                                <strong>Название</strong>
                                                {formData.title}
                                            </p>
                                            <p>
                                                <strong>Авторы</strong>
                                                {formData.authors.join(', ') || 'Не удалось определить'}
                                            </p>
                                            <p>
                                                <strong>Год</strong>
                                                {formData.year || 'Не определен'}
                                            </p>
                                            <p>
                                                <strong>Тип</strong>
                                                {formData.source_type === 'book' ? 'Книга' :
                                                 formData.source_type === 'article' ? 'Статья' :
                                                 formData.source_type}
                                            </p>
                                        </div>
                                        <button
                                            onClick={switchToManual}
                                            className="edit-metadata-btn"
                                        >
                                            ✏️ Редактировать метаданные перед добавлением
                                        </button>
                                    </div>
                                )}

                                <div className="upload-tips">
                                    <h4>Рекомендации по загрузке</h4>
                                    <ul>
                                        <li>Загружайте PDF или DOCX файлы научных статей, книг, диссертаций</li>
                                        <li>Система автоматически извлечет метаданные и сохранит файл</li>
                                        <li>Источник будет доступен для проверки цитирования в ваших работах</li>
                                        <li>При необходимости вы можете отредактировать извлеченные данные</li>
                                    </ul>
                                </div>
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AddSourceForm;