// === Модуль для инлайн-управления периодичностью прямо в таблице задач ===
import { formatDurationFromSeconds } from './taskPeriodicity.js';
import { getCookie } from './secondary-system-functions.js';

// Полностью синхронизируем константы с вашим основным модулем
const SECONDS_IN = {
    years: 31536000,
    months: 2592000,
    weeks: 604800,
    days: 86400,
    hours: 3600,
    minutes: 60
};

export function initInlinePeriodicity() {
    const tableBody = document.getElementById('tasks-table-body');
    if (!tableBody) return;

    // 1. Инициализация (заполнение) полей при открытии дропдауна из data-seconds
    tableBody.addEventListener('show.bs.dropdown', function (e) {
        const cell = e.target.closest('.task-periodicity-cell');
        if (!cell) return;

        const row = cell.closest('tr');

        // НАДЕЖНЫЙ ПРЕДОХРАНИТЕЛЬ: Ищем заполненное время напоминания в этой строке
        // Проверяем наличие активного желтого колокольчика (.bi-bell-fill)
        // ИЛИ наличие скрытого инпута с сохраненной датой (.raw-reminder-date)
        const hasActiveReminder = row.querySelector('.task-reminder-cell .bi-bell-fill') ||
                                  row.querySelector('.task-reminder-cell .raw-reminder-date')?.value;

        if (!hasActiveReminder) {
            e.preventDefault(); // ОТМЕНЯЕМ открытие дропдауна, если времени нет!
            return;
        }

        // Считываем секунды из data-seconds ячейки
        const totalSeconds = parseInt(cell.getAttribute('data-seconds'), 10) || 0;
        const valueInput = cell.querySelector('.inline-period-value');
        const unitSelect = cell.querySelector('.inline-period-unit');

        if (!valueInput || !unitSelect) return;

        // Раскладываем секунды по инпутам по вашей схеме (от большего к меньшему)
        if (totalSeconds <= 0) {
            valueInput.value = '';
            unitSelect.value = 'none';
            valueInput.disabled = true;
        } else if (totalSeconds % SECONDS_IN.years === 0) {
            valueInput.value = totalSeconds / SECONDS_IN.years;
            unitSelect.value = 'years';
            valueInput.disabled = false;
        } else if (totalSeconds % SECONDS_IN.months === 0) {
            valueInput.value = totalSeconds / SECONDS_IN.months;
            unitSelect.value = 'months';
            valueInput.disabled = false;
        } else if (totalSeconds % SECONDS_IN.weeks === 0) {
            valueInput.value = totalSeconds / SECONDS_IN.weeks;
            unitSelect.value = 'weeks';
            valueInput.disabled = false;
        } else if (totalSeconds % SECONDS_IN.days === 0) {
            valueInput.value = totalSeconds / SECONDS_IN.days;
            unitSelect.value = 'days';
            valueInput.disabled = false;
        } else if (totalSeconds % SECONDS_IN.hours === 0) {
            valueInput.value = totalSeconds / SECONDS_IN.hours;
            unitSelect.value = 'hours';
            valueInput.disabled = false;
        } else {
            valueInput.value = Math.floor(totalSeconds / SECONDS_IN.minutes);
            unitSelect.value = 'minutes';
            valueInput.disabled = false;
        }
    });

    // 2. Логика второго варианта: Активация/Блокировка инпута при изменении селекта
    tableBody.addEventListener('change', function (e) {
        if (e.target.classList.contains('inline-period-unit')) {
            const cell = e.target.closest('.task-periodicity-cell');
            const valueInput = cell?.querySelector('.inline-period-value');

            if (valueInput) {
                if (e.target.value === 'none') {
                    valueInput.value = '';
                    valueInput.disabled = true;
                } else {
                    valueInput.disabled = false;
                    // Если поле было пустым, подставляем удобную единицу "1"
                    if (!valueInput.value) valueInput.value = '1';
                    valueInput.focus();
                }
            }
        }
    });

    // 3. Обработка кнопки "Отмена"
    tableBody.addEventListener('click', function (e) {
        if (e.target.classList.contains('btn-inline-period-cancel')) {
            closeDropdown(e.target);
        }
    });

    // 4. Обработка кнопки "ОК" (Сбор данных и отправка)
    tableBody.addEventListener('click', function (e) {
        if (!e.target.classList.contains('btn-inline-period-save')) return;

        const cell = e.target.closest('.task-periodicity-cell');
        const taskId = cell.getAttribute('data-id');

        const valueInput = cell.querySelector('.inline-period-value');
        const unitSelect = cell.querySelector('.inline-period-unit');

        const value = parseInt(valueInput.value, 10) || 0;
        const unit = unitSelect.value;

        // Если период выбран, но число невалидно
        if (unit !== 'none' && value <= 0) {
            alert('Пожалуйста, укажите значение периода больше нуля');
            valueInput.focus();
            return;
        }

        // Вычисляем итоговые секунды
        let totalSeconds = 0;
        if (unit !== 'none' && value > 0) {
            totalSeconds = value * SECONDS_IN[unit];
        }

        saveInlinePeriodicity(taskId, totalSeconds, cell);
    });
}

/**
 * Закрытие Bootstrap Dropdown
 */
function closeDropdown(element) {
    const cell = element.closest('.task-periodicity-cell');
    const trigger = cell?.querySelector('.inline-periodicity-trigger');
    if (trigger) {
        const dropdownInstance = bootstrap.Dropdown.getInstance(trigger);
        dropdownInstance?.hide();
    }
}

/**
 * Отправка AJAX POST-запроса на бэкенд класса
 */
function saveInlinePeriodicity(taskId, seconds, cell) {
    const formData = new FormData();
    formData.set('id', taskId);
    formData.set('periodicity_seconds', seconds);

    fetch('/daily/task/update-periodicity/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Ошибка сервера');
        return response.json();
    })
    .then(data => {
        if (data.success === false) {
            alert('Ошибка при сохранении: ' + (data.error || 'Неизвестная ошибка'));
            return;
        }

        // УСПЕХ: Обновляем data-seconds в DOM ячейки
        cell.setAttribute('data-seconds', seconds);

        // Перерисовываем содержимое триггера
        const trigger = cell.querySelector('.inline-periodicity-trigger');
        if (seconds > 0) {
            const textValue = formatDurationFromSeconds(seconds);
            trigger.innerHTML = `
                <i class="bi bi-arrow-repeat me-1 text-warning"></i>
                <span class="period-text">${textValue}</span>
            `.trim();
        } else {
            trigger.innerHTML = `<i class="bi bi-arrow-repeat text-muted"></i>`;
        }

        // Закрываем окошко
        closeDropdown(cell);
    })
    .catch(error => {
        console.error('Ошибка инлайн-сохранения:', error);
        alert('Не удалось сохранить изменения. Подробности в консоли.');
    });
}
