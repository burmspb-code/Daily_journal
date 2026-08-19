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
    saveInlineTask
} from './create-task.js';
import { deleteSelectedTasks } from './delete-tasks.js'
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
import {
    initPeriodicityListeners,
    handleFieldsToggle,
    setPeriodicityFields,
    formatDurationFromSeconds
} from './taskPeriodicity.js';
import { initInlinePeriodicity } from './inline-periodicity-editor.js';

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
window.initPeriodicityListeners = initPeriodicityListeners;
window.handleFieldsToggle = handleFieldsToggle;
window.setPeriodicityFields = setPeriodicityFields;
window.formatDurationFromSeconds = formatDurationFromSeconds;
window.initInlinePeriodicity = initInlinePeriodicity;

// ==========================================
// 3. ГЛОБАЛЬНЫЕ ЭЛЕМЕНТЫ ИНТЕРФЕЙСА
// ==========================================
document.addEventListener('DOMContentLoaded', function () {
    const selectAllCheckbox = document.getElementById('select-all-tasks');
    const btnEdit = document.getElementById('btn-edit-selected');
    const btnDelete = document.getElementById('btn-delete-selected');
    const selectedCountSpan = document.getElementById('selected-count');
    const tasksTable = document.getElementById('tasks-table');

    // Автоматическая инициализация модулей
    initReminderEditing();
    initInlinePeriodicity(); // <--- ДОБАВЛЕНО: Запускаем инлайн-редактор при старте страницы!

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
                const taskId = checkedBoxes[0].getAttribute('data-id');
                btnEdit.setAttribute('hx-get', `/daily/task/edit-modal/${taskId}/`);

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

        // ПРЕДОХРАНИТЕЛЬ: Если этот дропдаун находится внутри ячейки таблицы инлайн-выбора,
        // полностью игнорируем его и не вешаем автозакрытие по уходу мыши!
        if (dropdownWrapper.closest('.task-periodicity-cell')) return;

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
