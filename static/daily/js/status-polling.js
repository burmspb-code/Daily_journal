// === ПОЛЛИНГ СТАТУСОВ ЗАДАЧ ===
// Периодически проверяет изменения статусов задач на сервере и обновляет UI

let pollingInterval = null;
const POLLING_INTERVAL_MS = 30000; // 30 секунд

/**
 * Запускает периодическое обновление статусов задач
 */
export function startStatusPolling() {
    if (pollingInterval) {
        return;
    }

    // Сразу делаем первый запрос
    updateTaskStatuses();

    // Запускаем периодический опрос
    pollingInterval = setInterval(updateTaskStatuses, POLLING_INTERVAL_MS);
}

/**
 * Останавливает polling
 */
export function stopStatusPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

/**
 * Запрашивает актуальные статусы задач с сервера и обновляет DOM
 */
async function updateTaskStatuses() {
    try {
        // Получаем текущий URL с параметрами фильтрации
        const currentUrl = new URL(window.location.href);
        const params = new URLSearchParams(currentUrl.search);

        // Формируем URL для API запроса
        // Добавляем page_size=1000 чтобы получить все задачи без пагинации
        params.set('page_size', '1000');
        const apiUrl = `/daily/api/v1/tasks/?${params.toString()}`;

        // Получаем CSRF токен
        const getCookie = (name) => {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        };
        const csrftoken = getCookie('csrftoken');

        const headers = {
            'Content-Type': 'application/json',
        };
        if (csrftoken) {
            headers['X-CSRFToken'] = csrftoken;
        }

        const response = await fetch(apiUrl, {
            method: 'GET',
            headers: headers,
            credentials: 'same-origin'
        });

        if (!response.ok) {
            console.error('[Polling] Ошибка при получении статусов:', response.status);
            return;
        }

        const data = await response.json();
        // API возвращает пагинированный ответ с полем 'results'
        // Внутри results может быть структура с полем 'tasks' или сразу массив
        let tasks = [];
        if (data.results) {
            if (Array.isArray(data.results)) {
                tasks = data.results;
            } else if (data.results.tasks && Array.isArray(data.results.tasks)) {
                tasks = data.results.tasks;
            }
        }

        // Обновляем статусы в таблице
        let updatedCount = 0;
        tasks.forEach(task => {
            const row = document.getElementById(`task-row-${task.id}`);
            if (row) {
                const currentBadge = row.querySelector('.task-status-cell .badge');
                if (currentBadge) {
                    const currentStatus = parseInt(currentBadge.getAttribute('data-status') || '0');
                    const newStatus = task.status_flag;

                    // Если статус изменился, обновляем бейдж
                    if (currentStatus !== newStatus) {
                        updateStatusBadge(currentBadge, newStatus);
                        currentBadge.setAttribute('data-status', newStatus);
                        updatedCount++;
                    }
                }
            }
        });

    } catch (error) {
        console.error('[Polling] Ошибка polling:', error);
    }
}

/**
 * Обновляет визуальное отображение бейджа статуса
 */
function updateStatusBadge(badge, statusFlag) {
    const flag = parseInt(statusFlag, 10);
    if (isNaN(flag)) return;

    const statusConfig = {
        0: {bg: 'bg-success text-white', icon: 'bi-plus-circle-fill', text: 'Создана'},
        1: {bg: 'bg-warning text-dark', icon: 'bi-gear-fill', text: 'В работе'},
        2: {bg: 'bg-secondary text-white', icon: 'bi-check-circle-fill', text: 'Выполнена'},
        3: {bg: 'bg-danger text-white', icon: 'bi-exclamation-triangle-fill', text: 'Дедлайн'}
    };

    if (flag in statusConfig) {
        const config = statusConfig[flag];
        badge.className = `badge rounded-pill ${config.bg} px-2 py-1 d-inline-flex align-items-center gap-1`;
        badge.setAttribute('title', config.text);
        badge.innerHTML = `<i class="bi ${config.icon}"></i> ${config.text}`;
        
        // Небольшая визуальная индикация обновления
        badge.style.transition = 'transform 0.2s';
        badge.style.transform = 'scale(1.1)';
        setTimeout(() => {
            badge.style.transform = 'scale(1)';
        }, 200);
    }
}
