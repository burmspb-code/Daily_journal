from datetime import timedelta

from django import template

register = template.Library()


@register.filter
def format_duration(value):
    """
    Кастомный Django шаблонный фильтр для форматирования объектов timedelta.

    Преобразует временной интервал (DurationField) в удобочитаемую текстовую строку
    на русском языке с указанием кратности периода (минуты, часы, дни, недели, месяцы, годы).
    Используется для вывода периодичности задач в интерфейсе таблиц.

    Args:
        value (datetime.timedelta | None): Объект временного интервала, переданный
            из контекста шаблона Django.

    Returns:
        str: Строка с отформатированным текстовым представлением периода (например, "5 дн.").
            Возвращает длинное тире "—", если:
            - Передан пустой объект (None);
            - Переданный тип данных отличается от datetime.timedelta;
            - Интервал равен 0 секунд.

    Notes:
        - Расчет месяцев и лет основан на фиксированных интервалах:
          1 месяц принят за 30 дней (2 592 000 секунд).
          1 год принят за 365 дней (31 536 000 секунд).
        - Фильтр автоматически приводит дробные результаты деления к типу integer.

    Examples:
        Внутри Python:
        >>> from datetime import timedelta
        >>> format_duration(timedelta(minutes=15))
        '15 мин.'
        >>> format_duration(timedelta(days=2))
        '2 дн.'
        >>> format_duration(None)
        '—'

        Внутри Django-шаблона (.html):
        {% load duration_tags %}
        <td>{{ task.periodicity|format_duration }}</td>
    """
    if not value or not isinstance(value, timedelta):
        return "—"

    seconds = value.total_seconds()
    if seconds == 0:
        return "—"

    # Убрано слово "Каждые " и сокращено "час." до "ч." для минимализма
    if seconds % 31536000 == 0:
        return f"{int(seconds / 31536000)} г."
    if seconds % 2592000 == 0:
        return f"{int(seconds / 2592000)} мес."
    if seconds % 604800 == 0:
        return f"{int(seconds / 604800)} нед."
    if seconds % 86400 == 0:
        return f"{int(seconds / 86400)} дн."
    if seconds % 3600 == 0:
        return f"{int(seconds / 3600)} ч."

    return f"{int(seconds / 60)} мин."
