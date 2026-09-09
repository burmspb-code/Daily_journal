// === Модуль для инлайн-управления статусом задачи прямо в таблице ===
import { getCookie } from './secondary-system-functions.js';

export function initInlineStatusEditor() {
    const tableBody = document.getElementById('tasks-table-body');
    if (!tableBody) return;

    // Обработка клика на кнопку "Выполнена" в dropdown меню
    tableBody.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-mark-completed');
        if (!btn) return;

        const taskId = btn.getAttribute('data-task-id');
        const newStatus = btn.getAttribute('data-status');
        const cell = btn.closest('.task-status-cell');

        if (!taskId || !newStatus || !cell) return;

        // Отправка AJAX-запроса на бэкенд
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
                alert('Ошибка при изменении статуса: ' + (data.error || 'Неизвестная ошибка'));
                return;
            }

            // Обновляем data-атрибут ячейки
            cell.setAttribute('data-status', data.status);

            // Заменяем содержимое ячейки на новый статус (Выполнена)
            cell.innerHTML = `
                <span class="badge bg-transparent text-secondary p-0 fw-medium d-inline-flex align-items-center justify-content-center gap-2 fs-6"
                      title="Выполнена" data-status="${data.status}">
                    <i class="bi bi-check2-circle"></i> Выполнена
                </span>
            `;

            // Закрываем выпадающий список Bootstrap
            const toggleBtn = cell.querySelector('[data-bs-toggle="dropdown"]');
            if (toggleBtn) {
                const bsDropdown = bootstrap.Dropdown.getOrCreateInstance(toggleBtn);
                if (bsDropdown) bsDropdown.hide();
            }
        })
        .catch(error => {
            console.error("Ошибка изменения статуса:", error);
            alert("Не удалось изменить статус. Подробности в консоли.");
        });
    });
}
