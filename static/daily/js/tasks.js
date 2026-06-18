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

        // Управление кнопкой пакетного удаления
        if (count > 0) {
            if (btnDelete) btnDelete.classList.remove('d-none');
            if (selectedCountSpan) selectedCountSpan.textContent = count;
        } else {
            if (btnDelete) btnDelete.classList.add('d-none');
        }

        // Управление кнопкой редактирования (только для 1 выбранной задачи)
        if (count === 1) {
            if (btnEdit) btnEdit.classList.remove('d-none');
        } else {
            if (btnEdit) btnEdit.classList.add('d-none');
        }
    }

    // Слушатель для главного чекбокса "Выбрать все"
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            taskCheckboxes.forEach(cb => cb.checked = this.checked);
            updateActionButtons();
        });
    }

    // Слушатели для индивидуальных чекбоксов задач
    taskCheckboxes.forEach(cb => {
        cb.addEventListener('change', function () {
            if (!this.checked && selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }
            updateActionButtons();
        });
    });

    // Закрытие выпадающих окон фильтрации при клике вне их области
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.position-relative')) {
            document.querySelectorAll('.header-filter-popup').forEach(popup => {
                popup.style.display = 'none';
            });
        }
    });
});

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

// Открытие модального окна и заполнение его полей текущими данными из строки таблицы
function openEditModal() {
    const selectedCheckbox = document.querySelector('.task-checkbox:checked');
    if (!selectedCheckbox) return;

    const taskId = selectedCheckbox.value;
    const row = document.getElementById(`task-row-${taskId}`);
    if (!row) return;

    const currentName = row.querySelector('.task-name-cell').textContent.trim();
    const currentComment = row.querySelector('.task-comment-cell').textContent.trim();

    document.getElementById('edit-task-id').value = taskId;
    document.getElementById('edit-task-name').value = currentName;
    document.getElementById('edit-task-comment').value = currentComment;
}

// Отправка измененных данных задачи на сервер через AJAX (Fetch API)
function saveTaskChanges(event) {
    event.preventDefault();

    const taskId = document.getElementById('edit-task-id').value;
    const updatedName = document.getElementById('edit-task-name').value;
    const updatedComment = document.getElementById('edit-task-comment').value;

    const btnEdit = document.getElementById('btn-edit-selected');
    const url = btnEdit.getAttribute('data-url');

    // Безопасное чтение CSRF-токена, сгенерированного Django в шаблоне
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            id: taskId,
            name: updatedName,
            comment: updatedComment
        })
    })
    .then(response => {
        if (response.ok) return response.json();
        return response.json().then(err => { throw new Error(err.message || 'Ошибка сервера при сохранении'); });
    })
    .then(data => {
        // Динамически обновляем текст ячеек в строке таблицы на лету
        const row = document.getElementById(`task-row-${taskId}`);
        if (row) {
            row.querySelector('.task-name-cell').textContent = updatedName;
            row.querySelector('.task-comment-cell').textContent = updatedComment;
        }

        // Закрываем модальное окно через Bootstrap API
        const modalElement = document.getElementById('editTaskModal');
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        if (modalInstance) modalInstance.hide();
    })
    .catch(error => {
        alert('Ошибка при изменении задачи: ' + error.message);
        console.error(error);
    });
}

// Пакетное удаление всех выбранных задач через AJAX (Fetch API)
function deleteSelectedTasks() {
    const checkedBoxes = document.querySelectorAll('.task-checkbox:checked');
    if (checkedBoxes.length === 0) return;

    if (!confirm(`Вы уверены, что хотите удалить выбранные задачи (${checkedBoxes.length} шт.)?`)) {
        return;
    }

    const taskIds = Array.from(checkedBoxes).map(cb => cb.value);
    const btnDelete = document.getElementById('btn-delete-selected');
    const url = btnDelete.getAttribute('data-url');

    // Безопасное чтение CSRF-токена, сгенерированного Django в шаблоне
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
            // Удаляем HTML-строки из таблицы без перезагрузки страницы
            taskIds.forEach(id => {
                const row = document.getElementById(`task-row-${id}`);
                if (row) row.remove();
            });

            // Сбрасываем состояние главного чекбокса в шапке
            const selectAll = document.getElementById('select-all-tasks');
            if (selectAll) selectAll.checked = false;

            // Прячем кнопки групповых действий
            btnDelete.classList.add('d-none');
            document.getElementById('btn-edit-selected').classList.add('d-none');

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
