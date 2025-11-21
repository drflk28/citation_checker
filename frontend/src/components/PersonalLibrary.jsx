import React, { useState, useEffect } from 'react';
import AddSourceForm from './AddSourceForm';
import SourceList from './SourceList';
import '../css/PersonalLibrary.css';
import '../css/components.css';
import axios from 'axios';

const API_BASE = 'http://localhost:8001/api/library';

const PersonalLibrary = () => {
    const [sources, setSources] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [page, setPage] = useState(1);

    // Загрузка источников из бэкенда
    useEffect(() => {
        loadSourcesFromBackend();
    }, []);

    const loadSourcesFromBackend = async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${API_BASE}/sources`);
            if (response.data.success) {
                setSources(response.data.sources || []);
            } else {
                console.error('Error loading sources:', response.data.message);
                // Fallback to localStorage if backend fails
                loadSourcesFromStorage();
            }
        } catch (error) {
            console.error('Error loading sources from backend:', error);
            // Fallback to localStorage if backend is unavailable
            loadSourcesFromStorage();
        } finally {
            setLoading(false);
        }
    };

    const loadSourcesFromStorage = () => {
        try {
            const storedSources = localStorage.getItem('citation_library_sources');
            if (storedSources) {
                const parsedSources = JSON.parse(storedSources);
                setSources(parsedSources);
            }
        } catch (error) {
            console.error('Error loading sources from storage:', error);
        }
    };

    const handleAddSource = async (sourceData) => {
        try {
            const response = await axios.post(`${API_BASE}/sources`, sourceData);

            if (response.data.success) {
                // Обновляем локальное состояние
                const newSource = {
                    id: response.data.source_id,
                    ...sourceData,
                    created_at: new Date().toISOString(),
                    last_used: new Date().toISOString()
                };

                setSources(prev => [newSource, ...prev]);
                alert('Источник успешно добавлен в библиотеку!');
            } else {
                throw new Error(response.data.message);
            }
        } catch (error) {
            console.error('Error adding source:', error);
            // Fallback to localStorage
            const newSource = {
                id: Date.now().toString(),
                ...sourceData,
                created_at: new Date().toISOString(),
                last_used: new Date().toISOString()
            };
            setSources(prev => [newSource, ...prev]);
            saveSourcesToStorage([newSource, ...sources]);
            alert('Источник добавлен в локальную библиотеку (бэкенд недоступен)');
        }
    };

    const saveSourcesToStorage = (sourcesToSave) => {
        try {
            localStorage.setItem('citation_library_sources', JSON.stringify(sourcesToSave));
        } catch (error) {
            console.error('Error saving sources to storage:', error);
        }
    };

    const handleDeleteSource = async (sourceId) => {
        if (!confirm('Вы уверены, что хотите удалить этот источник?')) {
            return;
        }

        try {
            const response = await axios.delete(`${API_BASE}/sources/${sourceId}`);

            if (response.data.success) {
                setSources(prev => prev.filter(source => source.id !== sourceId));
                alert('Источник успешно удален!');
            } else {
                throw new Error(response.data.message);
            }
        } catch (error) {
            console.error('Error deleting source:', error);
            // Fallback to local deletion
            setSources(prev => prev.filter(source => source.id !== sourceId));
            saveSourcesToStorage(sources.filter(source => source.id !== sourceId));
            alert('Источник удален из локальной библиотеки (бэкенд недоступен)');
        }
    };

    // Остальной код остается таким же...
    const handleSearch = (query) => {
        setSearchQuery(query);
    };

    // Фильтрация источников для поиска
    const filteredSources = sources.filter(source => {
        if (!searchQuery.trim()) return true;

        const query = searchQuery.toLowerCase();
        return (
            source.title.toLowerCase().includes(query) ||
            source.authors.some(author => author.toLowerCase().includes(query)) ||
            (source.publisher && source.publisher.toLowerCase().includes(query)) ||
            (source.journal && source.journal.toLowerCase().includes(query)) ||
            (source.year && source.year.toString().includes(query))
        );
    });

    // Пагинация
    const itemsPerPage = 6;
    const totalPages = Math.ceil(filteredSources.length / itemsPerPage);
    const startIndex = (page - 1) * itemsPerPage;
    const paginatedSources = filteredSources.slice(startIndex, startIndex + itemsPerPage);

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) {
            setPage(newPage);
        }
    };

    return (
        <div className="library-section">
            <div className="library-header">
                <h2>Библиотека источников</h2>
                <p>Коллекция библиографических источников</p>
            </div>

            <div className="search-bar">
                <input
                    type="text"
                    placeholder="Поиск по названию, авторам, издательству..."
                    value={searchQuery}
                    onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setPage(1);
                    }}
                    className="search-input"
                />
            </div>

            <AddSourceForm onSubmit={handleAddSource} />

            {loading ? (
                <div className="loading-state">
                    <div className="loading-spinner"></div>
                    <p>Загрузка библиотеки...</p>
                </div>
            ) : (
                <>
                    <SourceList
                        sources={paginatedSources}
                        onDelete={handleDeleteSource}
                    />

                    {filteredSources.length > itemsPerPage && (
                        <div className="pagination">
                            <button
                                onClick={() => handlePageChange(page - 1)}
                                disabled={page <= 1}
                                className="pagination-btn prev"
                            >
                                ←
                            </button>
                            <span className="pagination-info">
                                {page} / {totalPages}
                            </span>
                            <button
                                onClick={() => handlePageChange(page + 1)}
                                disabled={page >= totalPages}
                                className="pagination-btn next"
                            >
                                →
                            </button>
                        </div>
                    )}

                    <div className="library-stats">
                        <p>Всего: {sources.length} | Найдено: {filteredSources.length}</p>
                    </div>
                </>
            )}
        </div>
    );
};

export default PersonalLibrary;