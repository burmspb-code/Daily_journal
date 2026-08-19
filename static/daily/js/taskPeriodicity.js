// === Модуль для управления полями периодичности задачи в модальном окне ===

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
    // 1. Слушаем изменения в селекте периодичности Django-формы
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'id_periodicity_1') {
            handleFieldsToggle();
        }
    });

    // 2. ПРЕДОХРАНИТЕЛЬ: Ловим клавиатурный ввод в поле даты
    document.addEventListener('input', function(e) {
        if (e.target && e.target.id === 'id_reminder_at') {
            handleFieldsToggle();
        }
    });

    // 3. Ловим выбор даты мышкой через стандартный календарь
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'id_reminder_at') {
            handleFieldsToggle();
        }
    });

    // 4. ЖЕЛЕЗОБЕТОННАЯ СТРАХОВКА: Ловим потерю фокуса и закрытие системного календаря.
    // Событие 'blur' не всплывает стандартным образом, поэтому используем третий аргумент true (capture phase)
    document.addEventListener('blur', function(e) {
        if (e.target && e.target.id === 'id_reminder_at') {
            // Небольшой таймаут, чтобы браузер успел очистить value перед проверкой
            setTimeout(() => {
                handleFieldsToggle();
            }, 10);
        }
    }, true);

    // 5. Разблокируем поля перед отправкой формы, чтобы данные улетели в Django
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
 * Управляет доступностью полей периодичности в модальном окне.
 */
export function handleFieldsToggle() {
    const reminderInput = document.getElementById('id_reminder_at');
    const valueInput = document.getElementById('id_periodicity_0');
    const unitSelect = document.getElementById('id_periodicity_1');

    if (!unitSelect || !valueInput) return;

    const hasReminder = reminderInput && reminderInput.value.trim() !== "";

    if (!hasReminder) {
        // Просто блокируем элементы, если даты изначально нет при открытии
        unitSelect.disabled = true;
        valueInput.disabled = true;
        return;
    }

    unitSelect.disabled = false;
    if (unitSelect.value === 'none') {
        valueInput.value = '';
        valueInput.disabled = true;
    } else {
        valueInput.disabled = false;
    }
}

/**
 * Заполняет поля периодичности в модальном окне на основе переданных секунд из БД.
 */
export function setPeriodicityFields(totalSeconds) {
    // ИСПРАВЛЕНО: Указываем точные ID вашей Django-формы
    const valueInput = document.getElementById('id_periodicity_0');
    const unitSelect = document.getElementById('id_periodicity_1');

    if (!valueInput || !unitSelect) return;

    if (!totalSeconds || totalSeconds <= 0) {
        valueInput.value = '';
        unitSelect.value = 'none';
        handleFieldsToggle();
        return;
    }

    const SECONDS_IN = { YEAR: 31536000, MONTH: 2592000, WEEK: 604800, DAY: 86400, HOUR: 3600, MINUTE: 60 };

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
