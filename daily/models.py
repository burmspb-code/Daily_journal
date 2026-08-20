from django.conf import settings
from django.db import models


class Bookmark(models.Model):
    """
    Модель для закладки.
    Используется для консолидации задач по определенному смысловому признаку.
    Attributes:
        title (str): Уникальное или смысловое наименование закладки.
        description (str): Подробное описание назначения данной закладки.
    """

    title = models.CharField(
        max_length=100,
        verbose_name="Наименование",
        help_text="Введите наименование закладки",
    )

    description = models.TextField(
        verbose_name="Описание", help_text="Введите описание закладки"
    )

    # Связь с моделью пользователя
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        verbose_name="Автор",
    )

    class Meta:
        """Класс метаданных."""

        verbose_name = "Закладка"
        verbose_name_plural = "Закладки"
        ordering = ["title"]

    def __str__(self):
        return self.title


from django.db import models
from django.conf import settings


class Task(models.Model):
    """
    Модель для представления задачи.

    Используется для хранения и управления данными задач, импортированных
    или синхронизированных со структурой внешней таблицы (например, Excel).

    Attributes:
        title (str): Наименование задачи или контрагента (Столбец B).
        created_at (datetime): Дата и время автоматического создания записи (Столбец C).
        reminder_at (datetime, optional): Дата и время напоминания (Столбец D).
        periodicity (timedelta): Периодичность повторения задачи.
        comment (str, optional): Дополнительный текстовый комментарий к задаче (Столбец E).
        status_flag (int): Числовой признак для внутренней логики управления (Столбец F).
        bookmark (Bookmark): Ссылка на объект закладки, к которой привязана задача.
        owner (User): Автор/владелец задачи.
        is_notified (bool): Флаг успешной отправки уведомления.
    """

    class StatusChoices(models.IntegerChoices):
        CREATED = 0, "Создана"
        IN_PROGRESS = 1, "В работе"
        COMPLETED = 2, "Выполнена"
        OVERDUE = 3, "Просрочена"

    # Наименование контрагента/задачи
    title = models.CharField(max_length=255, verbose_name="Наименование")

    # Столбец C: Время создания
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Время создания")

    # Время напоминания (разрешаем null для строк со звездочкой)
    # db_index=True добавлен для быстрого поиска задач, по которым нужно отправить пуш
    reminder_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="Время напоминания"
    )

    # Количественное значение периода
    periodicity_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Значение периода"
    )

    # Показатель периода
    periodicity_unit = models.CharField(
        max_length=10,
        default='none',
        choices=[
            ('none', 'Не повторять'),
            ('minutes', 'Минут'),
            ('hours', 'Часов'),
            ('days', 'Дней'),
            ('weeks', 'Недель'),
            ('months', 'Месяцев'),
            ('years', 'Лет'),
        ],
        verbose_name="Единица времени"
    )

    # Комментарий к задаче
    comment = models.TextField(null=True, blank=True, verbose_name="Комментарий")

    # Столбец F: Признак для логики управления данными (по умолчанию 0)
    status_flag = models.IntegerField(
        default=StatusChoices.CREATED,
        choices=StatusChoices.choices,
        verbose_name="Признак управления",
    )

    # Связь с моделью Закладки
    bookmark = models.ForeignKey(
        "Bookmark",  # Рекомендуется использовать строку, если модель объявлена ниже
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Закладка",
        help_text="Выберите закладку",
    )

    # Связь с моделью пользователя
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Автор",
    )

    # Флаг успешной отправки уведомления
    is_notified = models.BooleanField(
        default=False,
        verbose_name="Уведомление отправлено",
        help_text="Флаг контроля, чтобы не отправлять пуш повторно",
    )

    class Meta:
        """Класс метаданных."""

        db_table = "tasks"
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ["id"]  # Оставьте, если жестко завязано на порядок Excel (Столбец A)

    def __str__(self):
        return f"№{self.id} | {self.title} | Флаг: {self.get_status_flag_display()}"
