// static/daily/js/tasks.js

document.addEventListener('DOMContentLoaded', function () {
    const selectAllCheckbox = document.getElementById('select-all-tasks');
    const btnEdit = document.getElementById('btn-edit-selected');
    const btnDelete = document.getElementById('btn-delete-selected');
    const selectedCountSpan = document.getElementById('selected-count');

    // Функция переключения видимости кнопок групповых операций
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
            if (btnEdit) btnEdit.classList.remove('d-none');
        } else {
            if (btnEdit) btnEdit.classList.add('d-none');
        }
    }

    // Обработка главного чекбокса "Выбрать все"
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            // ИСПРАВЛЕНО: ищем чекбоксы динамически, чтобы захватить и новые задачи
            const currentCheckboxes = document.querySelectorAll('.task-checkbox');
            currentCheckboxes.forEach(cb => cb.checked = this.checked);
            updateActionButtons();
        });
    }

    // ИСПРАВЛЕНО: Делегирование событий. Слушаем клики по чекбоксам на всей таблице
    const tasksTable = document.getElementById('tasks-table');
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

    // === УНИВЕРСАЛЬНОЕ И СТАБИЛЬНОЕ АВТОЗАКРЫТИЕ ДЛЯ ВСЕХ МЕНЮ (БЕЗ БАГОВ) ===
    const allDropdowns = document.querySelectorAll('.dropdown');

    allDropdowns.forEach(dropdownWrapper => {
        let closeTimeout = null;

        dropdownWrapper.addEventListener('mouseleave', function () {
            if (!closeTimeout) {
                closeTimeout = setTimeout(() => {
                    const toggleBtn = dropdownWrapper.querySelector('[data-bs-toggle="dropdown"]');
                    if (toggleBtn) {
                        const bsDropdown = bootstrap.Dropdown.getOrCreateInstance(toggleBtn);
                        if (bsDropdown) {
                            bsDropdown.hide();
                        }
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

    // === РЕДАКТИРОВАНИЕ НАЗВАНИЯ ЗАКЛАДКИ (ИСПРАВЛЕННАЯ СИНХРОНИЗАЦИЯ) ===
    let originalText = ""; // Глобальный буфер для отмены изменений

    // Запоминаем текст в момент фокуса (клик по полю)
    document.addEventListener('focusin', function (e) {
        if (e.target.classList.contains('editable-task-comment')) {
            const hasIcon = e.target.querySelector('.add-comment-icon');
            originalCommentText = hasIcon ? "" : e.target.innerText.trim();

            if (hasIcon) e.target.innerHTML = ""; // Если внутри иконка — очищаем ячейку для ввода
        }
    });

    // Обработка клавиш Enter (сохранение) и Escape (отмена)
    document.addEventListener('keydown', function (e) {
        // ИСПРАВЛЕНО: Заменено на 'editable-task-comment', чтобы события клавиатуры работали для комментариев
        if (e.target.classList.contains('editable-task-comment')) {
            if (e.key === 'Enter') {
                e.preventDefault(); // Запрещаем перенос строки в таблице
                e.target.blur();    // Вызываем потерю фокуса для отправки AJAX
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                // Если исходный текст был пустым, возвращаем правильную иконку, иначе — старый текст
                const iconHtml = `<i class="bi bi-pencil add-comment-icon text-secondary fs-6" title="Добавить комментарий"></i>`;
                e.target.innerHTML = originalCommentText ? originalCommentText : iconHtml;
                e.target.blur();
            }
        }
    });

    // Сохранение изменений при потере фокуса
    document.addEventListener('focusout', function (e) {
        if (!e.target.classList.contains('editable-task-comment')) return;

        const editableField = e.target;
        let newComment = editableField.innerText.trim();
        const taskId = editableField.getAttribute('data-id');

        // ИСПРАВЛЕНО: Шаблон обновлен на рабочий text-secondary и fs-6
        const iconHtml = `<i class="bi bi-pencil add-comment-icon text-secondary fs-6" title="Добавить комментарий"></i>`;

        if (newComment === originalCommentText) {
            if (newComment === "") editableField.innerHTML = iconHtml;
            return;
        }

        fetch('/daily/task/update-api/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                id: taskId,
                comment: newComment
            })
        })
        .then(response => {
            if (response.ok) {
                originalCommentText = newComment;
                if (newComment === "") editableField.innerHTML = iconHtml; // Если сохранили пустоту, возвращаем серый карандаш
            } else {
                alert("Не удалось сохранить комментарий");
                editableField.innerHTML = originalCommentText ? originalCommentText : iconHtml;
            }
        })
        .catch(error => {
            console.error('Ошибка AJAX:', error);
            editableField.innerHTML = originalCommentText ? originalCommentText : iconHtml;
        });
    });
});

// Вспомогательная функция (вынесена за пределы DOMContentLoaded, чтобы не загромождать код)
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


// Управление показом кастомных окон фильтрации в шапке таблицы
function toggleFilterPopup(event, popupId) {
    event.stopPropagation();
    const popup = document.getElementById(popupId);
    if (!popup) return;

    const isOpen = popup.style.display === 'block';
    document.querySelectorAll('.header-filter-popup').forEach(p => p.style.display = 'none');

    if (!isOpen) {
        popup.style.display = 'block';
    }
}

// Переключение сортировки по дате (для скрытой GET-формы)
function toggleDateSort() {
    const form = document.getElementById('hidden-filter-form');
    const sortInput = document.getElementById('hidden-sort');
    if (!form || !sortInput) return;

    sortInput.value = (sortInput.value === 'newest') ? 'oldest' : 'newest';
    form.submit();
}

// ЭТАЛОННАЯ ФУНКЦИЯ ОТКРЫТИЯ ОКНА: Адаптирована под поле title
function openEditModal() {
    const selectedCheckbox = document.querySelector('.task-checkbox:checked');
    if (!selectedCheckbox) return;

    const taskId = selectedCheckbox.value;
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;

    // Читаем данные из ячейки title (заменили класс на .task-title-cell)
    const currentTitle = row.querySelector('.task-title-cell')
        ? row.querySelector('.task-title-cell').textContent.trim()
        : row.querySelector('.task-name-cell').textContent.trim(); // Резерв на случай, если класс в HTML ещё старый

    const currentComment = row.querySelector('.task-comment-cell').textContent.trim();

    const currentFlagBadge = row.querySelector('.badge');
    const currentFlag = currentFlagBadge ? currentFlagBadge.textContent.trim() : "0";

    // Срез текста. Гарантирует отсутствие синтаксических сбоев в JS
    let formattedDate = "";
    if (row.cells && row.cells[4]) {
        const rawDateStr = row.cells[4].textContent.trim(); // "19.06.2026 14:00"

        if (rawDateStr && rawDateStr.length >= 16) {
            const day = rawDateStr.substring(0, 2);
            const month = rawDateStr.substring(3, 5);
            const year = rawDateStr.substring(6, 10);
            const time = rawDateStr.substring(11, 16);

            formattedDate = year + "-" + month + "-" + day + "T" + time;
        }
    }

    document.getElementById('edit-task-id').value = taskId;
    // Записываем значение в инпут (использован новый ID 'edit-task-title')
    document.getElementById('edit-task-title').value = currentTitle;
    document.getElementById('edit-task-comment').value = currentComment;
    document.getElementById('edit-task-reminder').value = formattedDate;

    const flagSelect = document.getElementById('edit-task-flag');
    if (flagSelect) flagSelect.value = currentFlag;

    document.getElementById('edit-task-number-title').textContent = taskId;
}

// ЭТАЛОННАЯ ФУНКЦИЯ СОХРАНЕНИЯ ИЗМЕНЕНИЙ
function saveTaskChanges(event) {
    event.preventDefault();

    const taskId = document.getElementById('edit-task-id').value;
    // 1. Читаем из инпута с новым ID 'edit-task-title'
    const updatedTitle = document.getElementById('edit-task-title').value;
    const updatedComment = document.getElementById('edit-task-comment').value;
    const updatedReminder = document.getElementById('edit-task-reminder').value;

    const btnEdit = document.getElementById('btn-edit-selected');
    const url = btnEdit.getAttribute('data-url');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            id: taskId,
            title: updatedTitle, // 2. Отправляем на бэкенд ключ 'title' вместо 'name'
            comment: updatedComment,
            reminder_at: updatedReminder || null
        })
    })
    .then(response => {
        if (response.ok) return response.json();
        return response.json().then(err => { throw new Error(err.message || 'Ошибка сервера при сохранении'); });
    })
    .then(data => {
        const row = document.getElementById(`task-row-${taskId}`);
        if (row) {
            // 3. Обновляем ячейку в таблице. Ищем новый класс .task-title-cell, с резервом на старый
            const titleCell = row.querySelector('.task-title-cell') || row.querySelector('.task-name-cell');
            if (titleCell) {
                titleCell.textContent = updatedTitle;
            }

            row.querySelector('.task-comment-cell').textContent = updatedComment;

            const reminderCell = row.cells[4];
            if (reminderCell) {
                if (updatedReminder) {
                    const dateObj = new Date(updatedReminder);
                    const day = String(dateObj.getDate()).padStart(2, '0');
                    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
                    const year = dateObj.getFullYear();
                    const hours = String(dateObj.getHours()).padStart(2, '0');
                    const minutes = String(dateObj.getMinutes()).padStart(2, '0');
                    reminderCell.innerHTML = `${day}.${month}.${year} ${hours}:${minutes}`;
                } else {
                    reminderCell.innerHTML = '<span class="text-danger fw-bold">*</span>';
                }
            }

            if (data.new_flag !== undefined) {
                const badge = row.querySelector('.badge');
                if (badge) {
                    badge.textContent = data.new_flag;
                    badge.className = 'badge rounded-pill';
                    if (data.new_flag == 0) badge.classList.add('bg-success');
                    else if (data.new_flag == 1) badge.classList.add('bg-secondary');
                    else if (data.new_flag == 2) badge.classList.add('bg-warning', 'text-dark');
                    else if (data.new_flag == 3) badge.classList.add('bg-danger');
                }
            }
        }

        const modalElement = document.getElementById('editTaskModal');
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        if (modalInstance) modalInstance.hide();
    })
    .catch(error => alert('Ошибка при изменении задачи: ' + error.message));
}

