from django.urls import path
from .views import task_list

urlpatterns = [
    # Пустая строка означает, что это главная страница приложения
    path('', task_list, name='task_list'),
]
