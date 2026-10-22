// === КОНФИГУРАЦИЯ ИКОНОК СТАТУСОВ ЗАДАЧ ===

export const STATUS_ICONS = {
    CREATED: {
        icon: 'bi-file-earmark-plus',
        text: 'Создана',
        bg: 'bg-transparent text-success p-0 fw-medium d-inline-flex align-items-center justify-content-center gap-2 fs-6'
    },
    IN_PROGRESS: {
        icon: 'bi-gear',
        text: 'В работе',
        bg: 'bg-transparent text-warning p-0 fw-medium d-inline-flex align-items-center justify-content-center gap-2 fs-6'
    },
    COMPLETED: {
        icon: 'bi-check2-circle',
        text: 'Выполнена',
        bg: 'bg-transparent text-secondary p-0 fw-medium d-inline-flex align-items-center justify-content-center gap-2 fs-6'
    },
    DEADLINE: {
        icon: 'bi-clock-history',
        text: 'Дедлайн',
        bg: 'bg-transparent text-danger p-0 fw-medium d-inline-flex align-items-center justify-content-center gap-2 fs-6'
    }
};

// Функция для получения конфигурации по флагу статуса
export function getStatusConfig(flag) {
    const flagNum = parseInt(flag, 10);
    const configMap = {
        0: STATUS_ICONS.CREATED,
        1: STATUS_ICONS.IN_PROGRESS,
        2: STATUS_ICONS.COMPLETED,
        3: STATUS_ICONS.DEADLINE
    };
    return configMap[flagNum] || STATUS_ICONS.CREATED;
}
