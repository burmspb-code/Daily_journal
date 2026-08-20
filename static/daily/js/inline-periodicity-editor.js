// === Модуль для инлайн-управления периодичностью прямо в таблице задач ===
import { getCookie } from './secondary-system-functions.js';

export function initInlinePeriodicity() {
    const tableBody = document.getElementById('tasks-table-body');
    if (!tableBody) return;

    // 1. Инициализация (заполнение) полей при открытии дропдауна из data-value и data-unit
    tableBody.addEventListener('show.bs.dropdown', function (e) {
        const cell = e.target.closest('.task-periodicity-cell');
        if (!cell) return;

        const row = cell.closest('tr');

        // НАДЕЖНЫЙ ПРЕДОХРАНИТЕЛЬ: Ищем заполненное время напоминания в этой строке
        const hasActiveReminder = row.querySelector('.task-reminder-cell .bi-bell-fill') ||
                                  row.querySelector('.task-reminder-cell .raw-reminder-date')?.value;

        if (!hasActiveReminder) {
            e.preventDefault(); // ОТМЕНЯЕМ открытие дропдауна, если времени нет!
            return;
        }

        // ИСПРАВЛЕНО: Считываем чистые значения напрямую из новых data-атрибутов без математики
        const rawValue = cell.getAttribute('data-value') || '';
        const rawUnit = cell.getAttribute('data-unit') || 'none';

        const valueInput = cell.querySelector('.inline-period-value');
        const unitSelect = cell.querySelector('.inline-period-unit');

        if (!valueInput || !unitSelect) return;

        // Напрямую прокидываем значения в инпуты
        valueInput.value = rawValue;
        unitSelect.value = rawUnit;

        // Управляем блокировкой поля ввода
        valueInput.disabled = (rawUnit === 'none');
    });

    // 2. Логика: Активация/Блокировка инпута при изменении селекта
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
                    // Если поле было пустым, подставляем удобную дефолтную единицу "1"
                    if (!valueInput.value) valueInput.value = '1';
                    valueInput.focus();
                }
            }
        }
    });

    // 3. Обработка кнопки "Отмена"
    tableBody.addEventListener('click', function (e) {
        if (e.target.classList.contains('btn-inline-period-cancel')) {
            const toggleBtn = e.target.closest('.task-periodicity-cell')?.querySelector('[data-bs-toggle="dropdown"]');
            if (toggleBtn) {
                const bsDropdown = bootstrap.Dropdown.getOrCreateInstance(toggleBtn);
                if (bsDropdown) bsDropdown.hide();
            }
        }
    });

    // 4. Обработка кнопки "ОК" (Сбор данных и отправка)
    tableBody.addEventListener('click', function (e) {
        if (!e.target.classList.contains('btn-inline-period-save')) return;

        const cell = e.target.closest('.task-periodicity-cell');
        const taskId = cell.getAttribute('data-id');

        const valueInput = cell.querySelector('.inline-period-value');
        const unitSelect = cell.querySelector('.inline-period-unit');

        const pValue = parseInt(valueInput.value, 10) || 0;
        const pUnit = unitSelect.value;

        // Если период выбран, но число невалидно
        if (pUnit !== 'none' && pValue <= 0) {
            alert('Пожалуйста, укажите значение периода больше нуля');
            valueInput.focus();
            return;
        }

        // ИСПРАВЛЕНО: Формируем FormData со свойствами под новые поля модели Django
        const formData = new FormData();
        formData.append('task_id', taskId);
        formData.append('periodicity_value', pUnit === 'none' ? '' : pValue);
        formData.append('periodicity_unit', pUnit);

        // Отправка AJAX-запроса на бэкенд
        fetch('/daily/task/update-periodicity/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: formData
        })
        .then(response => {
            if (!response.ok) throw new Error('Ошибка сервера (400 Bad Request или 500)');
            return response.json();
        })
        .then(data => {
            // ИСПРАВЛЕНО: Обновляем новые data-атрибуты ячейки
            cell.setAttribute('data-value', pUnit === 'none' ? '' : pValue);
            cell.setAttribute('data-unit', pUnit);

            // Обновляем видимый текст в строке таблицы
            const textSpan = cell.querySelector('.period-text');
            const triggerDiv = cell.querySelector('.inline-periodicity-trigger');

            if (pUnit !== 'none' && pValue > 0) {
                const selectedText = unitSelect.options[unitSelect.selectedIndex].text.toLowerCase();

                if (textSpan) {
                    textSpan.textContent = `${pValue} ${selectedText}`;
                } else {
                    // Если до этого периода не было (был серый значок), пересоздаем внутренний HTML триггера
                    triggerDiv.innerHTML = `
                        <i class="bi bi-arrow-repeat me-1 text-warning"></i>
                        <span class="period-text">${pValue} ${selectedText}</span>
                    `;
                }
            } else {
                // Если сбросили в "Нет"
                triggerDiv.innerHTML = '<i class="bi bi-arrow-repeat text-muted"></i>';
            }

            // Закрываем выпадающий список Bootstrap
            const toggleBtn = cell.querySelector('[data-bs-toggle="dropdown"]');
            if (toggleBtn) {
                const bsDropdown = bootstrap.Dropdown.getOrCreateInstance(toggleBtn);
                if (bsDropdown) bsDropdown.hide();
            }
        })
        .catch(error => {
            console.error("Ошибка инлайн-сохранения:", error);
            alert("Не удалось сохранить изменения. Подробности в консоли.");
        });
    });
}

