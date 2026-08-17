// === ИНЛАЙН УДАЛЕНИЕ ЗАДАЧИ ===

let bootstrapDeleteModal = null;

export function deleteSelectedTasks() {
    const checkedBoxes = document.querySelectorAll('.task-checkbox:checked');
    if (checkedBoxes.length === 0) return;

    // Находим модальное окно в DOM
    const modalEl = document.getElementById('deleteConfirmModal');
    if (!modalEl) {
        console.error('Модальное окно #deleteConfirmModal не найдено в HTML!');
        return;
    }

    // Обновляем счетчик задач в тексте окна
    const countSpan = document.getElementById('delete-count-span');
    if (countSpan) countSpan.textContent = checkedBoxes.length;

    // Инициализируем инстанс Bootstrap Modal, если он еще не создан
    if (!bootstrapDeleteModal) {
        bootstrapDeleteModal = new bootstrap.Modal(modalEl);
    }

    // Настраиваем кнопку подтверждения "ОК"
    const btnConfirm = document.getElementById('btn-confirm-delete-action');

    // Клонируем кнопку, чтобы очистить старые обработчики кликов (защита от дублирования запросов)
    const newBtnConfirm = btnConfirm.cloneNode(true);
    btnConfirm.parentNode.replaceChild(newBtnConfirm, btnConfirm);

    // Навешиваем логику удаления на новую чистую кнопку "ОК"
    newBtnConfirm.addEventListener('click', () => {
        // Закрываем окно перед отправкой запроса
        bootstrapDeleteModal.hide();

        const taskIds = Array.from(checkedBoxes).map(cb => parseInt(cb.getAttribute('data-id')));
        const btnDelete = document.getElementById('btn-delete-selected');
        const url = btnDelete.getAttribute('data-url');

        // Отправка запроса на сервер
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': typeof getCookie === 'function' ? getCookie('csrftoken') : document.querySelector('[name=csrfmiddlewaretoken]')?.value
            },
            body: JSON.stringify({ task_ids: taskIds })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Удаляем строки из таблицы
                taskIds.forEach(id => {
                    const row = document.getElementById(`task-row-${id}`);
                    if (row) row.remove();
                });

                // Вызываем перерасчет номеров строк
                if (typeof renumberTableRows === 'function') renumberTableRows();

                // Сбрасываем состояние интерфейса
                const selectAll = document.getElementById('select-all-tasks');
                if (selectAll) selectAll.checked = false;

                btnDelete.classList.add('d-none');

                const btnEdit = document.getElementById('btn-edit-selected');
                if (btnEdit) btnEdit.classList.add('d-none');

                const selectedCountSpan = document.getElementById('selected-count');
                if (selectedCountSpan) selectedCountSpan.textContent = '0';

                //alert(data.message);
            } else {
                alert('Ошибка выполнения: ' + data.message);
            }
        })
        .catch(error => alert('Ошибка удаления: ' + error.message));
    });

    // Показываем красивое модальное окно Bootstrap вместо confirm()
    bootstrapDeleteModal.show();
}