// ФУНКЦИЯ УДАЛЕНИЯ
function deleteSelectedTasks() {
    const checkedBoxes = document.querySelectorAll('.task-checkbox:checked');
    if (checkedBoxes.length === 0) return;

    if (!confirm(`Вы уверены, что хотите удалить выбранные задачи (${checkedBoxes.length} шт.)?`)) {
        return;
    }

    const taskIds = Array.from(checkedBoxes).map(cb => parseInt(cb.getAttribute('data-id')));
    const btnDelete = document.getElementById('btn-delete-selected');
    const url = btnDelete.getAttribute('data-url');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ task_ids: taskIds })
    })
    .then(response => {
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error(`Сервер вернул некорректный ответ (Статус: ${response.status}). Проверьте терминал PyCharm!`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            taskIds.forEach(id => {
                const row = document.getElementById(`task-row-${id}`);
                if (row) row.remove();
            });

            renumberTableRows(); // Пересчет номеров строк таблицы

            const selectAll = document.getElementById('select-all-tasks');
            if (selectAll) selectAll.checked = false;

            btnDelete.classList.add('d-none');
            document.getElementById('btn-edit-selected').classList.add('d-none');
            
            // Сбрасываем текстовый счётчик выделенных задач в 0
            const selectedCountSpan = document.getElementById('selected-count');
            if (selectedCountSpan) selectedCountSpan.textContent = '0';

            alert(data.message);
        } else {
            alert('Ошибка выполнения: ' + data.message);
        }
    })
    .catch(error => {
        alert('Ошибка удаления: ' + error.message);
        console.error(error);
    });
}

