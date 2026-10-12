"""
Конфигурация URL-маршрутов для приложения 'daily'.
"""

from django.urls import path

from .apps import DailyConfig
from .views import (
    BookmarkCreateView,
    BookmarkDeleteView,
    BookmarkListCreateAPIView,
    BookmarkUpdateExternalApiView,
    BookmarkUpdateWebResponseView,
    TaskCreateView,
    TaskDeleteView,
    TaskListAPIView,
    TaskListView,
    TaskUpdateExternalApiView,
    TaskUpdateView,
    UpdateTaskPeriodicityView,
    UpdateTaskStatusView,
)

app_name = DailyConfig.name

urlpatterns = [
    # =========================================================================
    # ВЕБ-ИНТЕРФЕЙС (HTML СТРАНИЦЫ ДЛЯ БРАУЗЕРА)
    # =========================================================================
    # Маршрут со списком задач
    path("", TaskListView.as_view(), name="task_list"),
    # НОВЫЙ МАРШРУТ ДЛЯ ИНЛАЙН-СОЗДАНИЯ
    path("task/create/", TaskCreateView.as_view(), name="task_create"),
    # Маршрут инлайн редактирования задачи
    path("task/update/", TaskUpdateView.as_view(), name="task_update"),
    # Маршрут для редактирование через модальное окно для GET (HTMX)
    path('task/edit-modal/<int:task_id>/', TaskUpdateView.as_view(), name='task_edit_modal'),
    # Маршрут инлайн радактирования периода напоминания
    path(
        "task/update-periodicity/",
        UpdateTaskPeriodicityView.as_view(),
        name="update_task_periodicity",
    ),
    # Маршрут инлайн редактирования статуса задачи
    path(
        "task/update-status/",
        UpdateTaskStatusView.as_view(),
        name="update_task_status",
    ),
    # Маршрут для удаления задачи
    path("task/delete/", TaskDeleteView.as_view(), name="task_delete"),
    # Маршрут для создания закладки
    path("bookmark/add/", BookmarkCreateView.as_view(), name="bookmark_create"),
    # Маршрут редактирования закладки
    path(
        "bookmark/update/",
        BookmarkUpdateWebResponseView.as_view(),
        name="bookmark_update",
    ),
    path(
        "bookmark/delete/",
        BookmarkDeleteView.as_view(),
        name="bookmark_delete"
    ),
    # =========================================================================
    # REST API V1 (ДЛЯ МОБИЛЬНЫХ ПРИЛОЖЕНИЙ И ФРОНТЕНДА)
    # =========================================================================
    # URL для задач (возвращает список задач)
    path("api/v1/tasks/", TaskListAPIView.as_view(), name="task_list_api"),
    # URL для создания новой закладки (POST) или получения списка закладок(GET)
    path(
        "api/v1/bookmarks/",
        BookmarkListCreateAPIView.as_view(),
        name="bookmark_list_create_api",
    ),
    # URL для просмотра(GET), обновления(PUT / PATCH) и удаления(DELETE) конкретной закладки
    path(
        "api/v1/bookmarks/<int:pk>/",
        BookmarkUpdateExternalApiView.as_view(),
        name="bookmark_api",
    ),
    # URL для просмотра(GET), обновления(PUT / PATCH) и удаления(DELETE) конкретной задачи
    path(
        "api/v1/tasks/<int:pk>/",
        TaskUpdateExternalApiView.as_view(),
        name="task_api",
    ),
]
