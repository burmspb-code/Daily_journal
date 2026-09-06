// === Модуль управления полями периодичности ===

/**
 * Инициализирует логику переключения состояния полей (активно/заблокировано).
 */
export function initPeriodicityListeners() {
    // Слушаем изменения в селекте единиц времени или в поле даты
    document.addEventListener('change', function(e) {
        if (e.target && (e.target.id === 'id_periodicity_1' || e.target.classList.contains('inline-period-unit'))) {
            handleFieldsToggle(e.target);
        }
        if (e.target && (e.target.id === 'id_reminder_at' || e.target.classList.contains('raw-reminder-date'))) {
            handleFieldsToggle(e.target);
        }
    });

    // Ловим ручной ввод даты
    document.addEventListener('input', function(e) {
        if (e.target && (e.target.id === 'id_reminder_at' || e.target.classList.contains('raw-reminder-date'))) {
            handleFieldsToggle(e.target);
        }
    });

    // Ловим потерю фокуса с поля даты (для календаря)
    document.addEventListener('blur', function(e) {
        if (e.target && (e.target.id === 'id_reminder_at' || e.target.classList.contains('raw-reminder-date'))) {
            handleFieldsToggle(e.target);
        }
    }, true);  // true для capture phase

    // Разблокируем элементы перед отправкой, чтобы Django-форма не пропустила данные
    document.addEventListener('submit', function(e) {
        if (e.target && e.target.id === 'edit-task-form') {
            const valueInput = document.getElementById('id_periodicity_0');
            const unitSelect = document.getElementById('id_periodicity_1');
            if (unitSelect) unitSelect.disabled = false;
            if (valueInput) valueInput.disabled = false;
        }
    });
}

/**
 * Управляет доступностью полей периодичности в зависимости от наличия даты напоминания.
 */
export function handleFieldsToggle(targetElement) {
    let reminderInput, valueInput, unitSelect;

    // Проверяем контекст: таблица или модальное окно
    if (targetElement && (targetElement.classList.contains('inline-period-unit') || targetElement.classList.contains('inline-period-value') || targetElement.closest('.task-periodicity-cell'))) {
        const cell = targetElement.closest('.task-periodicity-cell') || targetElement.closest('td');
        const row = cell ? cell.closest('tr') : null;

        valueInput = cell ? cell.querySelector('.inline-period-value') : null;
        unitSelect = cell ? cell.querySelector('.inline-period-unit') : null;
        reminderInput = row ? row.querySelector('.raw-reminder-date') : null;
    } else {
        // Главное модальное окно редактирования задачи
        reminderInput = document.getElementById('id_reminder_at');
        valueInput = document.getElementById('id_periodicity_0');
        unitSelect = document.getElementById('id_periodicity_1');
    }

    if (!unitSelect || !valueInput) return;

    const hasReminder = reminderInput && reminderInput.value.trim() !== "";

    // Селект единиц времени всегда доступен для выбора
    unitSelect.disabled = false;

    // Если даты напоминания нет — блокируем только поле количества
    if (!hasReminder) {
        valueInput.disabled = true;
        return;
    }

    // Если есть дата напоминания, управляем полем количества на основе выбора
    if (unitSelect.value === 'none') {
        valueInput.value = '';
        valueInput.disabled = true;
    } else {
        valueInput.disabled = false;
    }
}

/**
 * ПРЯМОЕ заполнение полей для инлайн-редактора в таблице (без конвертации секунд).
 */
export function setPeriodicityFields(rawValue, rawUnit, targetContainer = null) {
    let valueInput, unitSelect;

    if (targetContainer) {
        // Работаем строго внутри ячейки таблицы
        valueInput = targetContainer.querySelector('.inline-period-value');
        unitSelect = targetContainer.querySelector('.inline-period-unit');
    } else {
        // Модальное окно (используется для подстраховки)
        valueInput = document.getElementById('id_periodicity_0');
        unitSelect = document.getElementById('id_periodicity_1');
    }

    if (!valueInput || !unitSelect) return;

    // Просто копируем чистые строки из data-атрибутов HTML-шаблона таблицы
    valueInput.value = rawValue || '';
    unitSelect.value = rawUnit || 'none';

    handleFieldsToggle(valueInput);
}

/**
 * Заглушка-предохранитель, чтобы сторонние модули (inline-periodicity-editor.js) не падали при импорте.
 */
export function formatDurationFromSeconds(totalSeconds) {
    return '';
}
