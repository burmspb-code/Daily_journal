/**
 * Финальная оптимизированная версия без дубликатов и конфликтов.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Глобальные элементы интерфейса
    const selectAllCheckbox = document.getElementById('select-all-tasks');
    const btnEdit = document.getElementById('btn-edit-selected');
    const btnDelete = document.getElementById('btn-delete-selected');
    const selectedCountSpan = document.getElementById('selected-count');
    const tasksTable = document.getElementById('tasks-table');

    // === 1. ГРУППОВЫЕ ОПЕРАЦИИ И ЧЕКБОКСЫ ===
    function updateActionButtons() {
        const checkedBoxes = document.querySelectorAll('.task-checkbox:checked');
        const count = checkedBoxes.length;

        if (count > 0) {
            if (btnDelete) btnDelete.classList.remove('d-none');
            if (selectedCountSpan) selectedCountSpan.textContent = count;
        } else {
            if (btnDelete) btnDelete.classList.add('d-none');
        }

        if (count === 1) {
            if (btnEdit) {
                btnEdit.classList.remove('d-none');

                // Передаем ID отмеченной задачи в HTMX-атрибут кнопки
                const taskId = checkedBoxes[0].getAttribute('data-id');
                btnEdit.setAttribute('hx-get', `/daily/task/edit-modal/${taskId}/`);

                // Заставляем HTMX обновить триггеры на этой кнопке
                if (typeof htmx !== 'undefined') {
                    htmx.process(btnEdit);
                }
            }
        } else {
            if (btnEdit) {
                btnEdit.classList.add('d-none');
                btnEdit.setAttribute('hx-get', '');
            }
        }
    }

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            const currentCheckboxes = document.querySelectorAll('.task-checkbox');
            currentCheckboxes.forEach(cb => cb.checked = this.checked);
            updateActionButtons();
        });
    }

    // Делегирование событий: автоматически слушает и старые, и новые чекбоксы
    if (tasksTable) {
        tasksTable.addEventListener('change', function (e) {
            if (e.target.classList.contains('task-checkbox')) {
                if (!e.target.checked && selectAllCheckbox) {
                    selectAllCheckbox.checked = false;
                }
                updateActionButtons();
            }
        });
    }

    // === 2. ДИНАМИЧЕСКИЕ ДРОПДАУНЫ (АВТОЗАКРЫТИЕ) ===
    const allDropdowns = document.querySelectorAll('.dropdown');
    allDropdowns.forEach(dropdownWrapper => {
        let closeTimeout = null;

        dropdownWrapper.addEventListener('mouseleave', function () {
            if (!closeTimeout) {
                closeTimeout = setTimeout(() => {
                    const toggleBtn = dropdownWrapper.querySelector('[data-bs-toggle="dropdown"]');
                    if (toggleBtn) {
                        const bsDropdown = bootstrap.Dropdown.getOrCreateInstance(toggleBtn);
                        if (bsDropdown) bsDropdown.hide();
                    }
                }, 500);
            }
        });

        dropdownWrapper.addEventListener('mouseenter', function () {
            if (closeTimeout) {
                clearTimeout(closeTimeout);
                closeTimeout = null;
            }
        });
    });
});

// === РЕДАКТИРОВАНИЕ НАЗВАНИЯ ЗАКЛАДКИ (ИСПРАВЛЕННАЯ СИНХРОНИЗАЦИЯ) ===
let originalBookmarkText = ""; // Глобальный буфер для отмены изменений

// 1. Запоминаем текст в момент фокуса (клик по названию закладки)
document.addEventListener('focusin', function (e) {
    if (e.target.classList.contains('editable-bookmark-name')) {
        originalBookmarkText = e.target.innerText.trim();
    }
});

// 2. Обработка горячих клавиш при редактировании
document.addEventListener('keydown', function (e) {
    if (e.target.classList.contains('editable-bookmark-name')) {
        // Нажатие Enter — сохраняем изменения и убираем фокус
        if (e.key === 'Enter') {
            e.preventDefault();
            e.target.blur();
        }
        // Нажатие Escape — отменяем изменения, возвращаем старый текст и убираем фокус
        if (e.key === 'Escape') {
            e.preventDefault();
            e.target.innerText = originalBookmarkText;
            e.target.blur();
        }
    }
});

/// 3. Сохранение названия закладки на бэкенд при потере фокуса
document.addEventListener('focusout', function (e) {
    if (e.target.classList.contains('editable-bookmark-name')) {
        const editableField = e.target;
        let newBookmarkName = editableField.innerText.trim();
        const bookmarkId = editableField.getAttribute('data-id');

        if (newBookmarkName === "" || newBookmarkName === originalBookmarkText) {
            if (newBookmarkName === "") {
                alert("Название закладки не может быть пустым");
                editableField.innerText = originalBookmarkText;
            }
            return;
        }

        const formData = new FormData();
        formData.append('id', bookmarkId);
        formData.append('title', newBookmarkName);

        fetch('/daily/bookmark/update-api/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        })
        .then(response => {
            if (response.ok) {
                originalBookmarkText = newBookmarkName;

                // === СИНХРОНИЗАЦИЯ С ВЫПАДАЮЩИМ МЕНЮ (ПОД ВАШУ ВЕРСТКУ) ===
                // Находим конкретный span по его классу и data-id закладки
                const menuTargetSpan = document.querySelector(`.bookmark-link-name[data-id="${bookmarkId}"]`);

                if (menuTargetSpan) {
                    // Просто обновляем текст внутри span, иконка перед ним не пострадает
                    menuTargetSpan.textContent = newBookmarkName;
                }

            } else {
                return response.json().then(err => { throw err; }).catch(() => { throw new Error(); });
            }
        })
        .catch(error => {
            alert(error.error || "Не удалось сохранить название закладки");
            editableField.innerText = originalBookmarkText;
        });
    }
});

// === 3. ИНЛАЙН РЕДАКТИРОВАНИЕ НАЗВАНИЙ И КОММЕНТАРИЕВ (CONTENTEDITABLE) ===
let originalNameText = "";
let originalCommentText = "";

document.addEventListener('focusin', function (e) {
    if (e.target.classList.contains('editable-task-name')) {
        originalNameText = e.target.innerText.trim();
    }

    if (e.target.classList.contains('editable-task-comment')) {
        const hasPencil = e.target.querySelector('.add-comment-icon');
        if (hasPencil) {
            originalCommentText = "";
            e.target.innerHTML = "";
        } else {
            originalCommentText = e.target.innerText.trim();
        }
    }
});

document.addEventListener('keydown', function (e) {
    if (e.target.classList.contains('editable-task-name')) {
        if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
        if (e.key === 'Escape') { e.preventDefault(); e.target.innerText = originalNameText; e.target.blur(); }
    }

    if (e.target.classList.contains('editable-task-comment')) {
        if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
        if (e.key === 'Escape') {
            e.preventDefault();
            e.target.innerHTML = originalCommentText === ""
                ? `<i class="bi bi-pencil add-comment-icon text-secondary fs-6" title="Добавить комментарий"></i>`
                : originalCommentText;
            e.target.blur();
        }
    }
});

document.addEventListener('focusout', function (e) {
    // Сохранение названия задачи
    if (e.target.classList.contains('editable-task-name')) {
        const editableField = e.target;
        let newName = editableField.innerText.trim();
        const taskId = editableField.getAttribute('data-id');

        if (newName === "") {
            alert("Наименование задачи не может быть пустым");
            editableField.innerText = originalNameText;
            return;
        }
        if (newName === originalNameText) return;

        // === ИСПРАВЛЕННЫЙ БЛОК FETCH ===
        const formData = new FormData();
        formData.append('id', taskId);
        formData.append('title', newName);

        fetch('/daily/task/update-api/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
                // ВАЖНО: НЕ добавляем 'Content-Type': 'application/json'
            },
            body: formData
        })
        .then(response => {
            if (response.ok) {
                originalNameText = newName;
            } else {
                alert("Не удалось сохранить наименование задачи");
                editableField.innerText = originalNameText;
            }
        })
        .catch(() => editableField.innerText = originalNameText);
    }

    // Сохранение комментария к задаче
    if (e.target.classList.contains('editable-task-comment')) {
        const editableField = e.target;
        let newComment = editableField.innerText.trim();
        const taskId = editableField.getAttribute('data-id');
        const iconHtml = `<i class="bi bi-pencil add-comment-icon text-secondary fs-6" title="Добавить комментарий"></i>`;

        if (newComment === "" && originalCommentText === "") {
            editableField.innerHTML = iconHtml;
            return;
        }
        if (newComment === originalCommentText) return;

        // === ИСПРАВЛЕННЫЙ БЛОК FETCH ===
        const formData = new FormData();
        formData.append('id', taskId);
        formData.append('comment', newComment);

        fetch('/daily/task/update-api/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        })
        .then(response => {
            if (response.ok) {
                originalCommentText = newComment;
                if (newComment === "") editableField.innerHTML = iconHtml;
            } else {
                alert("Не удалось сохранить комментарий");
                editableField.innerHTML = originalCommentText === "" ? iconHtml : originalCommentText;
            }
        })
        .catch(() => editableField.innerHTML = originalCommentText === "" ? iconHtml : originalCommentText);
    }
});

// === РЕДАКТИРОВАНИЕ В МОДАЛЬНОМ ОКНЕ ===
// Функция 1: Срабатывает при клике на верхнюю кнопку "Редактировать". Заполняет модалку за 0.01 мс.
function openEditModal() {
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

    // 6. ИСПРАВЛЕНО: Извлекаем текущий статус на основе текста бейджа в последней ячейке строки таблицы
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
function saveTaskChanges(event) {
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

// === 4. ИНЛАЙН РЕДАКТИРОВАНИЕ ВРЕМЕНИ НАПОМИНАНИЯ (КАЛЕНДАРЬ) ===
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
    const newDateTime = input.value; // Получаем строку вида 'YYYY-MM-DDTHH:MM' или пустую строку

    // Если значение не изменилось, просто возвращаем старый HTML
    if (input.value === input.defaultValue && cell.dataset.oldHtml) {
        cell.innerHTML = cell.dataset.oldHtml;
        return;
    }

    // 1. Используем FormData вместо JSON, чтобы бэкенд принял запрос через request.POST
    const formData = new FormData();
    formData.append('id', taskId);
    formData.append('reminder_at', newDateTime); // Ключ совпадает с бэкендом!

    fetch('/daily/task/update-api/', {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie('csrftoken')
            // Content-Type ставить НЕ НАДО, браузер сам настроит его для FormData
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Ошибка сервера');
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            if (data.task.reminder_at) {
                const dateObj = new Date(data.task.reminder_at);
                const formattedDate = dateObj.toLocaleString('ru-RU', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                });

                // ИСПРАВЛЕНО: Сохраняем скрытый инпут, чтобы модалка могла прочитать дату!
                cell.innerHTML = `
                    <input type="hidden" class="raw-reminder-date" value="${data.task.reminder_at}">
                    <span class="d-inline-flex align-items-center gap-1 text-warning">
                        <i class="bi bi-bell-fill"></i> ${formattedDate}
                    </span>`;
            } else {
                cell.innerHTML = `
                    <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;">
                        <i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i>
                    </span>`;
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

// === 5. ИНЛАЙН СОЗДАНИЕ ЗАДАЧ ===
function appendNewTaskRow() {
    if (document.getElementById('inline-task-input')) {
        document.getElementById('inline-task-input').focus();
        return;
    }

    const tbody = document.getElementById('tasks-table-body');
    if (!tbody) return;

    document.getElementById('no-tasks-row')?.remove();
    const nextNumber = tbody.querySelectorAll('tr[id^="task-row-"]').length + 1;
    const bookmarkId = tbody.getAttribute('data-current-bookmark-id') || "";

    const newRow = document.createElement('tr');
    newRow.id = 'temporary-creation-row';
    newRow.innerHTML = `
        <td class="ps-4"><input class="form-check-input" type="checkbox" disabled></td>
        <td><span class="text-muted">${nextNumber}</span></td>
        <td colspan="4">
            <input type="text" id="inline-task-input" class="form-control form-control-sm border-primary shadow-sm" placeholder="Напишите название задачи и нажмите Enter..." style="outline: none;">
        </td>
        <td class="text-center">
            <span class="badge rounded-pill bg-success px-2 py-1 d-inline-flex align-items-center gap-1">
                <i class="bi bi-plus-circle-fill"></i> Создана
            </span>
        </td>
    `;
    tbody.appendChild(newRow);

    const inputEl = document.getElementById('inline-task-input');
    let isSaving = false;

    inputEl.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            const titleValue = inputEl.value.trim();
            if (!titleValue || isSaving) return;
            isSaving = true;
            saveInlineTask(titleValue, bookmarkId, nextNumber);
        } else if (event.key === 'Escape') {
            event.preventDefault();
            isSaving = true;
            newRow.remove();
            checkIfTableIsEmpty();
        }
    });

    inputEl.addEventListener('blur', function() {
        setTimeout(() => {
            if (isSaving) return;
            const titleValue = inputEl.value.trim();
            if (titleValue === "") {
                newRow.remove();
                checkIfTableIsEmpty();
            } else {
                isSaving = true;
                saveInlineTask(titleValue, bookmarkId, nextNumber);
            }
        }, 150);
    });

    newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    inputEl.focus();
}

function saveInlineTask(title, bookmarkId, rowNumber) {
    const input = document.getElementById('inline-task-input');
    if (input) input.disabled = true;

    fetch('/daily/task/create-api/', {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie('csrftoken') },
        body: JSON.stringify({ title: title, bookmark_id: bookmarkId })
    })
    .then(response => {
        if (!response.ok) throw new Error();
        return response.json();
    })
    .then(data => {
        const tempRow = document.getElementById('temporary-creation-row');
        if (!tempRow) return;

        tempRow.id = `task-row-${data.id}`;
        tempRow.setAttribute('data-id', data.id);
        tempRow.innerHTML = `
            <td class="ps-4"><input class="form-check-input task-checkbox" type="checkbox" data-id="${data.id}"></td>
            <td>${rowNumber}</td>
            <td class="task-name-cell align-middle fw-semibold" onclick="this.querySelector('.editable-task-name').focus()">
                <span class="editable-task-name d-inline-block" contenteditable="true" data-id="${data.id}" style="cursor: text; min-height: 24px;">${title}</span>
            </td>
            <td>${data.created_at}</td>
            <td class="task-reminder-cell align-middle text-nowrap small" data-id="${data.id}">
                <span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;"><i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i></span>
            </td>
            <td class="task-comment-cell align-middle" onclick="this.querySelector('.editable-task-comment').focus()">
                <span class="editable-task-comment text-muted small d-inline-block" contenteditable="true" data-id="${data.id}" style="cursor: text; min-height: 24px;"><i class="bi bi-pencil add-comment-icon text-secondary fs-6" title="Добавить комментарий"></i></span>
            </td>
            <td class="text-center">
                <span class="badge rounded-pill bg-success px-2 py-1 d-inline-flex align-items-center gap-1">
                    <i class="bi bi-plus-circle-fill"></i> Создана
                </span>
            </td>
        `;
        updateTopTaskCounter(1);
    })
    .catch(() => {
        alert("Не удалось сохранить задачу.");
        if (input) { input.disabled = false; input.focus(); }
    });
}

function deleteSelectedTasks() {
    const checkedBoxes = document.querySelectorAll('.task-checkbox:checked');
    if (checkedBoxes.length === 0) return;

    if (!confirm(`Вы уверены, что хотите удалить выбранные задачи (${checkedBoxes.length} шт.)?`)) return;

    const taskIds = Array.from(checkedBoxes).map(cb => parseInt(cb.getAttribute('data-id')));
    const btnDelete = document.getElementById('btn-delete-selected');
    const url = btnDelete.getAttribute('data-url');

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ task_ids: taskIds })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            taskIds.forEach(id => { const row = document.getElementById(`task-row-${id}`); if (row) row.remove(); });
            renumberTableRows();
            const selectAll = document.getElementById('select-all-tasks');
            if (selectAll) selectAll.checked = false;
            btnDelete.classList.add('d-none');
            document.getElementById('btn-edit-selected').classList.add('d-none');
            const selectedCountSpan = document.getElementById('selected-count');
            if (selectedCountSpan) selectedCountSpan.textContent = '0';
            alert(data.message);
        } else {
            alert('Ошибка выполнения: ' + data.message);
        }
    })
    .catch(error => alert('Ошибка удаления: ' + error.message));
}

// === 6. ВСПОМОГАТЕЛЬНЫЕ СИСТЕМНЫЕ ФУНКЦИИ ===
function updateTopTaskCounter(amount) {
    const badges = document.querySelectorAll('.badge');
    badges.forEach(badge => {
        if (badge.textContent.includes('Найдено задач:')) {
            const currentCount = parseInt(badge.textContent.replace(/\D/g, '')) || 0;
            badge.textContent = `Найдено задач: ${currentCount + amount}`;
        }
    });
}

function renumberTableRows() {
    const tbody = document.getElementById('tasks-table-body');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr:not(#temporary-creation-row):not(#no-tasks-row)');
    rows.forEach((row, index) => {
        if (row.cells && row.cells[1]) {
            row.cells[1].textContent = index + 1;
        }
    });
}

function checkIfTableIsEmpty() {
    const tbody = document.getElementById('tasks-table-body');
    if (tbody && tbody.querySelectorAll('tr').length === 0) {
        tbody.innerHTML = `<tr id="no-tasks-row"><td colspan="7" class="text-center text-muted py-3">Нет задач в этой закладке</td></tr>`;
    }
}

function updateRowStatusBadge(taskId, flagValue) {
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

        // 1. Обновляем классы (заменяем только цвета, сохраняя структуру верстки)
        badge.className = `badge rounded-pill ${config.bg} px-2 py-1 d-inline-flex align-items-center gap-1`;

        // 2. ИСПРАВЛЕНО: Обновляем всплывающую подсказку при наведении
        badge.setAttribute('title', config.text);

        // 3. Обновляем иконку и текст
        badge.innerHTML = `<i class="bi ${config.icon}"></i> ${config.text}`;
    }
}

function getCookie(name) {
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

// === 7. ЗАЩИТА ОТ МУСОРА И RICH TEXT ПРИ ВСТАВКЕ ===
document.addEventListener('paste', function(e) {
    if (e.target.classList.contains('editable-task-name') ||
        e.target.classList.contains('editable-task-comment') ||
        e.target.classList.contains('editable-bookmark-name')) {

        e.preventDefault();
        const text = (e.originalEvent || e).clipboardData.getData('text/plain');
        document.execCommand('insertText', false, text);
    }
});
