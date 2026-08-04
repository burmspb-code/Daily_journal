// === ВСПОМОГАТЕЛЬНЫЕ СИСТЕМНЫЕ ФУНКЦИИ ===

export function updateTopTaskCounter(amount) {
    const badges = document.querySelectorAll('.badge');
    badges.forEach(badge => {
        if (badge.textContent.includes('Найдено задач:')) {
            const currentCount = parseInt(badge.textContent.replace(/\D/g, '')) || 0;
            badge.textContent = `Найдено задач: ${currentCount + amount}`;
        }
    });
}

export function renumberTableRows() {
    const tbody = document.getElementById('tasks-table-body');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr:not(#temporary-creation-row):not(#no-tasks-row)');
    rows.forEach((row, index) => {
        if (row.cells && row.cells[1]) {
            row.cells[1].textContent = index + 1;
        }
    });
}

export function checkIfTableIsEmpty() {
    const tbody = document.getElementById('tasks-table-body');
    if (tbody && tbody.querySelectorAll('tr').length === 0) {
        tbody.innerHTML = `<tr id="no-tasks-row"><td colspan="7" class="text-center text-muted py-3">Нет задач в этой закладке</td></tr>`;
    }
}

export function updateRowStatusBadge(taskId, flagValue) {
    // Находим строку задачи по ID
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;

    // Находим бэйдж внутри ячейки статуса
    const badge = row.querySelector('.task-status-cell .badge') || row.querySelector('.badge');
    if (!badge) return;

    // Безопасно приводим к числу
    const flag = parseInt(flagValue, 10);
    if (isNaN(flag)) return; // Если прилетел некорректный флаг, ничего не делаем

    // Единая конфигурация стилей и текстов (полностью по вашему ТЗ)
    const statusConfig = {
        0: { bg: 'bg-success text-white', icon: 'bi-plus-circle-fill', text: 'Создана' },
        1: { bg: 'bg-warning text-dark', icon: 'bi-gear-fill', text: 'В работе' },
        2: { bg: 'bg-secondary text-white', icon: 'bi-check-circle-fill', text: 'Выполнена' },
        3: { bg: 'bg-danger text-white', icon: 'bi-exclamation-triangle-fill', text: 'Дедлайн' }
    };

    // Проверяем, существует ли такой статус в конфиге
    if (flag in statusConfig) {
        const config = statusConfig[flag];

        // Обновляем классы (заменяем только цвета, сохраняя структуру верстки)
        badge.className = `badge rounded-pill ${config.bg} px-2 py-1 d-inline-flex align-items-center gap-1`;

        // Обновляем всплывающую подсказку при наведении
        badge.setAttribute('title', config.text);

        // Обновляем иконку и текст
        badge.innerHTML = `<i class="bi ${config.icon}"></i> ${config.text}`;
    }
}

export function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) { cookieValue = decodeURIComponent(cookie.substring(name.length + 1)); break; }
        }
    }
    return cookieValue;
}