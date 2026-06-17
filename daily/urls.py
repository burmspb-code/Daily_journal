from django.urls import path
from .views import TaskListView  # Импортируем наш новый класс

urlpatterns = [
    # Заменяем функцию на класс
    path('', TaskListView.as_view(), name='task_list'),
]
