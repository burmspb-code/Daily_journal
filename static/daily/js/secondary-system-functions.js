// === ВСПОМОГАТЕЛЬНЫЕ СИСТЕМНЫЕ ФУНКЦИИ ===

import { getStatusConfig } from './status-icons-config.js';

export function updateTopTaskCounter(amount) {
    const tasksCountBadge = document.getElementById('tasks-count-badge');
    if (tasksCountBadge) {
        const currentCount = parseInt(tasksCountBadge.textContent.replace(/\D/g, '')) || 0;
        tasksCountBadge.textContent = `Найдено задач: ${currentCount + amount}`;
    }
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
    // ИСПРАВЛЕНО: colspan="8", так как добавился столбец "Повторение"
    if (tbody && tbody.querySelectorAll('tr').length === 0) {
        tbody.innerHTML = `<tr id="no-tasks-row"><td colspan="8" class="text-center text-muted py-3">Нет задач в этой закладке</td></tr>`;
    }
}

// Статусы, для которых в ячейке есть выпадающее меню «Изменить статус».
// Аналогично условию в шаблоне daily/includes/task_row.html: у «Выполнена» (2)
// меню не рендерится, поэтому и триггер дропдауна создавать не нужно.
const STATUSES_WITH_DROPDOWN = [0, 1, 3];

/**
 * Полностью перерисовывает ячейку статуса задачи под новый флаг.
 *
 * Раньше обновлялся только сам `.badge`, из-за чего ломалась разметка:
 * у ячейки пропадала обёртка-триггер дропдауна (`inline-status-trigger`) и
 * меню «Изменить статус», поэтому после смены статуса с задачей нельзя было
 * взаимодействовать наведением мыши. Здесь ячейка собирается заново ровно
 * так же, как в шаблоне, включая триггер и меню для статусов 0/1/3.
 *
 * @param {HTMLElement} cell - ячейка `.task-status-cell`.
 * @param {number|string} flagValue - новый флаг статуса.
 * @param {boolean} isPeriodic - периодическая ли задача (меняет текст кнопки).
 */
export function renderTaskStatusCell(cell, flagValue, isPeriodic = false) {
    if (!cell) return;

    const config = getStatusConfig(flagValue);
    if (!config) return;

    const flag = parseInt(flagValue, 10);
    const taskId = cell.getAttribute('data-id') || '';

    const badge = `
        <span class="badge ${config.bg}"
              title="${config.text}" data-status="${flag}">
            <i class="bi ${config.icon}"></i> ${config.text}
        </span>
    `.trim();

    let triggerHtml;
    if (STATUSES_WITH_DROPDOWN.includes(flag)) {
        triggerHtml = `
            <div class="inline-status-trigger d-inline-block cursor-pointer"
                 data-bs-toggle="dropdown"
                 data-bs-auto-close="outside"
                 aria-expanded="false"
                 style="cursor: pointer;">
                ${badge}
            </div>
        `.trim();
    } else {
        triggerHtml = badge;
    }

    let dropdownHtml = '';
    if (STATUSES_WITH_DROPDOWN.includes(flag)) {
        const actionLabel = isPeriodic ? 'Завершить цикл' : 'Выполнена';
        dropdownHtml = `
            <div class="dropdown-menu p-2 shadow-lg border" style="min-width: 180px; z-index: 1050;">
                <div class="mb-2 text-center border-bottom pb-2">
                    <strong class="text-dark small">Изменить статус</strong>
                </div>
                <button type="button"
                        class="dropdown-item d-flex align-items-center gap-2 btn-mark-completed"
                        data-task-id="${taskId}"
                        data-status="2">
                    <i class="bi bi-check2-circle text-secondary"></i>
                    ${actionLabel}
                </button>
            </div>
        `.trim();
    }

    cell.setAttribute('data-status', flag);
    cell.innerHTML = triggerHtml + dropdownHtml;
}

export function updateRowStatusBadge(taskId, flagValue) {
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;

    const cell = row.querySelector('.task-status-cell');
    if (!cell) return;

    const isPeriodic = row.getAttribute('data-periodic') === '1';
    renderTaskStatusCell(cell, flagValue, isPeriodic);
}

export function getCookie(name) {
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
}

// Варианты оформления уведомления: иконка, цвет и заголовок по умолчанию.
const NOTIFICATION_TYPES = {
    info: { icon: 'bi-info-circle', color: 'text-warning', title: 'Уведомление' },
    success: { icon: 'bi-check2-circle', color: 'text-success', title: 'Готово' },
    error: { icon: 'bi-exclamation-triangle', color: 'text-danger', title: 'Ошибка' },
};

/**
 * Показывает уведомление в общем модальном окне по центру экрана.
 *
 * Единый стиль с окнами проекта: тот же матовый тёмный каркас, что и у
 * редактирования задачи. Заменяет собой всплывающие toast-сообщения в углу.
 *
 * @param {string} message - Текст уведомления.
 * @param {string} [type="info"] - Тип: `info`, `success` или `error`.
 */
export function showNotification(message, type = 'info') {
    if (!message) return;

    const modalEl = document.getElementById('notificationModal');
    if (!modalEl) {
        // Fallback: окна нет в разметке — хотя бы покажем сообщение пользователю.
        console.warn('Модальное окно #notificationModal не найдено:', message);
        return;
    }

    const cfg = NOTIFICATION_TYPES[type] || NOTIFICATION_TYPES.info;

    const titleEl = document.getElementById('notification-modal-title');
    if (titleEl) titleEl.textContent = cfg.title;

    const iconEl = document.getElementById('notification-modal-icon');
    if (iconEl) iconEl.className = `bi ${cfg.icon} ${cfg.color} me-2`;

    const textEl = document.getElementById('notification-modal-text');
    if (textEl) textEl.textContent = message;

    bootstrap.Modal.getOrCreateInstance(modalEl).show();
}
