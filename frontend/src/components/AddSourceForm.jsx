// frontend/src/components/AddSourceForm.jsx
import React, { useState } from 'react';
import '../css/AddSourceForm.css';
import '../css/components.css';

const AddSourceForm = ({ onSubmit }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [formData, setFormData] = useState({
        title: '',
        authors: [''],
        year: '',
        source_type: 'book',
        publisher: '',
        journal: '',
        url: '',
        doi: '',
        isbn: '',
        custom_citation: '',
        tags: []
    });

    const handleSubmit = (e) => {
        e.preventDefault();

        // Фильтруем пустых авторов
        const filteredAuthors = formData.authors.filter(author => author.trim() !== '');

        if (!formData.title.trim()) {
            alert('Пожалуйста, заполните название');
            return;
        }

        if (filteredAuthors.length === 0) {
            alert('Пожалуйста, добавьте хотя бы одного автора');
            return;
        }

        onSubmit({
            ...formData,
            authors: filteredAuthors
        });

        // Сбрасываем форму
        setFormData({
            title: '',
            authors: [''],
            year: '',
            source_type: 'book',
            publisher: '',
            journal: '',
            url: '',
            doi: '',
            isbn: '',
            custom_citation: '',
            tags: []
        });
        setIsExpanded(false);
    };

    const addAuthor = () => {
        setFormData(prev => ({
            ...prev,
            authors: [...prev.authors, '']
        }));
    };

    const updateAuthor = (index, value) => {
        setFormData(prev => ({
            ...prev,
            authors: prev.authors.map((author, i) => i === index ? value : author)
        }));
    };

    const removeAuthor = (index) => {
        setFormData(prev => ({
            ...prev,
            authors: prev.authors.filter((_, i) => i !== index)
        }));
    };

    return (
        <div className="add-source-form">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="expand-button"
            >
                {isExpanded ? '✕ Отмена' : '+ Добавить новый источник'}
            </button>

            {isExpanded && (
                <form onSubmit={handleSubmit} className="source-form">
                    <div className="form-group">
                        <label>Название *</label>
                        <input
                            type="text"
                            value={formData.title}
                            onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                            placeholder="Название книги или статьи"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Авторы *</label>
                        {formData.authors.map((author, index) => (
                            <div key={index} className="author-input">
                                <input
                                    type="text"
                                    value={author}
                                    onChange={(e) => updateAuthor(index, e.target.value)}
                                    placeholder="Фамилия И.О."
                                />
                                {formData.authors.length > 1 && (
                                    <button
                                        type="button"
                                        onClick={() => removeAuthor(index)}
                                        className="remove-author"
                                    >
                                        ✕
                                    </button>
                                )}
                            </div>
                        ))}
                        <button type="button" onClick={addAuthor} className="add-author">
                            + Добавить автора
                        </button>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Год</label>
                            <input
                                type="number"
                                value={formData.year}
                                onChange={(e) => setFormData(prev => ({ ...prev, year: e.target.value }))}
                                placeholder="2023"
                                min="1900"
                                max="2030"
                            />
                        </div>

                        <div className="form-group">
                            <label>Тип источника</label>
                            <select
                                value={formData.source_type}
                                onChange={(e) => setFormData(prev => ({ ...prev, source_type: e.target.value }))}
                            >
                                <option value="book">Книга</option>
                                <option value="article">Статья</option>
                                <option value="thesis">Диссертация</option>
                                <option value="conference">Конференция</option>
                                <option value="website">Веб-сайт</option>
                                <option value="other">Другое</option>
                            </select>
                        </div>
                    </div>

                    {formData.source_type === 'book' && (
                        <div className="form-group">
                            <label>Издательство</label>
                            <input
                                type="text"
                                value={formData.publisher}
                                onChange={(e) => setFormData(prev => ({ ...prev, publisher: e.target.value }))}
                                placeholder="Название издательства"
                            />
                        </div>
                    )}

                    {formData.source_type === 'article' && (
                        <div className="form-group">
                            <label>Журнал</label>
                            <input
                                type="text"
                                value={formData.journal}
                                onChange={(e) => setFormData(prev => ({ ...prev, journal: e.target.value }))}
                                placeholder="Название журнала"
                            />
                        </div>
                    )}

                    <div className="form-row">
                        <div className="form-group">
                            <label>ISBN</label>
                            <input
                                type="text"
                                value={formData.isbn}
                                onChange={(e) => setFormData(prev => ({ ...prev, isbn: e.target.value }))}
                                placeholder="ISBN для книг"
                            />
                        </div>

                        <div className="form-group">
                            <label>DOI</label>
                            <input
                                type="text"
                                value={formData.doi}
                                onChange={(e) => setFormData(prev => ({ ...prev, doi: e.target.value }))}
                                placeholder="DOI для статей"
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label>URL</label>
                        <input
                            type="url"
                            value={formData.url}
                            onChange={(e) => setFormData(prev => ({ ...prev, url: e.target.value }))}
                            placeholder="https://example.com"
                        />
                    </div>

                    <div className="form-group">
                        <label>Готовое цитирование</label>
                        <textarea
                            value={formData.custom_citation}
                            onChange={(e) => setFormData(prev => ({ ...prev, custom_citation: e.target.value }))}
                            placeholder="Иванов И.И. Название книги. — М.: Издательство, 2023. — 256 с."
                            rows="3"
                        />
                    </div>

                    <div className="form-actions">
                        <button type="submit" className="submit-button">
                            Добавить в библиотеку
                        </button>
                        <button
                            type="button"
                            onClick={() => setIsExpanded(false)}
                            className="cancel-button"
                        >
                            Отмена
                        </button>
                    </div>
                </form>
            )}
        </div>
    );
};

export default AddSourceForm;