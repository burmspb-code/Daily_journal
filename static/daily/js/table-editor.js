// ==========================================
// 1. ИМПОРТЫ МОДУЛЕЙ
// ==========================================
import './editing-bookmark-name.js';
import './editing-titles-and-comments.js';
import './paste-cleaner.js';

import { initReminderEditing } from './editing-reminder-time.js';
import { toggleDateSort } from './date-sort.js';
import {
    appendNewTaskRow,
    saveInlineTask,
    deleteSelectedTasks
} from './create-task.js';
import {
    openEditModal,
    saveTaskChanges
} from './editing-in-modal-window.js';
import {
    updateTopTaskCounter,
    renumberTableRows,
    checkIfTableIsEmpty,
    updateRowStatusBadge,
    getCookie
} from './secondary-system-functions.js';

// ==========================================
// 2. ГЛОБАЛЬНАЯ РЕГИСТРАЦИЯ ДЛЯ HTML / HTMX
// ==========================================
window.toggleDateSort = toggleDateSort;
window.updateTopTaskCounter = updateTopTaskCounter;
window.renumberTableRows = renumberTableRows;
window.checkIfTableIsEmpty = checkIfTableIsEmpty;
window.updateRowStatusBadge = updateRowStatusBadge;
window.getCookie = getCookie;
window.openEditModal = openEditModal;
window.saveTaskChanges = saveTaskChanges;
window.appendNewTaskRow = appendNewTaskRow;
window.saveInlineTask = saveInlineTask;
window.deleteSelectedTasks = deleteSelectedTasks;

// ==========================================
// 3. ГЛОБАЛЬНЫЕ ЭЛЕМЕНТЫ ИНТЕРФЕЙСА
// ==========================================
document.addEventListener('DOMContentLoaded', function () {
    const selectAllCheckbox = document.getElementById('select-all-tasks');
    const btnEdit = document.getElementById('btn-edit-selected');
    const btnDelete = document.getElementById('btn-delete-selected');
    const selectedCountSpan = document.getElementById('selected-count');
    const tasksTable = document.getElementById('tasks-table');

    // ИНИЦИАЛИЗАЦИЯ МОДУЛЯ НАПОМИНАНИЙ
    initReminderEditing();

    // === ГРУППОВЫЕ ОПЕРАЦИИ И ЧЕКБОКСЫ ===
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
            if (btnEdit) {
                btnEdit.classList.remove('d-none');

                // Передаем ID отмеченной задачи в HTMX-атрибут кнопки
                const taskId = checkedBoxes[0].getAttribute('data-id');
                btnEdit.setAttribute('hx-get', `/daily/task/edit-modal/${taskId}/`);

                // Заставляем HTMX обновить триггеры на этой кнопке
                if (typeof htmx !== 'undefined') {
                    htmx.process(btnEdit);
                }
            }
        } else {
            if (btnEdit) {
                btnEdit.classList.add('d-none');
                btnEdit.setAttribute('hx-get', '');
            }
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

    // === ДИНАМИЧЕСКИЕ ДРОПДАУНЫ (АВТОЗАКРЫТИЕ) ===
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