/**
 * Закрытие Bootstrap Dropdown
 */
function closeDropdown(element) {
    const cell = element.closest('.task-periodicity-cell');
    const trigger = cell?.querySelector('[data-bs-toggle="dropdown"]');
    if (trigger) {
        const dropdownInstance = bootstrap.Dropdown.getOrCreateInstance(trigger);
        dropdownInstance?.hide();
    }
}

/**
 * Отправка AJAX POST-запроса на бэкенд класса (БЕЗ СЕКУНД)
 */
function saveInlinePeriodicity(taskId, value, unit, cell) {
    const formData = new FormData();
    formData.set('task_id', taskId); // Передаем корректное имя ID
    formData.set('periodicity_value', unit === 'none' ? '' : value); // Передаем чистое число
    formData.set('periodicity_unit', unit);   // Передаем единицу времени (строку)

    fetch('/daily/task/update-periodicity/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Ошибка сервера (400 Bad Request или 500)');
        return response.json();
    })
    .then(data => {
        if (data.success === false) {
            alert('Ошибка при сохранении: ' + (data.error || 'Неизвестная ошибка'));
            return;
        }

        // УСПЕХ: Обновляем новые data-атрибуты в DOM ячейки таблицы
        cell.setAttribute('data-value', unit === 'none' ? '' : value);
        cell.setAttribute('data-unit', unit);

        // Находим элементы управления внутри ячейки для извлечения красивого текста
        const unitSelect = cell.querySelector('.inline-period-unit');
        const trigger = cell.querySelector('.inline-periodicity-trigger');

        if (trigger) {
            if (unit !== 'none' && value > 0 && unitSelect) {
                // Извлекаем человекочитаемый текст из селекта (например, "минуты", "часы")
                const selectedText = unitSelect.options[unitSelect.selectedIndex].text.toLowerCase();

                trigger.innerHTML = `
                    <i class="bi bi-arrow-repeat me-1 text-warning"></i>
                    <span class="period-text">${value} ${selectedText}</span>
                `.trim();
            } else {
                // Если сбросили в значение "Нет"
                trigger.innerHTML = `<i class="bi bi-arrow-repeat text-muted"></i>`;
            }
        }

        // Закрываем окошко выпадающего меню
        closeDropdown(cell);
    })
    .catch(error => {
        console.error('Ошибка инлайн-сохранения:', error);
        alert('Не удалось сохранить изменения. Подробности в консоли.');
    });
}
