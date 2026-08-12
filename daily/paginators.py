"""Модуль для описания пагинаций приложения daily."""

from rest_framework.pagination import PageNumberPagination

class TaskListAPIViewPagination(PageNumberPagination):
    """Пагинация для вывода списка задач через API запрос."""
    page_size = 10 # Количество элементов на странице
    page_size_query_param = 'page_size' # Параметр запроса для указания количества элементов на странице
    max_page_size = 15 # Максимальное количество элементов на странице
