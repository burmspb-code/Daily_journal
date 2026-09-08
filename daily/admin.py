from django.contrib import admin

from daily.models import Bookmark, Task


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

    # Поля, которые будут отображаться в таблице
    list_display = (
        "title",
        "created_at",
        "reminder_at",
        "comment",
        "status_flag",
        "bookmark",
        "owner",
    )

    # Клик по этим полям будет открывать страницу редактирования пользователя
    list_display_links = ("title",)

    # Поля, по которым можно фильтровать пользователей в правой панели
    list_filter = ("owner",)
