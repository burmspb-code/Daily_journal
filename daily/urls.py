from django.urls import path
from .views import TaskListView, TaskCreateView, TaskUpdateApiView, TaskDeleteApiView, BookmarkCreateView, \
    BookmarkUpdateApiView
from .apps import DailyConfig

app_name = DailyConfig.name

urlpatterns = [
    # Маршрут с таблицей задач
    path('', TaskListView.as_view(), name='task_list'),
    # Маршрут создания новой задачи
    path('task/add/', TaskCreateView.as_view(), name='task_create'),
    # Маршрут редактирования задачи
    path('task/update-api/', TaskUpdateApiView.as_view(), name='task_update_api'),
    # Маршрут для удаления задачи
    path('task/delete-api/', TaskDeleteApiView.as_view(), name='task_delete_api'),
    # Маршрут для создания закладки
    path('bookmark/add/', BookmarkCreateView.as_view(), name='bookmark_create'),
    # Маршрут редактирования закладки
    path('bookmark/update-api/', BookmarkUpdateApiView.as_view(), name='bookmark_update_api'),
]
