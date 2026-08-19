"""Сервисный слой для бизнес-логики основного приложения (daily).

Содержит классы и методы для инкапсуляции бизнес-логики, фильтрации данных
и подготовки контекста для интерфейсов (веб-страниц и REST API).
"""

from django.db.models import QuerySet
from .models import Bookmark, Task


class TaskService:
    """Сервисный класс для работы с бизнес-логикой задач.

    Предоставляет методы для агрегации данных, фильтрации, сортировки
    и минимизации количества SQL-запросов к моделям Task и Bookmark.
    """

    @staticmethod
    def get_task_list_context(user, params: dict) -> dict:
        """Формирует единый контекст данных для списка задач.

        Метод агрегирует параметры фильтрации, загружает связанные закладки
        в оперативную память для предотвращения проблемы N+1 и запрашивает
        финальный QuerySet задач. Используется совместно в Django Views и DRF API.

        Args:
            user (User): Объект текущего аутентифицированного пользователя.
            params (dict): Словарь GET-параметров запроса (или query_params в DRF).

        Returns:
            dict: Словарь с контекстом данных:
                - tasks (QuerySet): Отфильтрованный набор задач.
                - bookmarks (list): Список всех объектов Bookmark пользователя.
                - current_bookmark (Bookmark|None): Текущая активная закладка.
                - current_title (str): Применённая строка поиска по названию.
                - current_flag (str): Применённый ID флага статуса.
                - current_sort (str): Ключ текущей сортировки.
        """
        if not user or not user.is_authenticated:
            return {
                "tasks": Task.objects.none(),
                "bookmarks": [],
                "current_bookmark": None,
                "current_title": "",
                "current_flag": "",
                "current_sort": "",
            }

        # 1. Считываем параметры один раз
        title_param = params.get("title", "").strip()
        flag_param = params.get("flag", "").strip()
        sort_param = params.get("sort", "").strip()
        bookmark_param = str(params.get("bookmark", "")).strip()

        # 2. Оптимизация: загружаем все закладки в память ОДНИМ запросом
        bookmarks = list(Bookmark.objects.filter(owner=user).order_by("id"))

        # 3. Определяем текущую активную закладку в памяти
        current_bookmark = None
        if bookmark_param.isdigit():
            target_id = int(bookmark_param)
            current_bookmark = next((b for b in bookmarks if b.id == target_id), None)

        # Если ID не передан или чужой — берем первую закладку пользователя
        if not current_bookmark and bookmarks:
            current_bookmark = bookmarks[0]

        # 4. Получаем отфильтрованные задачи, передавая уже найденную закладку
        tasks_queryset = TaskService._get_filtered_tasks_queryset(
            user=user,
            current_bookmark=current_bookmark,
            title_query=title_param,
            flag_query=flag_param,
            sort_query=sort_param,
        )

        return {
            "tasks": tasks_queryset,
            "bookmarks": bookmarks,
            "current_bookmark": current_bookmark,
            "current_title": title_param,
            "current_flag": flag_param,
            "current_sort": sort_param,
        }

    @staticmethod
    def _get_filtered_tasks_queryset(
        user, current_bookmark, title_query: str, flag_query: str, sort_query: str
    ) -> QuerySet:
        """Внутренний метод для фильтрации и сортировки QuerySet задач.

        Выполняет SQL JOIN с таблицами Bookmark и User. Исключает повторные
        запросы к БД для поиска закладок за счет использования уже готового
        объекта `current_bookmark`.

        Args:
            user (User): Объект владельца задач.
            current_bookmark (Bookmark|None): Объект выбранной закладки.
            title_query (str): Поисковый запрос для фильтрации по названию (icontains).
            flag_query (str): Строковое представление ID флага статуса.
            sort_query (str): Ключ направления сортировки (newest, oldest, etc.).

        Returns:
            QuerySet: Оптимизированный и отсортированный набор объектов Task.
        """
        # SQL JOIN для предотвращения N+1
        queryset = Task.objects.filter(owner=user).select_related("bookmark", "owner")

        # Фильтрация по объекту закладки, который мы уже нашли в памяти
        if current_bookmark:
            queryset = queryset.filter(bookmark=current_bookmark)
        else:
            # У пользователя вообще нет закладок
            return Task.objects.none()

        # Поиск по названию
        if title_query:
            queryset = queryset.filter(title__icontains=title_query)

        # Фильтрация по флагу статуса
        if flag_query.isdigit():
            queryset = queryset.filter(status_flag=int(flag_query))

        # Безопасная сортировка
        sort_mapping = {
            "newest": ["-created_at", "-id"],
            "oldest": ["created_at", "id"],
            "name_asc": ["title"],
            "name_desc": ["-title"],
        }
        order_by_fields = sort_mapping.get(sort_query, ["id"])

        return queryset.order_by(*order_by_fields)
