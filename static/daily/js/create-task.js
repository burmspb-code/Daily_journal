// ===  ИНЛАЙН СОЗДАНИЕ ЗАДАЧИ ===

import { getStatusConfig } from './status-icons-config.js';

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

    const statusConfig = getStatusConfig(0); // Статус "Создана"

    const newRow = document.createElement('tr');
    newRow.id = 'temporary-creation-row';
    newRow.innerHTML = `
        <td class="ps-4"><input class="form-check-input" type="checkbox" disabled></td>
        <td><span class="text-muted">${nextNumber}</span></td>
        <td colspan="5">
            <input type="text" id="inline-task-input" class="form-control form-control-sm border-primary shadow-sm" placeholder="Напишите название задачи и нажмите Enter..." style="outline: none;">
        </td>
        <td class="text-center">
            <span class="badge rounded-pill ${statusConfig.bg} px-2 py-1 d-inline-flex align-items-center gap-1">
                <i class="bi ${statusConfig.icon}"></i> ${statusConfig.text}
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
        body: JSON.stringify({ title: title, bookmark_id: bookmarkId, row_number: rowNumber })
    })
    .then(response => {
        // Проверяем Content-Type ответа
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json().then(data => ({ isJson: true, data }));
        }
        return response.text().then(html => ({ isJson: false, html }));
    })
    .then(result => {
        if (result.isJson) {
            // Обработка JSON-ответа (ошибка лимита)
            if (result.data.status === 'limit_error') {
                const limitErrorModal = document.getElementById('limitErrorModal');
                const limitErrorBody = document.getElementById('limit-error-body');
                if (limitErrorBody) {
                    limitErrorBody.textContent = result.data.message;
                }
                if (limitErrorModal) {
                    const modal = new bootstrap.Modal(limitErrorModal);
                    modal.show();
                }
                const tempRow = document.getElementById('temporary-creation-row');
                if (tempRow) tempRow.remove();
                checkIfTableIsEmpty();
            } else if (result.data.status === 'error') {
                alert(result.data.message || "Не удалось сохранить задачу.");
                if (input) { input.disabled = false; input.focus(); }
            }
        } else {
            // Обработка HTML-ответа (успешное создание)
            const tempRow = document.getElementById('temporary-creation-row');
            if (!tempRow) return;

            tempRow.outerHTML = result.html;
            updateTopTaskCounter(1);
        }
    })
    .catch(() => {
        alert("Не удалось сохранить задачу.");
        if (input) { input.disabled = false; input.focus(); }
    });
}

// Слушатель горячей клавиши "+"
document.addEventListener('keydown', function(event) {
    // Проверяем нажатие клавиши "+" или кнопки "+" на Numpad
    if (event.key === '+' || event.key === 'NumpadAdd') {

        // Защита: проверяем, не пишет ли пользователь уже в инпуте или contenteditable
        const activeEl = document.activeElement;
        const isTyping = activeEl && (
            activeEl.tagName === 'INPUT' ||
            activeEl.tagName === 'TEXTAREA' ||
            activeEl.isContentEditable
        );

        // Если пользователь уже где-то вводит текст, то символ "+" должен просто напечататься
        if (isTyping) return;

        // Если фокус нигде не стоит, перехватываем нажатие и вызываем создание строки
        event.preventDefault();
        appendNewTaskRow();
    }
});
