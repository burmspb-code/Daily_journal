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
        ordering = ("title",)

    def __str__(self):
        return self.title


class Task(models.Model):
    """
    Модель для представления задачи.

    Используется для хранения и управления данными задач.

    Attributes:
        title (str): Наименование задачи или контрагента (Столбец B).
        created_at (datetime): Дата и время автоматического создания записи (Столбец C).
        reminder_at (datetime, optional): Дата и время напоминания (Столбец D).
        periodicity_value (int, optional): Числовое значение периодичности (например, 1, 2, 7).
        periodicity_unit (str, optional): Единица измерения периодичности ('minutes', 'days' и т.д.).
        comment (str, optional): Дополнительный текстовый комментарий к задаче (Столбец E).
        status_flag (int): Числовой признак для внутренней логики управления (Столбец F).
        bookmark (Bookmark): Ссылка на объект закладки, к которой привязана задача.
        owner (User): Автор/владелец задачи.
        status_changed_at (datetime, optional): Время последнего изменения статуса.
    """

    class StatusChoices(models.IntegerChoices):
        CREATED = 0, "Создана"
        IN_PROGRESS = 1, "В работе"
        COMPLETED = 2, "Выполнена"
        OVERDUE = 3, "Просрочена"

    # Наименование контрагента/задачи
    title = models.CharField(max_length=255, verbose_name="Наименование")

    # Время создания
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
            ('minutes', 'мин'),
            ('hours', 'ЧЧ'),
            ('days', 'ДД'),
            ('weeks', 'Н'),
            ('months', 'ММ'),
            ('years', 'ГГ'),
        ],
        verbose_name="Единица времени"
    )

    # Комментарий к задаче
    comment = models.TextField(blank=True, default='', verbose_name="Комментарий")

    # Признак для логики управления данными (по умолчанию 0)
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

    # Точное время изменения статуса фоновым роботом
    status_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время изменения статуса"
    )

    class Meta:
        """Класс метаданных."""

        db_table = "tasks"
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ("id", )  # Оставьте, если жестко завязано на порядок Excel (Столбец A)

    def __str__(self):
        return f"№{self.id} | {self.title} | Флаг: {self.get_status_flag_display()}"


class NotificationAttempt(models.Model):
    """
    Модель для отслеживания попыток доставки уведомлений по различным каналам.

    Предназначена для обеспечения наблюдаемости (observability) процесса отправки
    уведомлений в асинхронном окружении (Celery). Позволяет фиксировать статус
    каждой попытки, сохранять текст ошибки при сбое, учитывать количество
    повторных попыток и точно определять время успешной доставки.

    Бизнес‑ценность:
        *   Аудит доставки: возможность ответить пользователю «Да, письмо было
            отправлено» или «Нет, сервис почты недоступен», имея доказательства
            в БД.
        *   Контроль дублей: предотвращение повторной отправки одного и того же
            уведомления при рестарте воркеров или повторном запуске задачи.
        *   Отладка интеграций: хранение `error_message` позволяет разработчику
            увидеть точный ответ внешнего API (например, 429 Too Many Requests
            от Telegram или 550 User Unknown от SMTP) без парсинга логов.
        *   Аналитика надежности: агрегация по полю `status` и `channel` дает
            метрики SLA доставки для каждого канала.

    Жизненный цикл объекта:
        1.  Создание: происходит в начале асинхронной задачи отправки (статус
            `pending`).
        2.  Успех: при получении HTTP 200 от внешнего сервиса статус меняется
            на `sent`, заполняется `sent_at`.
        3.  Неудача: при любом исключении или не‑200 ответе статус меняется
            на `failed`, в `error_message` пишется текст ошибки, `attempts`
            увеличивается. Задача Celery может быть перезапущена (retry).
        4.  Фиксация лимита: если количество `attempts` превышает допустимый
            лимит (контролируется в логике Celery), дальнейшие попытки
            прекращаются, статус остается `failed`.

    Семантика полей:
        *   `task`: связь с бизнес‑сущностью «Задача», для которой генерируется
            уведомление. При удалении задачи все попытки доставки удаляются
            автоматически (`on_delete=models.CASCADE`).
        *   `channel`: тип канала доставки. Позволяет разделять логику и статистику
            для Email и Telegram. В будущем легко расширить новыми каналами
            (SMS, Push, WebSocket).
        *   `status`: текущий статус попытки. Используется для фильтрации
            в админке и построения дашбордов.
        *   `error_message`: хранит строковое представление исключения или
            тело ответа ошибки от внешнего API. Поле допускает NULL, чтобы
            не засорять БД пустыми значениями для успешных отправок.
        *   `attempts`: счетчик попыток. Критически важен для реализации
            экспоненциальной задержки (exponential backoff) и ограничения
            максимального числа повторов.
        *   `sent_at`: точное время успешной доставки. Позволяет отличать
            «попытка была» от «письмо реально ушло».

    Рекомендации по использованию:
        *   Для предотвращения гонки данных (race condition) при создании записи
            и обновлении статуса используйте транзакции (`transaction.atomic`)
            или блокировки строк (`select_for_update`) в контексте задач Celery.
        *   Для очистки старых данных настройте периодическую задачу (Celery Beat),
            которая удаляет записи старше 30–90 дней (в зависимости от требований
            регуляторов к хранению логов).
        *   В Django Admin добавьте фильтры по `channel`, `status` и
            `created_at__date`, а также колонку `error_message` (с ограничением
            длины вывода) для быстрой диагностики проблем.
        *   Индекс `[task, channel, status]` оптимизирует частые запросы вида:
            «Найти все неудачные попытки для задачи X по каналу Email».

    Примеры типичных запросов:
        *   Найти все неудачные попытки за сегодня:
            NotificationAttempt.objects.filter(
                status=NotificationAttempt.STATUS_FAILED,
                created_at__date=timezone.now().date()
            )
        *   Проверить, была ли уже отправлена попытка для задачи и канала:
            NotificationAttempt.objects.filter(
                task_id=task_id,
                channel=NotificationAttempt.CHANNEL_EMAIL
            ).exists()
        *   Получить последнюю ошибку для задачи:
            NotificationAttempt.objects.filter(
                task_id=task_id
            ).order_by('-created_at').first()
    """

    CHANNEL_EMAIL = "email"
    CHANNEL_TELEGRAM = "telegram"
    CHANNEL_CHOICES = (
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_TELEGRAM, "Telegram"),
    )

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="notification_attempts",
        verbose_name="Задача"
    )
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        verbose_name="Канал отправки"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Статус отправки"
    )
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Время создания")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Время отправки")
    attempts = models.PositiveIntegerField(default=0, verbose_name="Количество попыток")

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        indexes = (
            models.Index(fields=["task", "channel", "status"]),
        )

    def __str__(self) -> str:
        return f"{self.task} | {self.channel} | {self.status}"
