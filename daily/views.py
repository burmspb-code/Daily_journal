import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import ListView, CreateView, DeleteView

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import TaskEditForm
from .forms import TaskForm, BookmarkForm
from .models import Bookmark, Task
from .services import TaskService
from  .serializer import TaskSerializer

logger = logging.getLogger(__name__)

# ========================= Эндпоинты для работы для работы через WEB===============================================

class TaskListView(LoginRequiredMixin, ListView):
    """Представление для вывода списка задач на веб-страницу.

    Использует сервисный слой `TaskService` для сборки единого контекста данных
    (задачи, закладки, состояния фильтров). Инкапсулирует логику веб-интерфейса,
    добавляя HTML-форму редактирования.
    """
    model = Task
    template_name = "daily/task_list.html"
    context_object_name = "tasks"

    def get_queryset(self):
        """Возвращает пустой QuerySet.

        Переопределен для предотвращения стандартного запроса ListView к БД.
        Все необходимые данные (включая отфильтрованные задачи) извлекаются
        оптимизированным путем в методе `get_context_data`.

        Returns:
            QuerySet: Пустой набор объектов Task.
        """
        # Оставляем этот метод для корректной работы ListView,
        # но данные возьмем сразу пачкой в get_context_data, чтобы не дублировать логику
        return Task.objects.none()

    def get_context_data(self, **kwargs):
        """Формирует итоговый контекст данных для HTML-шаблона 'task_list.html'.

        Запрашивает бизнес-данные у сервисного слоя за один проход и дополняет
        их специфичными для веб-интерфейса элементами (Django-формами).

        Args:
            **kwargs: Произвольные именованные аргументы родительского класса.

        Returns:
            dict: Полный контекст для рендеринга страницы, содержащий:
                - tasks (QuerySet): Отфильтрованные задачи пользователя.
                - bookmarks (list): Все закладки пользователя.
                - current_bookmark (Bookmark): Активная закладка.
                - current_title / current_flag / current_sort (str): Состояния UI.
                - edit_form (TaskEditForm): Форма редактирования задачи.
        """
        context = super().get_context_data(**kwargs)

        # Запрашиваем всё у сервиса за один раз
        service_data = TaskService.get_task_list_context(
            user=self.request.user, params=self.request.GET
        )
        context.update(service_data)

        # Переопределяем tasks, так как ListView ожидает их здесь
        context["tasks"] = service_data["tasks"]
        context["edit_form"] = TaskEditForm(user=self.request.user)

        return context


class TaskCreateApiView(LoginRequiredMixin, View):
    """
    Самостоятельное API-представление для быстрого инлайн-создания задачи.

    Принимает POST-запрос с JSON-телом, валидирует данные через TaskForm
    и возвращает JSON с ID новой задачи для мгновенного добавления в таблицу.
    """

    def post(self, request, *args, **kwargs):
        # Проверяем наличие закладок у пользователя перед созданием задачи
        first_bookmark = (
            Bookmark.objects.filter(owner=request.user).order_by("id").first()
        )
        if not first_bookmark:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Сначала создайте хотя бы одну закладку в верхнем меню!",
                },
                status=400,
            )

        # Читаем и валидируем JSON из тела запроса
        try:
            json_data = json.loads(request.body)
        except json.JSONDecodeError, TypeError:
            return JsonResponse(
                {"status": "error", "message": "Некорректный JSON-формат"}, status=400
            )

        # Собираем данные для формы. Если закладка не передана, берем первую доступную
        bookmark_id = json_data.get("bookmark_id") or first_bookmark.id

        form_data = {
            "title": str(json_data.get("title", "")).strip(),
            "bookmark": bookmark_id,
        }

        # Инициализируем форму (передаем user для внутренней фильтрации querysets)
        form = TaskForm(data=form_data, user=request.user)

        if form.is_valid():
            # Напрямую сохраняем объект, привязав текущего пользователя
            task = form.save(commit=False)
            task.owner = request.user
            task.save()

            formatted_date = timezone.localtime(task.created_at).strftime(
                "%d.%m.%Y %H:%M"
            )
            return JsonResponse(
                {"status": "success", "id": task.id, "created_at": formatted_date}
            )

        # Обработка ошибок валидации формы Django
        errors = ", ".join([f"{v[0]}" for k, v in form.errors.items()])
        return JsonResponse(
            {"status": "error", "message": errors or "Ошибка валидации"}, status=400
        )


