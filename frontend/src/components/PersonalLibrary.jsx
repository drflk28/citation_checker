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
    const [uploading, setUploading] = useState(false);
    const [newSources, setNewSources] = useState([]);

    // Загрузка источников из бэкенда
    useEffect(() => {
        loadSourcesFromBackend();
    }, []);

    const loadSourcesFromBackend = async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${API_BASE}/sources`);
            if (response.data.success) {
                // Объединяем новые источники с загруженными
                const mergedSources = [...response.data.sources, ...newSources];
                // Убираем дубликаты по ID
                const uniqueSources = mergedSources.filter((source, index, self) =>
                    index === self.findIndex((s) => s.id === source.id)
                );
                setSources(uniqueSources);
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
            // Если есть файл, загружаем его
            if (sourceData.file) {
                await handleFileUpload(sourceData.file);
            } else {
                // Или добавляем вручную
                await addManualSource(sourceData);
            }
        } catch (error) {
            console.error('Error adding source:', error);
            alert('Ошибка при добавлении источника');
        }
    };

    const handleFileUpload = async (file) => {
        setUploading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await axios.post(`${API_BASE}/sources/upload`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });

            if (response.data.success) {
                // Получаем полную информацию о новом источнике
                const sourceId = response.data.source_id;
                const sourceResponse = await axios.get(`${API_BASE}/sources/${sourceId}`);

                if (sourceResponse.data.success) {
                    const newSource = sourceResponse.data.source;

                    // Добавляем новый источник в начало списка
                    setSources(prev => [newSource, ...prev]);

                    // Также добавляем в временный список новых источников
                    setNewSources(prev => [newSource, ...prev]);

                    alert('Файл успешно загружен и добавлен в библиотеку!');
                }
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            alert('Ошибка при загрузке файла');
        } finally {
            setUploading(false);
        }
    };

    const addManualSource = async (sourceData) => {
        try {
            const response = await axios.post(`${API_BASE}/sources/manual`, sourceData);

            if (response.data.success) {
                // Обновляем список источников
                await loadSourcesFromBackend();
                alert('Источник успешно добавлен в библиотеку!');
            }
        } catch (error) {
            console.error('Error adding manual source:', error);
            alert('Ошибка при добавлении источника');
        }
    };

    const handleSourceUpdated = (updatedSource) => {
        // Обновляем источник в списке
        setSources(prev => prev.map(source =>
            source.id === updatedSource.id ? updatedSource : source
        ));

        // Также обновляем в списке новых источников
        setNewSources(prev => prev.map(source =>
            source.id === updatedSource.id ? updatedSource : source
        ));
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
                setNewSources(prev => prev.filter(source => source.id !== sourceId));
                alert('Источник успешно удален!');
            } else {
                throw new Error(response.data.message);
            }
        } catch (error) {
            console.error('Error deleting source:', error);
            // Fallback to local deletion
            setSources(prev => prev.filter(source => source.id !== sourceId));
            setNewSources(prev => prev.filter(source => source.id !== sourceId));
            saveSourcesToStorage(sources.filter(source => source.id !== sourceId));
            alert('Источник удален из локальной библиотеки (бэкенд недоступен)');
        }
    };

    const handleSearch = (query) => {
        setSearchQuery(query);
    };

    // Фильтрация источников для поиска
    const filteredSources = sources.filter(source => {
        if (!searchQuery.trim()) return true;

        const query = searchQuery.toLowerCase();
        return (
            source.title.toLowerCase().includes(query) ||
            (source.authors && source.authors.some(author => author.toLowerCase().includes(query))) ||
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

    const handleRefresh = () => {
        loadSourcesFromBackend();
    };

    return (
        <div className="library-section">
            <div className="library-header">
                <div className="header-row">
                    <div>
                        <h2>Библиотека источников</h2>
                        <p>Коллекция библиографических источников</p>
                    </div>
                    <button
                        onClick={handleRefresh}
                        className="btn-refresh"
                        disabled={loading}
                    >
                        {loading ? '⏳' : '🔄'} Обновить
                    </button>
                </div>
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
                {searchQuery && (
                    <button
                        onClick={() => setSearchQuery('')}
                        className="clear-search"
                    >
                        ✕
                    </button>
                )}
            </div>

            <AddSourceForm onSubmit={handleAddSource} uploading={uploading} />

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
                        onUpdate={handleSourceUpdated}
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
                        <div className="stats-grid">
                            <div className="stat-item">
                                <span className="stat-label">Всего:</span>
                                <span className="stat-value">{sources.length}</span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-label">Найдено:</span>
                                <span className="stat-value">{filteredSources.length}</span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-label">С файлами:</span>
                                <span className="stat-value">
                                    {sources.filter(s => s.has_file).length}
                                </span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-label">Новых:</span>
                                <span className="stat-value">{newSources.length}</span>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default PersonalLibrary;