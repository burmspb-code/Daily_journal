// static/daily/js/tasks.js

document.addEventListener('DOMContentLoaded', function () {
    const selectAllCheckbox = document.getElementById('select-all-tasks');
    const taskCheckboxes = document.querySelectorAll('.task-checkbox');
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

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            taskCheckboxes.forEach(cb => cb.checked = this.checked);
            updateActionButtons();
        });
    }

    taskCheckboxes.forEach(cb => {
        cb.addEventListener('change', function () {
            if (!this.checked && selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
            updateActionButtons();
        });
    });

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
    document.addEventListener('focusin', function(e) {
        if (e.target.classList.contains('editable-bookmark-name')) {
            originalText = e.target.innerText.trim();
        }
    });

    // Обработка клавиш Enter (сохранение) и Escape (отмена)
    document.addEventListener('keydown', function(e) {
        if (e.target.classList.contains('editable-bookmark-name')) {
            if (e.key === 'Enter') {
                e.preventDefault(); // Намертво запрещаем перенос строки
                e.target.blur();    // Спровоцирует событие потери фокуса для сохранения
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                e.target.innerText = originalText; // Корректно откатываем к актуальному старому значению
                e.target.blur();
            }
        }
    });

    // Сохранение изменений при потере фокуса
    document.addEventListener('focusout', function(e) {
        if (!e.target.classList.contains('editable-bookmark-name')) return;

        const editableField = e.target;
        const newTitle = editableField.innerText.trim(); // Переименовали переменную для ясности
        const bookmarkId = editableField.getAttribute('data-id');

        // Если текст пустой или не изменился — отменяем отправку
        if (newTitle === '' || newTitle === originalText) {
            editableField.innerText = originalText;
            return;
        }

        // Отправка AJAX-запроса на бэкенд
        fetch('/daily/bookmark/update-api/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                id: bookmarkId,
                title: newTitle //  ИСПРАВЛЕНО: передаем ключ 'title' вместо 'name'
            })
        })
        .then(response => {
            if (response.ok) {
                originalText = newTitle; // Обновляем буфер актуальным именем

                // Синхронно меняем текст во всех элементах выпадающего меню с этим ID
                const connectedLinks = document.querySelectorAll(`.bookmark-link-name[data-id="${bookmarkId}"]`);
                connectedLinks.forEach(link => {
                    link.innerText = newTitle;
                });
            } else {
                // ВЫВОДИМ ТОЧНУЮ ПРИЧИНУ ОШИБКИ ОТ СЕРВЕРА
                response.json().then(data => {
                    alert(`Ошибка сохранения! Причина: ${data.message || 'Неизвестная ошибка сервера'}`);
                }).catch(() => {
                    alert(`Сервер вернул критическую ошибку без JSON. Статус: ${response.status}`);
                });

                editableField.innerText = originalText;
            }
        })
        .catch(error => {
            console.error('Ошибка AJAX:', error);
            editableField.innerText = originalText;
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

    const taskIds = Array.from(checkedBoxes).map(cb => cb.value);
    const btnDelete = document.getElementById('btn-delete-selected');
    const url = btnDelete.getAttribute('data-url');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ ids: taskIds })
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