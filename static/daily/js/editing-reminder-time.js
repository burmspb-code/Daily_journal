// === ИНЛАЙН РЕДАКТИРОВАНИЕ ВРЕМЕНИ НАПОМИНАНИЯ (КАЛЕНДАРЬ) ===

export function initReminderEditing() {
    document.addEventListener('click', function(e) {
        const cell = e.target.closest('.task-reminder-cell') || e.target.closest('.remind-cell');
        if (!cell || cell.querySelector('.inline-date-input')) return;

        const taskId = cell.getAttribute('data-id') || cell.closest('tr').getAttribute('data-id');
        if (!taskId) return;

        let currentText = cell.textContent.trim().replace(/[^\d.:\s]/g, '').trim();
        let currentIsoValue = "";

        if (currentText && currentText.length >= 16) {
            const parts = currentText.match(/(\d{2})\.(\d{2})\.(\d{4})\s(\d{2}):(\d{2})/);
            if (parts) {
                currentIsoValue = `${parts[3]}-${parts[2]}-${parts[1]}T${parts[4]}:${parts[5]}`;
            }
        }

        cell.dataset.oldHtml = cell.innerHTML;
        cell.innerHTML = `
            <input type="datetime-local" class="form-control form-control-sm inline-date-input" value="${currentIsoValue}"
                   style="outline: none; width: 100%; max-width: 170px; display: inline-block !important;"
                   onkeydown="handleDateKey(event, this)" onblur="saveInlineDate(this, '${taskId}')">
        `;

        setTimeout(() => {
            const input = cell.querySelector('.inline-date-input');
            if (input) {
                input.focus();
                if (typeof input.showPicker === 'function') input.showPicker();
            }
        }, 15);
    });
}

function handleDateKey(event, input) {
    if (event.key === 'Enter') { event.preventDefault(); input.blur(); }
    else if (event.key === 'Escape') {
        event.preventDefault();
        const cell = input.parentElement;
        cell.innerHTML = cell.dataset.oldHtml || `<span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;"><i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i></span>`;
    }
}

function saveInlineDate(input, taskId) {
    const cell = input.parentElement;
    const newDateTime = input.value;

    if (input.value === input.defaultValue && cell.dataset.oldHtml) {
        cell.innerHTML = cell.dataset.oldHtml;
        return;
    }

    // Проверяем, что время в будущем (если значение не пустое)
    if (newDateTime) {
        const selectedDate = new Date(newDateTime);
        const now = new Date();
        if (selectedDate < now) {
            // Показываем модальное окно предупреждения
            const modal = new bootstrap.Modal(document.getElementById('pastTimeWarningModal'));
            modal.show();
            // Восстанавливаем старое значение
            cell.innerHTML = cell.dataset.oldHtml || `
                <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;">
                    <i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i>
                </span>`;
            return;
        }
    }

    const formData = new FormData();
    formData.append('id', taskId);
    formData.append('reminder_at', newDateTime);

    fetch('/daily/task/update/', {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie('csrftoken')
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => { throw new Error(data.error || 'Ошибка сервера'); });
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            const row = cell.closest('tr');
            // Находим сопряженную ячейку периодичности в этой же строке
            const periodicityCell = row ? row.querySelector('.task-periodicity-cell') : null;

            if (data.task.reminder_at) {
                const dateObj = new Date(data.task.reminder_at);
                const formattedDate = dateObj.toLocaleString('ru-RU', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                });

                cell.innerHTML = `
                    <input type="hidden" class="raw-reminder-date" value="${data.task.reminder_at}">
                    <span class="d-inline-flex align-items-center gap-1 text-warning">
                        <i class="bi bi-bell-fill"></i> ${formattedDate}
                    </span>`;
            } else {
                // СРАБОТАЛА КНОПКА "УДАЛИТЬ" В КАЛЕНДАРЕ
                cell.innerHTML = `
                    <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;">
                        <i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i>
                    </span>`;

                // СИНХРОННО СБРАСЫВАЕМ И БЛОКИРУЕМ ПЕРИОДИЧНОСТЬ НА ЭКРАНЕ
                if (periodicityCell) {
                    // 1. Сбрасываем сохраненные секунды в DOM в 0
                    periodicityCell.setAttribute('data-seconds', '0');

                    // 2. Стираем надпись периода (например, "1 г.") и возвращаем серую иконку
                    const trigger = periodicityCell.querySelector('.inline-periodicity-trigger');
                    if (trigger) {
                        trigger.innerHTML = `<i class="bi bi-arrow-repeat text-muted"></i>`;
                    }
                }
            }

            if (typeof updateRowStatusBadge === "function") {
                updateRowStatusBadge(taskId, data.task.status);
            }
        }
    })
    .catch(error => {
        alert("Не удалось сохранить время напоминания. Причина: " + error.message);
        cell.innerHTML = cell.dataset.oldHtml || `
            <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;">
                <i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i>
            </span>`;
    });
}

// Экспонируем функции в глобальную область видимости для HTML-атрибутов
window.handleDateKey = handleDateKey;
window.saveInlineDate = saveInlineDate;