class TaskUpdateApiView(LoginRequiredMixin, View):

    # Если вместо редиректа на страницу входа для API нужен чистый JSON-ответ:
    def handle_no_permission(self):
        return JsonResponse({"error": "Пользователь не авторизован"}, status=401)

    def post(self, request, *args, **kwargs):
        task_id = request.POST.get("id")

        if not task_id:
            return JsonResponse({"error": "Не передан ID задачи"}, status=400)

        try:
            # Теперь request.user гарантированно авторизован
            task = Task.objects.get(id=task_id, owner=request.user)
        except Task.DoesNotExist:
            return JsonResponse(
                {"error": "Задача не найдена или нет доступа"}, status=404
            )

        updated_fields = []

        # 1. Обновляем название
        if "title" in request.POST:
            title = request.POST.get("title", "").strip()
            if not title:
                return JsonResponse(
                    {"error": "Наименование задачи не может быть пустым"}, status=400
                )
            task.title = title
            updated_fields.append("title")

        # 2. Обновляем комментарий
        if "comment" in request.POST:
            task.comment = request.POST.get("comment", "").strip()
            updated_fields.append("comment")

        # 3. Обновляем напоминание (дата и время)
        if "reminder_at" in request.POST:
            reminder_raw = request.POST.get("reminder_at", "").strip()

            if reminder_raw:
                naive_datetime = parse_datetime(reminder_raw)
                if naive_datetime is None:
                    return JsonResponse(
                        {"error": "Неверный формат даты и времени"}, status=400
                    )

                # Привязываем к часовому поясу
                if timezone.is_naive(naive_datetime):
                    new_reminder = timezone.make_aware(naive_datetime)
                else:
                    new_reminder = naive_datetime
            else:
                new_reminder = None

            # ЛОГИКА СБРОСА УВЕДОМЛЕНИЯ:
            # Если дата изменилась, нужно сбросить флаг уведомления, чтобы пуш ушел снова
            if task.reminder_at != new_reminder:
                task.reminder_at = new_reminder
                task.is_notified = False  # Сбрасываем флаг контроля пушей
                updated_fields.extend(["reminder_at", "is_notified"])

        # Сохраняем строго измененные поля
        if updated_fields:
            # Убираем дубликаты из списка, если они появились
            task.save(update_fields=list(set(updated_fields)))

        # Формируем ответ (маппинг 'status' совпадает с вашим JS скриптом)
        return JsonResponse(
            {
                "status": "success",
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "comment": task.comment,
                    "reminder_at": (
                        task.reminder_at.isoformat() if task.reminder_at else None
                    ),
                    "status": task.status_flag,  # Передаем число (0, 1, 2, 3)
                    "status_display": task.get_status_flag_display(),  # Передаем текст ("Создана", "В работе" и т.д.)
                    "bookmark_id": task.bookmark_id,
                },
            }
        )


class TaskDeleteApiView(LoginRequiredMixin, DeleteView):
    """
    Представление для удаления задачи.

    Принимает AJAX-запросы и возвращает статус удаления в формате JSON.
    """

    model = Task

    def get_object(self, queryset=None):
        """
        Стандартный DeleteView ищет один объект.
        Мы переопределяем этот метод, чтобы он не выдавал ошибку из-за отсутствия pk в URL.
        """
        return None

    def post(self, request, *args, **kwargs):
        """
        Переопределяем точку входа POST-запроса для обработки списка ID.
        """
        try:
            # Читаем наш JSON из тела запроса
            data = json.loads(request.body)
            task_ids = data.get("task_ids", [])

            if not task_ids:
                return JsonResponse(
                    {"status": "error", "message": "Не выбрано ни одной задачи"},
                    status=400,
                )

            # Выполняем удаление через queryset
            queryset = self.get_queryset().filter(id__in=task_ids)
            deleted_count, _ = queryset.delete()

            return JsonResponse(
                {
                    "status": "success",
                    "message": f"Успешно удалено задач: {deleted_count}",
                }
            )

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


