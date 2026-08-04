// === РЕДАКТИРОВАНИЕ В МОДАЛЬНОМ ОКНЕ ===

// Функция 1: Срабатывает при клике на верхнюю кнопку "Редактировать".
export function openEditModal() {
    // Находим единственный отмеченный чекбокс
    const checkedBox = document.querySelector('.task-checkbox:checked');
    if (!checkedBox) return;

    const taskId = checkedBox.getAttribute('data-id');

    // Находим строку задачи в таблице
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;

    // 1. Извлекаем название
    const title = row.querySelector('.editable-task-name')?.innerText.trim() || "";

    // 2. Извлекаем комментарий (очищаем от иконки карандаша, если текста нет)
    const commentCell = row.querySelector('.editable-task-comment');
    const hasPencil = commentCell?.querySelector('.add-comment-icon');
    const comment = hasPencil ? "" : (commentCell?.innerText.trim() || "");

    // 3. Номер строки таблицы (вторая ячейка <td> по порядку)
    const rowNumber = row.querySelector('td:nth-child(2)')?.innerText.trim() || "";

    // 4. Безопасно забираем "сырую" дату из скрытого инпута внутри ячейки, не ломая data-id таблицы
    const reminderCell = row.querySelector('.task-reminder-cell') || row.querySelector('.remind-cell');
    const hiddenDateInput = reminderCell ? reminderCell.querySelector('.raw-reminder-date') : null;
    let rawReminder = hiddenDateInput ? hiddenDateInput.value.trim() : "";

    // На случай, если скрытого инпута нет, но текст с датой в ячейке присутствует
    if (!rawReminder && reminderCell) {
        const cellText = reminderCell.textContent.trim().replace(/[^\d.:\s]/g, '').trim();
        if (cellText && cellText.length >= 16) {
            const parts = cellText.match(/(\d{2})\.(\d{2})\.(\d{4})\s(\d{2}):(\d{2})/);
            if (parts) {
                // Превращаем "02.08.2026 19:23" в "2026-08-02T19:23"
                rawReminder = `${parts[3]}-${parts[2]}-${parts[1]}T${parts[4]}:${parts[5]}`;
            }
        }
    }

    if (rawReminder) {
        // Приводим к стандарту HTML5 datetime-local (длина 16 символов: YYYY-MM-DDTHH:mm)
        rawReminder = rawReminder.replace(' ', 'T').substring(0, 16);
    }

    // 5. Мгновенно вытаскиваем ID текущей закладки из заголовка страницы
    const bookmarkNameElement = document.querySelector('.editable-bookmark-name');
    const bookmarkId = bookmarkNameElement ? bookmarkNameElement.getAttribute('data-id') : "";

    // 6. Извлекаем текущий статус на основе текста бейджа в последней ячейке строки таблицы
    const statusCell = row.querySelector('td:last-child');
    let currentStatusFlag = "0"; // По умолчанию "Создана" (0)

    if (statusCell) {
        const statusText = statusCell.innerText.trim();
        if (statusText.includes("Просрочено") || statusText.includes("Дедлайн")) {
            currentStatusFlag = "3";
        } else if (statusText.includes("Создана") || statusText.includes("В работе")) {
            currentStatusFlag = "0";
        }
    }

    // Наполняем элементы модального окна перед показом
    document.getElementById('edit-task-id').value = taskId;
    document.getElementById('edit-task-number-title').innerText = rowNumber;

    // Заполняем инпуты по ID, сгенерированным Django Forms ({% for field in form %})
    if (document.getElementById('id_title')) document.getElementById('id_title').value = title;
    if (document.getElementById('id_comment')) document.getElementById('id_comment').value = comment;
    if (document.getElementById('id_reminder_at')) document.getElementById('id_reminder_at').value = rawReminder;

    // Передаем ID закладки в выпадающий список формы Django
    if (document.getElementById('id_bookmark')) document.getElementById('id_bookmark').value = bookmarkId;

    // ИСПРАВЛЕНО: Передаем текущий статус задачи в выпадающий список Django-формы по ID 'id_flag'
    if (document.getElementById('id_flag')) document.getElementById('id_flag').value = currentStatusFlag;
}

