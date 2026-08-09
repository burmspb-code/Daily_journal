from django.urls import path

from .apps import DailyConfig
from .views import (
    TaskListView,
    TaskUpdateApiView,
    TaskDeleteApiView,
    BookmarkCreateView,
    BookmarkUpdateApiView,
    TaskCreateApiView,
)

app_name = DailyConfig.name

urlpatterns = [
    # =========================================================================
    # ВЕБ-ИНТЕРФЕЙС (HTML СТРАНИЦЫ ДЛЯ БРАУЗЕРА)
    # =========================================================================

    # Маршрут с таблицей задач
    path("", TaskListView.as_view(), name="task_list"),
    # НОВЫЙ МАРШРУТ ДЛЯ ИНЛАЙН-СОЗДАНИЯ
    path("task/create-api/", TaskCreateApiView.as_view(), name="task_create_api"),
    # Маршрут инлайн редактирования задачи
    path("task/update-api/", TaskUpdateApiView.as_view(), name="task_update_api"),
    # Маршрут для удаления задачи
    path("task/delete-api/", TaskDeleteApiView.as_view(), name="task_delete_api"),
    # Маршрут для создания закладки
    path("bookmark/add/", BookmarkCreateView.as_view(), name="bookmark_create"),
    # Маршрут редактирования закладки
    path("bookmark/update-api/", BookmarkUpdateApiView.as_view(), name="bookmark_update_api",),

    # =========================================================================
    # REST API V1 (ДЛЯ МОБИЛЬНЫХ ПРИЛОЖЕНИЙ И ФРОНТЕНДА)
    # =========================================================================


]