class BookmarkCreateView(LoginRequiredMixin, CreateView):
    """
    Представление для создания новой закладки.

    Обрабатывает AJAX-запросы и возвращает результат в формате JSON.
    """

    model = Bookmark
    form_class = BookmarkForm
    template_name = (
        "daily/bookmark_form.html"  # Укажите путь к вашему HTML-шаблону формы
    )
    context_object_name = "bookmark"

    def get_success_url(self):
        """
        После успешного создания закладки динамически перенаправляем
        пользователя на главную страницу с автоматическим открытием этой новой вкладки.
        """
        # self.object — это только что сохраненный в базу данных экземпляр Bookmark
        return f"{reverse('daily:task_list')}?bookmark={self.object.id}"

    def form_valid(self, form):
        """
        После успешного заполнения формы создания закладки добавляем
        в форму авторизованного пользователя вручную, т.к. данное поле
        отсутствует в форме.
        """
        # 1. Привязываем к полю owner объект текущего авторизованного пользователя
        form.instance.owner = self.request.user

        # 2. Запускаем стандартный процесс сохранения формы Django
        return super().form_valid(form)


class BookmarkUpdateApiView(LoginRequiredMixin, View):
    """
    API-представление для быстрого переименования закладки.
    Принимает стандартные данные формы (FormData), обновляя
    исключительно поле 'title'.
    """

    def post(self, request, *args, **kwargs):
        try:
            # ИСПРАВЛЕНО: Читаем данные напрямую из request.POST вместо json.loads
            bookmark_id = request.POST.get("id")
            new_title = request.POST.get("title", "").strip()

            # Быстрая проверка данных
            if not bookmark_id:
                return JsonResponse({"error": "ID закладки не передан"}, status=400)
            if not new_title:
                return JsonResponse(
                    {"error": "Название не может быть пустым"}, status=400
                )

            # Находим закладку в базе данных с проверкой владельца
            bookmark = Bookmark.objects.get(pk=bookmark_id, owner=request.user)

            # Обновляем только название и сохраняем
            bookmark.title = new_title
            bookmark.save(update_fields=["title"])

            return JsonResponse({"status": "success"}, status=200)

        except Bookmark.DoesNotExist:
            return JsonResponse(
                {"error": "Закладка не найдена или доступ запрещен"}, status=404
            )
        except Exception as e:
            return JsonResponse(
                {"error": f"Внутренняя ошибка сервера: {str(e)}"}, status=500
            )

# ========================= Эндпоинты для работы с API ===============================================

class TaskListAPIView(ListAPIView):
    """API-представление для получения списка задач в формате JSON.

    Интегрирует логику фильтрации `TaskService` с сериализаторами DRF. Возвращает
    клиенту не только массив задач, но и метаданные интерфейса (список закладок,
    активную закладку и примененные фильтры) в одном ответе.
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """Формирует структурированный JSON-ответ со списком задач и метаданными.

        Вызывает единый сервис контекста, сериализует объекты моделей Django
        в типы данных Python и возвращает унифицированный HTTP-ответ. Поддерживает
        стандартную пагинацию DRF.

        Args:
            request (Request): Объект запроса DRF.
            *args: Произвольные позиционные аргументы.
            **kwargs: Произвольные именованные аргументы.

        Returns:
            Response: Объект ответа DRF с JSON-структурой:
                {
                    "meta": {
                        "current_filters": {"title": str, "flag": str, "sort": str},
                        "bookmarks": [...],
                        "current_bookmark": {...}
                    },
                    "tasks": [...]
                }
        """
        # Получаем весь готовый контекст из сервиса
        service_context = TaskService.get_task_list_context(
            user=request.user, params=request.query_params
        )

        # Сериализуем список задач с поддержкой пагинации
        queryset = service_context["tasks"]
        page = self.paginate_queryset(queryset)
        if page is not None:
            tasks_data = self.get_serializer(page, many=True).data
        else:
            tasks_data = self.get_serializer(queryset, many=True).data

        # Сериализуем метаданные закладок
        bookmarks_serialized = BookmarkSerializer(service_context["bookmarks"], many=True).data
        current_bookmark_serialized = (
            BookmarkSerializer(service_context["current_bookmark"]).data
            if service_context["current_bookmark"] else None
        )

        # Формируем единый чистый JSON-ответ
        response_data = {
            "meta": {
                "current_filters": {
                    "title": service_context["current_title"],
                    "flag": service_context["current_flag"],
                    "sort": service_context["current_sort"],
                },
                "bookmarks": bookmarks_serialized,
                "current_bookmark": current_bookmark_serialized,
            },
            "tasks": tasks_data,
        }

        if page is not None:
            return self.get_paginated_response(response_data)

        return Response(response_data)
