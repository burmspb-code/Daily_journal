// === СОРТИРОВКА ПО ДАТЕ СОЗДАНИЯ ===

export  function toggleDateSort() {
    // Получаем текущие URL-параметры
    const urlParams = new URLSearchParams(window.location.search);
    const currentSort = urlParams.get('sort'); // предполагаем, что параметр называется 'sort'

    // Определяем следующее состояние сортировки
    let nextSort = 'newest';
    if (currentSort === 'newest') {
        nextSort = 'oldest';
    } else if (currentSort === 'oldest') {
        nextSort = 'newest';
    }

    // Обновляем параметр в URL и перезагружаем страницу
    urlParams.set('sort', nextSort);
    window.location.search = urlParams.toString();
}