// Функция 2: Сохранение изменений
export function saveTaskChanges(event) {
    event.preventDefault(); // Обязательно: останавливаем стандартную отправку формы

    const taskId = document.getElementById('edit-task-id')?.value;
    const form = document.getElementById('edit-task-form');

    if (!taskId || !form) {
        console.error('Не найдены ID задачи или форма');
        return;
    }

    // 1. Получаем значение названия напрямую, чтобы сделать свою валидацию
    const titleInput = document.getElementById('id_title');
    const newTitle = titleInput ? titleInput.value.trim() : "";

    if (!newTitle) {
        alert("Наименование задачи не может быть пустым!");
        titleInput.focus();
        return; // Прерываем, ничего не отправляем
    }

    // 2. Собираем данные через FormData (это правильно для Django форм)
    const formData = new FormData(form);
    formData.set('id', taskId); // Явно гарантируем передачу 'id'
    formData.set('title', newTitle); // Явно гарантируем передачу 'title'

    // Функция для получения CSRF токена
    function getCookie(name) {
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

    // 3. Отправляем запрос
    fetch('/daily/task/update-api/', {
        method: 'POST',
        body: formData, // Отправляем FormData, НЕ JSON
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
            // ВАЖНО: НЕ ставь здесь 'Content-Type: application/json'!
            // Браузер сам поставит правильный Content-Type (multipart/form-data) для FormData
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Ошибка сервера');
        return response.json();
    })
    .then(data => {
        console.log('Успех:', data);
        const row = document.getElementById(`task-row-${taskId}`);

        if (row) {
            // 1. Наименование задачи
            const titleCell = row.querySelector('.editable-task-name');
            if (titleCell) {
                titleCell.innerText = data.task.title || '';
            }

            // 2. Комментарий задачи
            const commentCell = row.querySelector('.editable-task-comment');
            if (commentCell) {
                if (data.task.comment && data.task.comment.trim() !== '') {
                    commentCell.innerText = data.task.comment;
                    commentCell.classList.remove('text-muted');
                } else {
                    commentCell.classList.add('text-muted');
                    commentCell.innerHTML = '<i class="bi bi-pencil add-comment-icon text-secondary" title="Добавить"></i>';
                }
            }

            // 3. Напоминание даты и времени
            const reminderCell = row.querySelector('.task-reminder-cell');
            if (reminderCell) {
                if (data.task.reminder_at) {
                    // Безопасный парсинг даты ISO из Django
                    const dateObj = new Date(data.task.reminder_at);

                    if (!isNaN(dateObj.getTime())) { // Проверяем, что дата распарсилась корректно
                        const formattedDate = dateObj.toLocaleString('ru-RU', {
                            day: '2-digit', month: '2-digit', year: 'numeric',
                            hour: '2-digit', minute: '2-digit'
                        }).replace(',', ''); // Убираем возможную запятую между датой и временем

                        reminderCell.innerHTML = `
                            <input type="hidden" class="raw-reminder-date" value="${data.task.reminder_at}">
                            <span class="d-inline-flex align-items-center gap-1 text-warning">
                                <i class="bi bi-bell-fill"></i> ${formattedDate}
                            </span>`.trim();
                    }
                } else {
                    reminderCell.innerHTML = `
                        <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;">
                            <i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить"></i>
                        </span>`.trim();
                }
            }

            // 4. Статус задачи (Полностью синхронизирован с ТЗ и Django-шаблоном)
            const statusCell = row.querySelector('.task-status-cell');
            if (statusCell) {
                const statusCode = data.task.status;
                const statusText = data.task.status_display || '';

                const statusConfig = {
                    0: { bg: 'bg-success text-white', icon: 'bi-plus-circle-fill', title: 'Создана' },
                    1: { bg: 'bg-warning text-dark', icon: 'bi-gear-fill', title: 'В работе' },
                    2: { bg: 'bg-secondary text-white', icon: 'bi-check-circle-fill', title: 'Выполнена' },
                    3: { bg: 'bg-danger text-white', icon: 'bi-exclamation-triangle-fill', title: 'Дедлайн' }
                };

                // Корректная проверка: ищем ключ в объекте, если его нет (undefined) — берем статус 0
                const config = (statusCode in statusConfig) ? statusConfig[statusCode] : statusConfig[0];

                statusCell.innerHTML = `
                    <span class="badge rounded-pill ${config.bg} px-2 py-1 d-inline-flex align-items-center gap-1" title="${config.title}">
                        <i class="bi ${config.icon}"></i> ${statusText}
                    </span>
                `.trim();
            }

            // 5. Проверка изменения закладки (если задачу перенесли в другую закладку, удаляем строку)
            const currentBookmarkElement = document.querySelector('.editable-bookmark-name');
            const currentBookmarkId = currentBookmarkElement ? currentBookmarkElement.getAttribute('data-id') : "";

            if (data.task.bookmark_id && currentBookmarkId && String(data.task.bookmark_id) !== String(currentBookmarkId)) {
                row.remove();
            }
        }

        // --- СБРОС ВЫДЕЛЕНИЙ ---
        const taskCheckbox = document.querySelector(`.task-checkbox[data-id="${taskId}"]`);
        if (taskCheckbox) taskCheckbox.checked = false;

        const selectAllCheckbox = document.getElementById('select-all-tasks');
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        document.getElementById('btn-delete-selected')?.classList.add('d-none');
        document.getElementById('btn-edit-selected')?.classList.add('d-none');

        const selectedCountSpan = document.getElementById('selected-count');
        if (selectedCountSpan) selectedCountSpan.textContent = '0';

        // Закрываем модалку
        const modalElement = document.getElementById('editTaskModal');
        if (modalElement) {
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            if (modalInstance) modalInstance.hide();
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        alert('Произошла ошибка при сохранении. Проверьте консоль.');
    });
}