// === Модуль для управления полями периодичности задачи ===

const SECONDS_IN = {
    YEAR: 31536000,
    MONTH: 2592000,
    WEEK: 604800,
    DAY: 86400,
    HOUR: 3600,
    MINUTE: 60
};

/**
 * Инициализирует логику переключения состояния полей (активно/заблокировано).
 */
export function initPeriodicityListeners() {
    // Слушаем изменения в селекте периодичности
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'edit-task-period-unit') {
            handleFieldsToggle();
        }
    });

    // ПРЕДОХРАНИТЕЛЬ: Слушаем ввод/удаление даты в реальном времени
    document.addEventListener('input', function(e) {
        if (e.target && e.target.id === 'id_reminder_at') {
            handleFieldsToggle();
        }
    });

    // ВАЖНО: Разблокируем поля прямо перед отправкой формы!
    // Иначе заблокированные (disabled) поля не попадут в FormData и Django выдаст ошибку.
    document.addEventListener('submit', function(e) {
        if (e.target && e.target.id === 'edit-task-form') {
            const unitSelect = document.getElementById('edit-task-period-unit');
            const valueInput = document.getElementById('edit-task-period-value');
            if (unitSelect) unitSelect.disabled = false;
            if (valueInput) valueInput.disabled = false;
        }
    });
}

/**
 * Управляет доступностью полей периодичности.
 * Предохранитель срабатывает, если поле "Время напоминания" пустое.
 */
export function handleFieldsToggle() {
    const reminderInput = document.getElementById('id_reminder_at');
    const unitSelect = document.getElementById('edit-task-period-unit');
    const valueInput = document.getElementById('edit-task-period-value');

    if (!unitSelect || !valueInput) return;

    // Проверяем, заполнено ли время напоминания
    const hasReminder = reminderInput && reminderInput.value.trim() !== "";

    if (!hasReminder) {
        // ПРЕДОХРАНИТЕЛЬ СРАБОТАЛ: Если даты нет, намертво блокируем оба поля
        unitSelect.value = 'none';
        unitSelect.disabled = true;
        unitSelect.classList.add('bg-secondary');

        valueInput.value = '';
        valueInput.disabled = true;
        valueInput.classList.add('bg-secondary');
        valueInput.removeAttribute('required');
        return;
    }

    // Если дата есть, возвращаем стандартное поведение селекта
    unitSelect.disabled = false;
    unitSelect.classList.remove('bg-secondary');

    if (unitSelect.value === 'none') {
        valueInput.value = '';
        valueInput.disabled = true;
        valueInput.classList.add('bg-secondary');
        valueInput.removeAttribute('required');
    } else {
        valueInput.disabled = false;
        valueInput.classList.remove('bg-secondary');
        valueInput.setAttribute('required', 'required');
    }
}

/**
 * Заполняет поля периодичности в модальном окне на основе переданных секунд из БД.
 */
export function setPeriodicityFields(totalSeconds) {
    const valueInput = document.getElementById('edit-task-period-value');
    const unitSelect = document.getElementById('edit-task-period-unit');

    if (!valueInput || !unitSelect) return;

    if (!totalSeconds || totalSeconds <= 0) {
        valueInput.value = '';
        unitSelect.value = 'none';
        handleFieldsToggle(); // handleFieldsToggle сама заблокирует поля, если даты нет
        return;
    }

    if (totalSeconds % SECONDS_IN.YEAR === 0) {
        valueInput.value = totalSeconds / SECONDS_IN.YEAR;
        unitSelect.value = 'years';
    } else if (totalSeconds % SECONDS_IN.MONTH === 0) {
        valueInput.value = totalSeconds / SECONDS_IN.MONTH;
        unitSelect.value = 'months';
    } else if (totalSeconds % SECONDS_IN.WEEK === 0) {
        valueInput.value = totalSeconds / SECONDS_IN.WEEK;
        unitSelect.value = 'weeks';
    } else if (totalSeconds % SECONDS_IN.DAY === 0) {
        valueInput.value = totalSeconds / SECONDS_IN.DAY;
        unitSelect.value = 'days';
    } else if (totalSeconds % SECONDS_IN.HOUR === 0) {
        valueInput.value = totalSeconds / SECONDS_IN.HOUR;
        unitSelect.value = 'hours';
    } else {
        valueInput.value = Math.floor(totalSeconds / SECONDS_IN.MINUTE);
        unitSelect.value = 'minutes';
    }

    // Проверяем финальное состояние (учитывая предохранитель)
    handleFieldsToggle();
}

/**
 * Преобразует секунды из базы данных в красивую строку для отображения в таблице (ТЗ).
 */
export function formatDurationFromSeconds(totalSeconds) {
    if (!totalSeconds || totalSeconds <= 0) return '';

    if (totalSeconds % SECONDS_IN.YEAR === 0) {
        return `${totalSeconds / SECONDS_IN.YEAR} г.`;
    } else if (totalSeconds % SECONDS_IN.MONTH === 0) {
        return `${totalSeconds / SECONDS_IN.MONTH} мес.`;
    } else if (totalSeconds % SECONDS_IN.WEEK === 0) {
        return `${totalSeconds / SECONDS_IN.WEEK} нед.`;
    } else if (totalSeconds % SECONDS_IN.DAY === 0) {
        return `${totalSeconds / SECONDS_IN.DAY} дн.`;
    } else if (totalSeconds % SECONDS_IN.HOUR === 0) {
        return `${totalSeconds / SECONDS_IN.HOUR} ч.`;
    } else {
        return `${Math.floor(totalSeconds / SECONDS_IN.MINUTE)} мин.`;
    }
}
