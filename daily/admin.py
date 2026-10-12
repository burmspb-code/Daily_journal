from django.contrib import admin

from daily.models import Bookmark, NotificationAttempt, Task


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    """
    Конфигурация панели администратора для модели Bookmark (Закладки).
    Определяет структуру отображения списка закладок в интерфейсе админки.
    """

    list_display = ("title", "description")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Конфигурация панели администратора для модели Task (Задачи).
    Определяет набор полей, выводимых в таблице задач, включая
    временные метки, статусы и связь с моделью Bookmark.
    """

    list_display = (
        "title",
        "created_at",
        "reminder_at",
        "comment",
        "status_flag",
        "bookmark",
        "owner",
        "status_changed_at",
    )

    list_display_links = ("title",)

    list_filter = ("owner",)


@admin.register(NotificationAttempt)
class NotificationAttemptAdmin(admin.ModelAdmin):
    """
    Конфигурация панели администратора для модели NotificationAttempt.

    Предоставляет интерфейс для мониторинга и диагностики процесса доставки
    уведомлений. Позволяет фильтровать попытки по каналу, статусу и дате,
    искать по тексту ошибки и видеть количество попыток отправки.
    """

    list_display = (
        "task",
        "channel",
        "status",
        "attempts",
        "created_at",
        "sent_at",
        "short_error",
    )

    list_display_links = ("task",)

    list_filter = (
        "channel",
        "status",
        "created_at",
    )

    search_fields = (
        "task__title",
        "error_message",
    )

    readonly_fields = (
        "created_at",
        "sent_at",
    )

    ordering = ("-created_at",)

    def short_error(self, obj):
        """Возвращает укороченный текст ошибки для отображения в списке."""
        if not obj.error_message:
            return "—"
        return (obj.error_message[:60] + "...") if len(obj.error_message) > 60 else obj.error_message

    short_error.short_description = "Ошибка"
