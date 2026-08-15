// === ИНЛАЙН РЕДАКТИРОВАНИЕ НАЗВАНИЙ И КОММЕНТАРИЕВ (CONTENTEDITABLE) ===

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

        fetch('/daily/task/update/', {
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

        fetch('/daily/task/update/', {
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