// ФУНКЦИЯ добавления новой задачи
function appendNewTaskRow() {
    if (document.getElementById('inline-task-input')) {
        document.getElementById('inline-task-input').focus();
        return;
    }

    const tbody = document.getElementById('tasks-table-body');
    document.getElementById('no-tasks-row')?.remove();

    // === ИСПРАВЛЕНО: Считаем ТОЛЬКО настоящие строки задач, у которых ID начинается с "task-row-" ===
    const nextNumber = tbody.querySelectorAll('tr[id^="task-row-"]').length + 1;

    const bookmarkButton = document.querySelector('[data-bookmark-id]');
    const bookmarkId = bookmarkButton ? bookmarkButton.getAttribute('data-bookmark-id') : "";

    const newRow = document.createElement('tr');
    newRow.id = 'temporary-creation-row';

    newRow.innerHTML = `
        <td class="ps-4">
            <input class="form-check-input" type="checkbox" disabled>
        </td>
        <td><span class="text-muted">${nextNumber}</span></td>
        <td colspan="4">
            <input type="text"
                   id="inline-task-input"
                   class="form-control form-control-sm border-primary shadow-sm"
                   placeholder="Напишите название задачи и нажмите Enter..."
                   style="outline: none;"
                   onkeydown="handleInlineTaskKey(event, '${bookmarkId}', ${nextNumber})"
                   onblur="handleInlineTaskBlur('${bookmarkId}', ${nextNumber})">
        </td>
        <td class="text-center">
            <span class="badge rounded-pill bg-secondary px-2">new</span>
        </td>
    `;

    tbody.appendChild(newRow);
    newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    document.getElementById('inline-task-input').focus();
}

