// === РЕДАКТИРОВАНИЕ В МОДАЛЬНОМ ОКНЕ ЧЕРЕЗ HTMX ===

import { getCookie } from './secondary-system-functions.js';

export function openEditModal() {
    // 1. Находим единственный отмеченный чекбокс
    const checkedBox = document.querySelector('.task-checkbox:checked');
    if (!checkedBox) return;

    const taskId = checkedBox.getAttribute('data-id');

    // Находим строку задачи в таблице
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;

    // СРАЗУ НА СТАРТЕ: Находим контейнер тела модального окна
    const modalBody = document.querySelector('#editTaskModal .modal-body');

    // Мгновенно сбрасываем старый HTML-контент предыдущей задачи и включаем желтый спиннер
    if (modalBody) {
        modalBody.innerHTML = `
            <div class="modal-body d-flex flex-column align-items-center justify-content-center py-5 w-100">
                <div class="spinner-border text-warning mb-3" role="status" style="width: 2.5rem; height: 2.5rem; border-width: 0.25em;">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <div class="text-muted small fw-semibold placeholder-glow">
                    <span class="placeholder col-12 bg-transparent text-muted" style="letter-spacing: 0.05em;">ЗАГРУЗКА ДАННЫХ...</span>
                </div>
            </div>
        `.trim();
    }

    // 2. Извлекаем номер строки таблицы (вторая ячейка <td> по порядку)
    const rowNumber = row.querySelector('td:nth-child(2)')?.innerText.trim() || "";

    // Наполняем заголовок модального окна номером задачи
    const editTaskNumberTitle = document.getElementById('edit-task-number-title');
    if (editTaskNumberTitle) editTaskNumberTitle.innerText = rowNumber;

    if (!modalBody) return;

    // 3. Делаем прямой AJAX-запрос к вашему новому методу GET в Django (Вместо HTMX)
    fetch(`/daily/task/edit-modal/${taskId}/`, {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Не удалось загрузить форму с сервера.');
        return response.text(); // Получаем чистый HTML от Django формы
    })
    .then(htmlMarkup => {
        // Вставляем готовую, заполненную сервером форму внутрь модалки
        modalBody.innerHTML = htmlMarkup;

        // Включаем предохранитель полей периода
        const reminderInput = document.getElementById('id_reminder_at');
        const unitSelect = document.getElementById('id_periodicity_1');
        const valueInput = document.getElementById('id_periodicity_0');

        // Если у задачи уже есть периодичность (не 'none'), разблокируем поля
        if (unitSelect && unitSelect.value && unitSelect.value !== 'none') {
            if (valueInput) valueInput.disabled = false;
            unitSelect.disabled = false;
        } else if (reminderInput && typeof window.handleFieldsToggle === 'function') {
            // Иначе проверяем по дате напоминания
            window.handleFieldsToggle(reminderInput);
        }

        // Добавляем слушатель изменения селекта единиц времени для разблокировки поля количества
        if (unitSelect && valueInput) {
            unitSelect.addEventListener('change', function() {
                if (this.value !== 'none') {
                    valueInput.disabled = false;
                } else {
                    valueInput.value = '';
                    valueInput.disabled = true;
                }
            });
        }
    })
    .catch(error => {
        console.error('Ошибка загрузки модального окна:', error);
        modalBody.innerHTML = `<div class="text-danger small text-center my-3">⚠️ Ошибка загрузки: ${error.message}</div>`;
    });
}

