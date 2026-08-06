// === РЕДАКТИРОВАНИЕ НАЗВАНИЯ ЗАКЛАДКИ (ИСПРАВЛЕННАЯ СИНХРОНИЗАЦИЯ) ===

let originalBookmarkText = ""; // Глобальный буфер для отмены изменений

// Запоминаем текст в момент фокуса (клик по названию закладки)
document.addEventListener('focusin', function (e) {
    if (e.target.classList.contains('editable-bookmark-name')) {
        originalBookmarkText = e.target.innerText.trim();
    }
});

// Обработка горячих клавиш при редактировании
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

// Сохранение названия закладки на бэкенд при потере фокуса
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

                // === СИНХРОНИЗАЦИЯ С ВЫПАДАЮЩИМ МЕНЮ ===
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