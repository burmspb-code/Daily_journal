// === Модуль для инлайн-управления статусом задачи прямо в таблице ===
import { getCookie } from './secondary-system-functions.js';
import { renderTaskStatusCell } from './secondary-system-functions.js';

function showToast(message) {
    if (!message) return;

    let container = document.getElementById('task-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'task-toast-container';
        container.className = 'position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1090';
        document.body.appendChild(container);
    }

    const toastEl = document.createElement('div');
    toastEl.className = 'toast align-items-center text-bg-dark border-0';
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto"
                    data-bs-dismiss="toast" aria-label="Закрыть"></button>
        </div>
    `;
    container.appendChild(toastEl);

    const bsToast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 5000 });
    bsToast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

function updateReminderTime(cell, isoString) {
    if (!isoString) return;

    const row = cell.closest('tr');
    if (!row) return;

    const reminderCell = row.querySelector('.task-reminder-cell');
    if (!reminderCell) return;

    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return;

    const pad = (n) => String(n).padStart(2, '0');
    const formatted = `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    const raw = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;

    const rawInput = reminderCell.querySelector('.raw-reminder-date');
    if (rawInput) rawInput.value = raw;

    reminderCell.innerHTML = `
        <input type="hidden" class="raw-reminder-date" value="${raw}">
        <span class="d-inline-flex align-items-center gap-1 text-warning">
            <i class="bi bi-bell-fill"></i> ${formatted}
        </span>
    `;
}

export function initInlineStatusEditor() {
    const tableBody = document.getElementById('tasks-table-body');
    if (!tableBody) return;

    // Обработка клика на кнопку "Выполнена"/"Завершить цикл" в dropdown меню
    tableBody.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-mark-completed');
        if (!btn) return;

        const taskId = btn.getAttribute('data-task-id');
        const newStatus = btn.getAttribute('data-status');
        const cell = btn.closest('.task-status-cell');

        if (!taskId || !newStatus || !cell) return;

        // Закрываем выпадающее меню статуса перед обновлением ячейки.
        const toggleBtn = cell.querySelector('[data-bs-toggle="dropdown"]');
        if (toggleBtn) {
            const bsDropdown = bootstrap.Dropdown.getInstance(toggleBtn);
            if (bsDropdown) bsDropdown.hide();
        }

        // Смена статуса выполняется сразу, без подтверждающего окна.
        changeTaskStatus(taskId, newStatus, cell);
    });
}

/**
 * Отправляет запрос на смену статуса и обновляет ячейку по ответу сервера.
 *
 * @param {string} taskId - ID задачи.
 * @param {string} newStatus - Новый флаг статуса.
 * @param {HTMLElement} cell - Ячейка `.task-status-cell` этой задачи.
 */
function changeTaskStatus(taskId, newStatus, cell) {
    const formData = new FormData();
    formData.append('task_id', taskId);
    formData.append('status_flag', newStatus);

    fetch('/daily/task/update-status/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error('Ошибка сервера');
        return response.json();
    })
    .then(data => {
        if (data.success === false) {
            showToast('Ошибка при изменении статуса: ' + (data.error || 'Неизвестная ошибка'));
            return;
        }

        // Полностью перерисовываем ячейку статуса: сохраняем обёртку-триггер
        // и меню «Изменить статус», чтобы с задачей можно было продолжать
        // взаимодействовать (наведение/клик по бейджу).
        renderTaskStatusCell(cell, data.status, Boolean(data.is_periodic));

        if (data.is_periodic && data.reminder_at) {
            updateReminderTime(cell, data.reminder_at);
        }

        showToast(data.message);
    })
    .catch(error => {
        console.error("Ошибка изменения статуса:", error);
        showToast("Не удалось изменить статус. Подробности в консоли.");
    });
}