// Обработка горячих клавиш внутри инпута
function handleInlineTaskKey(event, bookmarkId, rowNumber) {
    if (event.key === 'Enter') {
        event.preventDefault();
        saveInlineTask(event.target.value.trim(), bookmarkId, rowNumber);
    } else if (event.key === 'Escape') {
        document.getElementById('temporary-creation-row')?.remove();
        checkIfTableIsEmpty();
    }
}

// Функция проверяет: если текст есть — сохраняем, если текста нет — удаляем пустую строку
function handleInlineTaskBlur(bookmarkId, rowNumber) {
    const input = document.getElementById('inline-task-input');
    if (!input) return;

    const title = input.value.trim();

    if (title === "") {
        // Если ничего не введено — просто убираем временную строку
        document.getElementById('temporary-creation-row')?.remove();
        checkIfTableIsEmpty();
    } else {
        // Если текст есть — сохраняем задачу автоматически при клике мимо!
        saveInlineTask(title, bookmarkId, rowNumber);
    }
}

// Функция проверки: если удалили строку создания и таблица пуста — вернем заглушку
function checkIfTableIsEmpty() {
    const tbody = document.getElementById('tasks-table-body');
    if (tbody && tbody.querySelectorAll('tr').length === 0) {
        tbody.innerHTML = `<tr id="no-tasks-row"><td colspan="7" class="text-center text-muted py-3">Нет задач в этой закладке</td></tr>`;
    }
}

