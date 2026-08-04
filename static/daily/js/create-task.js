// ===  ИНЛАЙН СОЗДАНИЕ ЗАДАЧИ ===

export function appendNewTaskRow() {
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

export function saveInlineTask(title, bookmarkId, rowNumber) {
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

export function deleteSelectedTasks() {
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