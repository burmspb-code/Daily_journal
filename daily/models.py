from django.conf import settings
from django.db import models


class Bookmark(models.Model):
    """
    Модель для закладки.
    Используется для консолидации задач по определенному смысловому признаку.
    Attributes:
        name (str): Уникальное или смысловое наименование закладки.
        description (str): Подробное описание назначения данной закладки.
    """
    title = models.CharField(
        max_length=100,
        verbose_name="Наименование",
        help_text="Введите наименование закладки"
    )

    description = models.TextField(
        verbose_name="Описание",
        help_text="Введите описание закладки"
    )

    # Связь с моделью пользователя
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        verbose_name="Автор"
    )

    class Meta:
        """Класс метаданных."""
        verbose_name = "Закладка"
        verbose_name_plural = "Закладки"
        ordering = ['title']

    def __str__(self):
        return self.title


class Task(models.Model):
    """
    Модель для представления задачи.
    Используется для хранения и управления данными задач, импортированных
    или синхронизированных со структурой внешней таблицы (например, Excel).
    Attributes:
        name (str): Наименование задачи или контрагента (Столбец B).
        created_at (datetime): Дата и время автоматического создания записи (Столбец C).
        reminder_at (datetime, optional): Дата и время напоминания.
            Может быть пустым для записей со спец-символами (Столбец D).
        comment (str, optional): Дополнительный текстовый комментарий к задаче (Столбец E).
        status_flag (int): Числовой признак для внутренней логики управления данными.
            По умолчанию равен 0 (Столбец F).
        bookmark (Bookmark): Ссылка на объект закладки, к которой привязана задача.
    """
    # Столбец B: Наименование контрагента/задачи
    title = models.CharField(
        max_length=255,
        verbose_name="Наименование"
    )

    # Столбец C: Время создания
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время создания"
    )

    # Столбец D: Время напоминания (разрешаем null для строк со звездочкой)
    reminder_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время напоминания"
    )

    # Столбец E: Комментарий к задаче
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="Комментарий"
    )

    # Столбец F: Признак для логики управления данными (по умолчанию 0)
    status_flag = models.IntegerField(
        default=0,
        verbose_name="Признак управления"
    )

    # Связь с моделью Закладки
    bookmark = models.ForeignKey(
        Bookmark,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Закладка",
        help_text="Выберите закладку"
    )

    # Связь с моделью пользователя
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Автор"
    )

    class Meta:
        """Класс метаданных."""
        db_table = 'tasks'  # Имя таблицы в PostgreSQL
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['id']  # Сортировка по порядку (Столбец A)

    def __str__(self):
        return f"№{self.id} | {self.title} | Флаг: {self.status_flag}"