// Отправка созданной задачи на Django
function saveInlineTask(title, bookmarkId, rowNumber) {
    if (!title) {
        document.getElementById('temporary-creation-row')?.remove();
        checkIfTableIsEmpty();
        return;
    }

    // Блокируем инпут на время отправки, чтобы избежать повторных кликов
    const input = document.getElementById('inline-task-input');
    if (input) input.disabled = true;

    fetch('/daily/task/create-api/', {  // Укажите ваш точный URL для создания задач
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken')
        },
        body: JSON.stringify({
            title: title,
            bookmark_id: bookmarkId
        })
    })
    .then(response => {
        if (!response.ok) throw new Error("Ошибка бэкенда");
        return response.json();
    })
    .then(data => {
        const tempRow = document.getElementById('temporary-creation-row');
        if (!tempRow) return;

        // Превращаем временную строку ввода в постоянную строку вашей таблицы
        tempRow.id = `task-row-${data.id}`;
        tempRow.innerHTML = `
            <td class="ps-4">
                <input class="form-check-input task-checkbox" type="checkbox" data-id="${data.id}" onchange="toggleActionButtons()">
            </td>
            <td>${rowNumber}</td>
            <!-- ИСПРАВЛЕНО: убрали contenteditable и стили курсора -->
            <td class="task-title-cell" data-id="${data.id}">${title}</td>
            <td>${data.created_at || new Date().toLocaleDateString('ru-RU') + ' ' + new Date().toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'})}</td>
            <td><span class="text-danger fw-bold">*</span></td>
            <td></td>
            <td class="text-center">
                <span class="badge rounded-pill bg-success px-2">0</span>
            </td>
        `;

        // Обновляем счетчик найденных задач в бадже сверху страницы (Найдено задач: X)
        updateTopTaskCounter(1);
    })
    .catch(error => {
        console.error("Ошибка сохранения задачи:", error);
        alert("Не удалось сохранить задачу. Попробуйте еще раз.");

        // Разблокируем ввод для исправления в случае ошибки
        if (input) {
            input.disabled = false;
            input.focus();
        }
    });
}

function updateTopTaskCounter(amount) {
    const badges = document.querySelectorAll('.badge');
    badges.forEach(badge => {
        if (badge.textContent.includes('Найдено задач:')) {
            const currentCount = parseInt(badge.textContent.replace(/\D/g, '')) || 0;
            badge.textContent = `Найдено задач: ${currentCount + amount}`;
        }
    });
}

// ФУНКЦИЯ пересчета номеров строк в таблице
function renumberTableRows() {
    const tbody = document.getElementById('tasks-table-body');
    if (!tbody) return;

    // Находим все строки внутри tbody (исключая временную строку создания, если она открыта)
    const rows = tbody.querySelectorAll('tr:not(#temporary-creation-row):not(#no-tasks-row)');

    rows.forEach((row, index) => {
        // В вашей структуре ячейка № — это вторая колонка (индекс 1, так как 0 — это чекбокс)
        const numberCell = row.cells[1];
        if (numberCell) {
            numberCell.textContent = index + 1; // Устанавливаем правильный порядковый номер
        }
    });
}

// Активация поля ввода при клике на ячейку комментария
function activateCommentEdit(cell) {
    if (cell.querySelector('.inline-comment-input')) return;

    const taskId = cell.getAttribute('data-id');
    const spanText = cell.querySelector('.comment-text');

    const currentComment = spanText.textContent.trim() === '...' ? '' : spanText.textContent.trim();

    // Блок генерации инпута
    cell.innerHTML = `
    <input type="text"
           class="form-control form-control-sm inline-comment-input p-0 m-0 border-0 text-muted"
           value="${currentComment}"
           placeholder="Добавить комментарий..."
           style="outline: none; max-width: 180px; width: 100%; height: 20px; font-size: 0.875rem; box-shadow: none; display: inline-block; background: transparent; vertical-align: middle;"
           onkeydown="handleCommentKey(event, this, '${taskId}')"
           onblur="saveInlineComment(this, '${taskId}')">
    `;
    const input = cell.querySelector('.inline-comment-input');
    input.focus();
    input.select();
}

// Обработка клавиш Enter и Escape
function handleCommentKey(event, input, taskId) {
    if (event.key === 'Enter') {
        event.preventDefault();
        input.blur(); // Вызовет функцию сохранения через событие onblur
    } else if (event.key === 'Escape') {
        // Отмена изменений: возвращаем старый текст или три точки
        const cell = input.parentElement;
        const fallbackText = input.defaultValue || '...';
        cell.innerHTML = `<span class="comment-text text-muted small">${fallbackText}</span>`;
    }
}