// Функция 2: Срабатывает при отправке формы (кнопка "Сохранить изменения").
export function saveTaskChanges(event) {
    event.preventDefault(); // Предотвращаем стандартную перезагрузку страницы браузером

    const taskId = document.getElementById('edit-task-id')?.value;
    if (!taskId) {
        alert('Не удалось определить ID редактируемой задачи.');
        return;
    }

    // Находим инпуты на форме модального окна
    const titleInput = document.getElementById('id_title');
    const commentInput = document.getElementById('id_comment');
    const reminderInput = document.getElementById('id_reminder_at');
    const bookmarkSelect = document.getElementById('id_bookmark');

    // ИСПРАВЛЕНО: новые ID полей периодичности в соответствии с формой Django
    const periodValueInput = document.getElementById('id_periodicity_0');
    const periodUnitSelect = document.getElementById('id_periodicity_1');

    // Принудительно включаем инпуты перед отправкой, чтобы FormData их прочитал
    if (periodValueInput) periodValueInput.disabled = false;
    if (periodUnitSelect) periodUnitSelect.disabled = false;

    // Сбор данных в FormData
    const formData = new FormData();
    formData.append('id', taskId);
    if (titleInput) formData.append('title', titleInput.value.trim());
    if (commentInput) formData.append('comment', commentInput.value.trim());
    if (reminderInput) formData.append('reminder_at', reminderInput.value.trim());
    if (bookmarkSelect) formData.append('bookmark', bookmarkSelect.value);

    // ИСПРАВЛЕНО: передаем новые ключи полей, которые ожидает бэкенд во views.py
    const unitValue = periodUnitSelect ? periodUnitSelect.value : 'none';
    const numValue = periodValueInput ? periodValueInput.value.trim() : '';
    formData.append('periodicity_value', unitValue === 'none' ? '' : numValue);
    formData.append('periodicity_unit', unitValue);

    // Отправка POST-запроса на бэкенд контроллера TaskUpdateView
    fetch('/daily/task/update/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error('Ошибка при сохранении изменений на сервере.');
        return response.json();
    })
    .then(data => {
        if (data.status === 'success' || data.success === true) {
            const row = document.getElementById(`task-row-${taskId}`);
            if (row) {
                // 1. Обновляем текст наименования
                const nameSpan = row.querySelector('.editable-task-name');
                if (nameSpan && data.task) nameSpan.textContent = data.task.title;

                // 2. Обновляем текст комментария
                const commCell = row.querySelector('.editable-task-comment');
                if (commCell && data.task) {
                    if (data.task.comment) {
                        commCell.textContent = data.task.comment;
                        commCell.classList.remove('text-muted');
                    } else {
                        commCell.innerHTML = '<i class="bi bi-pencil add-comment-icon text-secondary" style="cursor: pointer;" title="Добавить комментарий"></i>';
                    }
                }

                // 3. Обновляем ячейку времени напоминания и её скрытый инпут
                const reminderCell = row.querySelector('.task-reminder-cell');
                if (reminderCell && data.task) {
                    const hiddenDate = reminderCell.querySelector('.raw-reminder-date');
                    if (hiddenDate) hiddenDate.value = data.task.reminder_at ? data.task.reminder_at.substring(0, 16) : "";

                    const displaySpan = reminderCell.querySelector('span');
                    if (displaySpan) {
                        if (data.task.reminder_at) {
                            const dateObj = new Date(data.task.reminder_at);
                            const formattedDate = dateObj.toLocaleDateString('ru-RU') + ' ' + dateObj.toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
                            displaySpan.className = "d-inline-flex align-items-center gap-1 text-warning";
                            displaySpan.innerHTML = `<i class="bi bi-bell-fill"></i> ${formattedDate}`;
                        } else {
                            reminderCell.innerHTML = `
                                <input type="hidden" class="raw-reminder-date" value="">
                                <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;">
                                    <i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить"></i>
                                </span>
                            `.trim();
                        }
                    }
                }

                // 4. ИСПРАВЛЕНО: Обновляем новые data-атрибуты ячейки периодичности в таблице (ВМЕСТО СЕКУНД)
                const periodicityCell = row.querySelector('.task-periodicity-cell');
                if (periodicityCell && data.task) {
                    periodicityCell.setAttribute('data-value', data.task.periodicity_value);
                    periodicityCell.setAttribute('data-unit', data.task.periodicity_unit);

                    const triggerDiv = periodicityCell.querySelector('.inline-periodicity-trigger');
                    if (triggerDiv) {
                        if (data.task.periodicity_unit !== 'none' && data.task.periodicity_value) {
                            triggerDiv.innerHTML = `
                                <i class="bi bi-arrow-repeat me-1 text-warning"></i>
                                <span class="period-text">${data.task.periodicity_display}</span>
                            `.trim();
                        } else {
                            triggerDiv.innerHTML = '<i class="bi bi-arrow-repeat text-muted"></i>';
                        }
                    }
                }

                // 5. Автоматическое обновление бейджа статуса строки задачи
                if (data.task && typeof updateRowStatusBadge === 'function') {
                    updateRowStatusBadge(taskId, data.task.status_display);
                }
            }

            // Закрываем модальное окно Bootstrap
            const modalElement = document.getElementById('editTaskModal');
            if (modalElement) {
                const modalInstance = bootstrap.Modal.getInstance(modalElement);
                modalInstance?.hide();
            }

            // Отправляем событие для снятия галочек с чекбоксов
            document.dispatchEvent(new Event('taskUpdated'));
        } else {
            alert('Ошибка при сохранении: ' + (data.error || 'Неизвестный сбой на бэкенде.'));
        }
    })
    .catch(error => {
        console.error('Ошибка при отправке изменений формы задачи:', error);
        alert('Критическая ошибка сохранения. Подробности выведены в консоль браузера.');
    });
}
