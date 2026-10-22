// === ПОЛЛИНГ СТАТУСОВ ЗАДАЧ ===
// Периодически проверяет изменения статусов задач на сервере и обновляет UI

import { renderTaskStatusCell } from './secondary-system-functions.js';

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

        // Обновляем статусы и время напоминания в таблице
        let updatedCount = 0;
        tasks.forEach(task => {
            const row = document.getElementById(`task-row-${task.id}`);
            if (row) {
                const statusCell = row.querySelector('.task-status-cell');
                const currentBadge = statusCell ? statusCell.querySelector('.badge') : null;
                if (statusCell && currentBadge) {
                    const currentStatus = parseInt(currentBadge.getAttribute('data-status') || '0');
                    const newStatus = parseInt(task.status_flag, 10);

                    // Если статус изменился, перерисовываем ВСЮ ячейку: только
                    // замена бейджа ломает обёртку-триггер дропдауна и меню
                    // «Изменить статус», после чего с задачей нельзя
                    // взаимодействовать (см. renderTaskStatusCell).
                    if (currentStatus !== newStatus) {
                        const isPeriodic = row.getAttribute('data-periodic') === '1';
                        renderTaskStatusCell(statusCell, newStatus, isPeriodic);
                        updatedCount++;
                    }
                }

                // Периодическая задача при просрочке/новом наступлении сдвигает
                // reminder_at на сервере. Без синхронизации ячейки время в
                // таблице оставалось старым до перезагрузки страницы.
                syncReminderCell(row, task.reminder_at);
            }
        });

    } catch (error) {
        console.error('[Polling] Ошибка polling:', error);
    }
}

/**
 * Синхронизирует ячейку времени напоминания с данными сервера.
 *
 * Сравнивает текущее значение скрытого инпута с пришедшим `reminder_at` и
 * перерисовывает ячейку только при реальном расхождении, чтобы не сбивать
 * открытый пользователем инлайн-редактор даты (`datetime-local`).
 *
 * @param {HTMLElement} row - строка таблицы задачи (`<tr>`).
 * @param {string|null} reminderAtIso - значение `reminder_at` из API (UTC ISO).
 */
function syncReminderCell(row, reminderAtIso) {
    const cell = row.querySelector('.task-reminder-cell');
    if (!cell) return;

    // Не трогаем ячейку, если в ней открыт инлайн-редактор даты.
    if (cell.querySelector('.inline-date-input')) return;

    const hiddenInput = cell.querySelector('.raw-reminder-date');
    if (!hiddenInput) return;

    const pad = (n) => String(n).padStart(2, '0');

    if (!reminderAtIso) {
        // Напоминание снято на сервере — показываем иконку «Добавить».
        if (hiddenInput.value !== '') {
            cell.innerHTML = `
                <input type="hidden" class="raw-reminder-date" value="">
                <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;">
                    <i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить"></i>
                </span>
            `.trim();
        }
        return;
    }

    const date = new Date(reminderAtIso);
    if (Number.isNaN(date.getTime())) return;

    const raw = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    // Значение скрытого инпута отрендерено Django в часовом поясе сервера
    // (TIME_ZONE), а `raw` — в часовом поясе браузера. В нормальной ситуации
    // (браузер и сервер в одном поясе) совпадение означает, что время не
    // менялось, и перерисовывать ячейку не нужно.
    if (hiddenInput.value === raw) return;

    const formatted = `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    cell.innerHTML = `
        <input type="hidden" class="raw-reminder-date" value="${raw}">
        <span class="d-inline-flex align-items-center gap-1 text-warning">
            <i class="bi bi-bell-fill"></i> ${formatted}
        </span>
    `;
}