// Отправка AJAX-запроса на сохранение комментария
function saveInlineComment(input, taskId) {
    const cell = input.parentElement;
    const newComment = input.value.trim();
    const oldComment = input.defaultValue;

    // Если текст не изменился — просто возвращаем текст обратно
    if (newComment === oldComment) {
        cell.innerHTML = `<span class="comment-text text-muted small">${newComment || '...'}</span>`;
        return;
    }

    // Отправляем данные на бэкенд (используем ваш готовый маршрут редактирования)
    fetch('/daily/task/update-api/', {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken')
        },
        body: JSON.stringify({
            id: taskId,
            comment: newComment // Передаем измененное поле
        })
    })
    .then(response => {
        if (response.ok) {
            // В случае успеха фиксируем новый текст в ячейке
            cell.innerHTML = `<span class="comment-text text-muted small">${newComment || '...'}</span>`;
        } else {
            alert("Не удалось сохранить комментарий.");
            cell.innerHTML = `<span class="comment-text text-muted small">${oldComment || '...'}</span>`;
        }
    })
    .catch(error => {
        console.error("Ошибка сохранения комментария:", error);
        cell.innerHTML = `<span class="comment-text text-muted small">${oldComment || '...'}</span>`;
    });
}

// Навешиваем слушатель на ячейки времени напоминания (вызовите один раз при загрузке страницы)
document.addEventListener('click', function(e) {
    const cell = e.target.closest('.remind-cell');
    if (!cell || cell.querySelector('input[type="datetime-local"]')) return;

    const taskId = cell.getAttribute('data-id');

    // Пытаемся вытащить текущую дату из текста (если там звезда *, то даты нет)
    let currentText = cell.textContent.trim();
    let currentIsoValue = "";

    if (currentText !== "*") {
        // Конвертируем формат "ДД.ММ.ГГГГ ЧЧ:ММ" в стандарт ISO "YYYY-MM-DDTHH:MM" для input
        const parts = currentText.match(/(\d{2})\.(\d{2})\.(\d{4})\s(\d{2}):(\d{2})/);
        if (parts) {
            currentIsoValue = `${parts[3]}-${parts[2]}-${parts[1]}T${parts[4]}:${parts[5]}`;
        }
    }

    // Заменяем содержимое ячейки на инпут календаря
    cell.innerHTML = `
        <input type="datetime-local"
               class="form-control form-control-sm inline-date-input"
               value="${currentIsoValue}"
               style="outline: none; width: 100%; max-width: 170px;"
               onkeydown="handleDateKey(event, this)"
               onblur="saveInlineDate(this, '${taskId}')">
    `;

    // Мгновенно открываем календарь
    const input = cell.querySelector('.inline-date-input');
    input.focus();
});

// Управление клавиатурой в календаре
function handleDateKey(event, input) {
    if (event.key === 'Enter') {
        event.preventDefault();
        input.blur(); // Вызовет сохранение
    } else if (event.key === 'Escape') {
        // При отмене просто возвращаем то значение, которое было до клика
        const cell = input.parentElement;
        const oldText = input.defaultValue ? formatIsoToRu(input.defaultValue) : `<span class="text-danger fw-bold">*</span>`;
        cell.innerHTML = oldText;
    }
}

