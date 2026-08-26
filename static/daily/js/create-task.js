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
        <td colspan="5">
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

    fetch('/daily/task/create/', {
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
            <td class="text-nowrap text-muted small task-periodicity-cell dropdown position-relative"
                data-id="${data.id}"
                data-value=""
                data-unit="none">
                <div class="inline-periodicity-trigger d-inline-block cursor-pointer"
                     data-bs-toggle="dropdown"
                     data-bs-auto-close="outside"
                     aria-expanded="false"
                     style="cursor: pointer;">
                    <i class="bi bi-arrow-repeat text-muted"></i>
                </div>
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

// Слушатель горячей клавиши "+"
document.addEventListener('keydown', function(event) {
    // 1. Проверяем нажатие клавиши "+" или кнопки "+" на Numpad
    if (event.key === '+' || event.key === 'NumpadAdd') {

        // 2. Защита: проверяем, не пишет ли пользователь уже в инпуте или contenteditable
        const activeEl = document.activeElement;
        const isTyping = activeEl && (
            activeEl.tagName === 'INPUT' ||
            activeEl.tagName === 'TEXTAREA' ||
            activeEl.isContentEditable
        );

        // Если пользователь уже где-то вводит текст, то символ "+" должен просто напечататься
        if (isTyping) return;

        // 3. Если фокус нигде не стоит, перехватываем нажатие и вызываем создание строки
        event.preventDefault();
        appendNewTaskRow();
    }
});
