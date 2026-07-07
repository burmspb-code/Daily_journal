from django.urls import path
from .views import TaskListView, TaskCreateView, TaskUpdateApiView, TaskDeleteApiView
from .apps import DailyConfig


app_name = DailyConfig.name

urlpatterns = [
    # Страница с таблицей задач
    path('', TaskListView.as_view(), name='task_list'),
    # Страница создания новой задачи
    path('task/add/', TaskCreateView.as_view(), name='task_create'),
    # Страница редактирования задачи
    path('task/update-api/', TaskUpdateApiView.as_view(), name='task_update_api'),
    # Страница для удаления
    path('task/delete-api/', TaskDeleteApiView.as_view(), name='task_delete_api'),
]