// Отправка даты на Django
function saveInlineDate(input, taskId) {
    const cell = input.parentElement;
    const newDateTime = input.value; // Строка типа "2026-07-30T23:00"

    fetch('/daily/task/update-api/', {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken')
        },
        body: JSON.stringify({
            id: taskId,
            remind_at: newDateTime // Передаем поле
        })
    })
    .then(response => {
        // Если сервер вернул ошибку (400, 404, 500), перенаправляем в catch с описанием
        if (!response.ok) {
            return response.json().then(data => { throw new Error(data.message || 'Ошибка сервера'); });
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            if (data.remind_at_display !== "*") {
                cell.innerHTML = data.remind_at_display;
            } else {
                cell.innerHTML = `<span class="text-danger fw-bold">*</span>`;
            }
            // Вызываем перекраску баджа статуса, если она у вас прописана
            if (typeof updateRowStatusBadge === "function") {
                updateRowStatusBadge(taskId, data.new_flag);
            }
        }
    })
    .catch(error => {
        // Выводим точную причину, которую прислал Django
        alert("Не удалось сохранить время напоминания. Причина: " + error.message);
        const oldText = input.defaultValue ? formatIsoToRu(input.defaultValue) : `<span class="text-danger fw-bold">*</span>`;
        cell.innerHTML = oldText;
    });
}

// Вспомогательная функция перевода ISO даты назад в красивый RU формат при отмене Esc
function formatIsoToRu(isoStr) {
    if (!isoStr) return `<span class="text-danger fw-bold">*</span>`;
    const t = isoStr.split(/[-T:]/);
    return `${t[2]}.${t[1]}.${t[0]} ${t[3]}:${t[4]}`;
}

// Функция для динамического обновления баджа статуса в строке
function updateRowStatusBadge(taskId, flagValue) {
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;
    const badge = row.querySelector('.badge');
    if (!badge) return;

    // В зависимости от флага бэкенда красим бадж прямо на лету!
    if (flagValue === 3) {
        badge.className = "badge rounded-pill bg-danger px-2";
        badge.textContent = "Просрочена";
    } else if (flagValue === 0) {
        badge.className = "badge rounded-pill bg-success px-2";
        badge.textContent = "0"; // Ваш статус "В работе" или исходный
    }
}

// Блок для редактирования названия задачи в таблице
let originalNameText = "";

// 1. Запоминаем исходное название при клике в поле
document.addEventListener('focusin', function (e) {
    if (e.target.classList.contains('editable-task-name')) {
        // Если задача зачеркнута (<del>), берем чистый текстовый контент
        originalNameText = e.target.innerText.trim();
    }
});

// 2. Обработка клавиш Enter и Escape для названия задачи
document.addEventListener('keydown', function (e) {
    if (e.target.classList.contains('editable-task-name')) {
        if (e.key === 'Enter') {
            e.preventDefault(); // Запрещаем перенос строки
            e.target.blur();    // Перенаправляем на focusout для сохранения
        }
        if (e.key === 'Escape') {
            e.preventDefault();
            // Возвращаем старый текст, если пользователь передумал
            e.target.innerText = originalNameText;
            e.target.blur();
        }
    }
});

// 3. Сохранение названия задачи через AJAX при потере фокуса
document.addEventListener('focusout', function (e) {
    if (!e.target.classList.contains('editable-task-name')) return;

    const editableField = e.target;
    let newName = editableField.innerText.trim();
    const taskId = editableField.getAttribute('data-id');

    // Проверка: если поле полностью очистили, не даем сохранить пустоту
    if (newName === "") {
        alert("Наименование задачи не может быть пустым");
        editableField.innerText = originalNameText;
        return;
    }

    // Если текст не изменился, ничего не отправляем
    if (newName === originalNameText) return;

    fetch('/daily/task/update-api/', { // Используем тот же эндпоинт
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            id: taskId,
            title: newName // Передаем поле title вместо comment
        })
    })
    .then(response => {
        if (response.ok) {
            originalNameText = newName;

            // Если задача выполнена (внутри есть тег <del>), перерисовываем структуру
            const isCompleted = editableField.querySelector('del');
            if (isCompleted) {
                editableField.innerHTML = `<del class="text-muted">${newName}</del>`;
            }
        } else {
            alert("Не удалось сохранить наименование задачи");
            editableField.innerText = originalNameText;
        }
    })
    .catch(error => {
        console.error('Ошибка AJAX:', error);
        editableField.innerText = originalNameText;
    });
});