/**
 * ТАСК-МЕНЕДЖЕР (tasks.js) — Часть 1 из 2
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
            if (btnEdit) btnEdit.classList.remove('d-none');
        } else {
            if (btnEdit) btnEdit.classList.add('d-none');
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

        fetch('/daily/task/update-api/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ id: taskId, title: newName })
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

        fetch('/daily/task/update-api/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ id: taskId, comment: newComment })
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

/**
 * ТАСК-МЕНЕДЖЕР (tasks.js) — Часть 2 (А)
 * Вставлять сразу после Части 1.
 */

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
    const newDateTime = input.value;

    if (input.value === input.defaultValue && cell.dataset.oldHtml) {
        cell.innerHTML = cell.dataset.oldHtml;
        return;
    }

    fetch('/daily/task/update-api/', {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie('csrftoken') },
        body: JSON.stringify({ id: taskId, remind_at: newDateTime })
    })
    .then(response => {
        if (!response.ok) return response.json().then(data => { throw new Error(data.message || 'Ошибка сервера'); });
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            if (data.remind_at_display && data.remind_at_display !== "*") {
                cell.innerHTML = `<span class="d-inline-flex align-items-center gap-1 text-warning"><i class="bi bi-bell-fill"></i> ${data.remind_at_display}</span>`;
            } else {
                cell.innerHTML = `<span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;"><i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i></span>`;
            }
            if (typeof updateRowStatusBadge === "function") updateRowStatusBadge(taskId, data.new_flag);
        }
    })
    .catch(error => {
        alert("Не удалось сохранить время напоминания. Причина: " + error.message);
        cell.innerHTML = cell.dataset.oldHtml || `<span class="editable-task-reminder d-inline-block w-100" style="cursor: pointer; min-height: 20px;"><i class="bi bi-bell add-reminder-icon text-secondary" title="Добавить напоминание"></i></span>`;
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
            <span class="badge rounded-pill bg-success px-2">0</span>
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

/**
 * ТАСК-МЕНЕДЖЕР (tasks.js) — Часть 2 (Б)
 * Вставлять в самый конец файла, сразу после Части 2 (А).
 */

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
            <td class="text-center"><span class="badge rounded-pill bg-success px-2">0</span></td>
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
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;
    const badge = row.querySelector('.badge');
    if (!badge) return;

    // Принудительно приводим к числу на случай, если пришла строка
    const flag = parseInt(flagValue);

    if (flag === 0) {
        badge.className = "badge rounded-pill bg-success px-2";
        badge.textContent = "0";
    } else if (flag === 1) {
        badge.className = "badge rounded-pill bg-warning text-dark px-2";
        badge.textContent = "1";
    } else if (flag === 2) {
        badge.className = "badge rounded-pill bg-secondary px-2";
        badge.textContent = "2";
    } else if (flag === 3) {
        badge.className = "badge rounded-pill bg-danger px-2";
        badge.textContent = "3"; // или "Дедлайн" в зависимости от того, что вы выводите в строках по умолчанию
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
const tableBody = document.getElementById('tasks-table-body');
if (tableBody) {
    tableBody.addEventListener('paste', function(e) {
        if (e.target.classList.contains('editable-task-name') || e.target.classList.contains('editable-task-comment')) {
            e.preventDefault();
            const text = (e.originalEvent || e).clipboardData.getData('text/plain');
            document.execCommand('insertText', false, text);
        }
    });
}
