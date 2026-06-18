from django.urls import path
from .views import TaskListView, TaskCreateView
from .apps import DailyConfig


app_name = DailyConfig.name

urlpatterns = [
    # Страница с таблицей задач
    path('', TaskListView.as_view(), name='task_list'),
    # Страница создания новой задачи
    path('task/add/', TaskCreateView.as_view(), name='task_create'),
]
