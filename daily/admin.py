from django.contrib import admin
from daily.models import Bookmark, Task


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    """
        Конфигурация панели администратора для модели Bookmark (Закладки).
        Определяет структуру отображения списка закладок в интерфейсе админки.
    """
    list_display = ('name', 'description')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
        Конфигурация панели администратора для модели Task (Задачи).
        Определяет набор полей, выводимых в таблице задач, включая
        временные метки, статусы и связь с моделью Bookmark.
    """
    list_display = (
        'name',
        'created_at',
        'reminder_at',
        'comment',
        'status_flag',
        'bookmark',
    )
