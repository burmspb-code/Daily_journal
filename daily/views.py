import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, DeleteView
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    RetrieveUpdateDestroyAPIView,
    ListCreateAPIView,
    ListAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .forms import TaskEditForm, TaskForm, BookmarkForm
from .models import Bookmark, Task
from .paginators import TaskListAPIViewPagination
from .serializers import BookmarkUpdateSerializer, TaskSerializer, BookmarkSerializer
from .services import TaskService

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


class TaskCreateView(LoginRequiredMixin, View):
    """
    Представление для быстрого инлайн-создания задачи.

    Принимает POST-запрос с JSON-телом, валидирует данные через TaskForm
    и возвращает HTML-строку задачи для мгновенного добавления в таблицу.
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

            # Вычисляем номер строки
            row_number = Task.objects.filter(owner=request.user).count()

            # Рендерим HTML строки задачи
            return render(
                request,
                "daily/includes/task_row.html",
                {"task": task, "row_number": row_number}
            )

        # Обработка ошибок валидации формы Django
        errors = ", ".join([f"{v[0]}" for k, v in form.errors.items()])
        return JsonResponse(
            {"status": "error", "message": errors or "Ошибка валидации"}, status=400
        )


class TaskUpdateView(LoginRequiredMixin, View):
    """
    Представление для редактирования задачи через модальное окно.
    Поддерживает GET (отдачу HTML формы через HTMX) и POST (сохранение изменений).
    """

    def handle_no_permission(self):
        return JsonResponse({"error": "Пользователь не авторизован"}, status=401)

    def get(self, request, task_id, *args, **kwargs):
        """
        Срабатывает при вызове кнопки 'Редактировать' через hx-get.
        Генерирует HTML-код формы, где все инпуты и селекты уже заполнены значениями из БД.
        """
        # Получаем задачу текущего пользователя
        task = get_object_or_404(Task, id=task_id, owner=request.user)

        # Инициализируем форму Django, передавая в неё объект задачи и контекст пользователя
        form = TaskEditForm(instance=task, user=request.user)

        # Рендерим частичный HTML-шаблон, который содержит только инпуты
        return render(
            request,
            "daily/includes/edit_task_form.html",
            {"edit_form": form, "task": task}
        )

    def post(self, request, *args, **kwargs):
        """
        Срабатывает при отправке формы модального окна (кнопка 'Сохранить изменения').
        """
        task_id = request.POST.get("id")

        if not task_id:
            return JsonResponse({"error": "Не передан ID задачи"}, status=400)

        try:
            task = Task.objects.get(id=task_id, owner=request.user)
        except Task.DoesNotExist:
            return JsonResponse(
                {"error": "Задача не найдена или нет доступа"}, status=404
            )

        updated_fields = []

        # Обновляем название
        if "title" in request.POST:
            title = request.POST.get("title", "").strip()
            if not title:
                return JsonResponse(
                    {"error": "Наименование задачи не может быть пустым"}, status=400
                )
            task.title = title
            updated_fields.append("title")

        # Обновляем комментарий
        if "comment" in request.POST:
            task.comment = request.POST.get("comment", "").strip()
            updated_fields.append("comment")

        # Обновляем напоминание (дата и время)
        if "reminder_at" in request.POST:
            reminder_raw = request.POST.get("reminder_at", "").strip()

            if reminder_raw:
                naive_datetime = parse_datetime(reminder_raw)
                if naive_datetime is None:
                    return JsonResponse(
                        {"error": "Неверный формат даты и времени"}, status=400
                    )

                if timezone.is_naive(naive_datetime):
                    new_reminder = timezone.make_aware(naive_datetime)
                else:
                    new_reminder = naive_datetime
            else:
                new_reminder = None

            if task.reminder_at != new_reminder:
                task.reminder_at = new_reminder
                task.is_notified = False
                updated_fields.extend(["reminder_at", "is_notified"])

                # Если дата удалена, намертво стираем периодичность из новых полей БД
                if new_reminder is None:
                    if task.periodicity_value is not None or task.periodicity_unit != 'none':
                        task.periodicity_value = None
                        task.periodicity_unit = 'none'
                        updated_fields.extend(["periodicity_value", "periodicity_unit"])

        # Обновляем периодичность повторения по НОВЫМ именам полей Django-формы
        # Пропускаем этот блок, если напоминание было удалено (периодичность уже очищена выше)
        if "reminder_at" not in request.POST or request.POST.get("reminder_at", "").strip():
            unit_key = next((k for k in request.POST.keys() if "periodicity_unit" in k), None)
            value_key = next((k for k in request.POST.keys() if "periodicity_value" in k), None)

            if unit_key:
                val_0 = request.POST.get(value_key, "").strip() if value_key else ""
                val_1 = request.POST.get(unit_key, "").strip()

                new_value = None
                new_unit = "none"

                if val_1 != "none" and val_0:
                    try:
                        new_value = int(val_0)
                        new_unit = val_1
                        if new_value <= 0:
                            return JsonResponse({"error": "Значение периода должно быть больше нуля"}, status=400)
                    except (ValueError, TypeError):
                        return JsonResponse(
                            {"error": "Некорректное значение интервала"}, status=400
                        )

                if task.periodicity_value != new_value or task.periodicity_unit != new_unit:
                    task.periodicity_value = new_value
                    task.periodicity_unit = new_unit
                    updated_fields.extend(["periodicity_value", "periodicity_unit"])

        # Сохраняем строго измененные поля
        if updated_fields:
            task.save(update_fields=list(set(updated_fields)))

        response = JsonResponse(
            {
                "status": "success",
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "comment": task.comment,
                    "reminder_at": (
                        task.reminder_at.isoformat() if task.reminder_at else None
                    ),
                    "status": task.status_flag,
                    "status_display": task.get_status_flag_display(),
                    "bookmark_id": task.bookmark_id,
                    "periodicity_value": task.periodicity_value or "",
                    "periodicity_unit": task.periodicity_unit,
                    "periodicity_display": f"{task.periodicity_value} {task.get_periodicity_unit_display().lower()}" if task.periodicity_value and task.periodicity_unit != 'none' else ""
                },
            }
        )

        # Добавляем кастомный HTTP-заголовок для HTMX, что редактирование завершено
        response['HX-Trigger'] = 'taskUpdated'

        return response


class UpdateTaskPeriodicityView(LoginRequiredMixin, View):
    """
    Класс для быстрого инлайн-обновления периодичности задачи из таблицы.
    Ожидает POST-запрос с 'task_id' (или 'id'), 'periodicity_value' и 'periodicity_unit'.
    """

    def post(self, request, *args, **kwargs):
        # Безопасно поддерживаем оба варианта именования ID для защиты от опечаток в JS
        task_id = request.POST.get("task_id") or request.POST.get("id")
        p_value_raw = request.POST.get("periodicity_value")
        p_unit = request.POST.get("periodicity_unit")

        if not task_id:
            return JsonResponse(
                {"success": False, "error": "ID задачи не указан"}, status=400
            )

        try:
            # Ищем задачу, проверяя владение текущим пользователем (безопасность)
            task = Task.objects.get(id=task_id, owner=request.user)
        except Task.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Задача не найдена или доступ запрещен"},
                status=404,
            )

        try:
            if p_unit == "none" or not p_unit or p_value_raw == "" or p_value_raw is None:
                task.periodicity_value = None
                task.periodicity_unit = "none"
            else:
                # Переводим в число только если это не пустышка
                task.periodicity_value = int(p_value_raw)
                task.periodicity_unit = p_unit

            # Обновляем СТРОГО только две новые измененные колонки в БД
            task.save(update_fields=["periodicity_value", "periodicity_unit"])

            return JsonResponse({"success": True})

        except ValueError:
            return JsonResponse(
                {"success": False, "error": "Значение периода должно быть целым числом"}, status=400
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Ошибка сервера: {str(e)}"}, status=500
            )


class TaskDeleteView(LoginRequiredMixin, DeleteView):
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
    Представление для создания новой закладки через стандартный WEB-интерфейс.
    После сохранения выполняет классический редирект на список задач.
    """

    model = Bookmark
    form_class = BookmarkForm
    template_name = "daily/bookmark_form.html"  # Укажите путь к HTML-шаблону формы
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
        # Привязываем к полю owner объект текущего авторизованного пользователя
        form.instance.owner = self.request.user

        # Запускаем стандартный процесс сохранения формы Django
        return super().form_valid(form)


@extend_schema(
    exclude=True
)  # Полностью исключает это веб-представление из Swagger/Redoc
class BookmarkUpdateWebResponseView(APIView):
    """
    Эндпоинт для инлайн-редактирования названия ЗАКЛАДКИ внутри WEB-интерфейса.
    Принимает POST-запрос с JSON (id, title, description) с текущей страницы.
    Аутентификация по сессии браузера + обязательная CSRF-защита.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [
        SessionAuthentication
    ]  # Завязано на вошедшего в браузер юзера

    def post(self, request, *args, **kwargs):
        bookmark_id = request.data.get("id")

        # Находим закладку строго для текущего пользователя сайта
        try:
            bookmark = Bookmark.objects.get(id=bookmark_id, owner=request.user)
        except (Bookmark.DoesNotExist, ValueError):
            return Response(
                {"status": "error", "message": "Закладка не найдена"}, status=status.HTTP_404_NOT_FOUND
            )

        # Передаем данные в сериализатор для валидации полей 'title' и 'description'
        serializer = BookmarkUpdateSerializer(bookmark, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({"status": "success"}, status=status.HTTP_200_OK)

        # Если есть ошибки валидации, возвращаем их
        errors = dict(serializer.errors)
        error_message = errors.get("title", errors.get("description", ["Ошибка валидации"]))[0]
        return Response(
            {"status": "error", "message": error_message},
            status=status.HTTP_400_BAD_REQUEST,
        )


class BookmarkDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    """Эндпоинт для удаления закладки."""

    model = Bookmark
    context_object_name = "bookmark"
    success_url = reverse_lazy("daily:task_list")
    success_message = "Закладка успешно удалена"

    def get_object(self, queryset=None):
        """
        Самостоятельно получаем объект из POST-параметров,
        минуя стандартные проверки DeleteView на наличие PK в URL.
        """
        # Считываем id из скрытого поля name="bookmark_id"
        bookmark_id = self.request.POST.get("bookmark_id")

        try:
            # Извлекаем объект напрямую по полученному ID
            obj = Bookmark.objects.get(id=bookmark_id)
        except Bookmark.DoesNotExist:
            # Если объект не найден, отдаем стандартную 404 ошибку Django
            raise Http404("Закладка не найдена.")

        # Проверяем права владельца
        if obj.owner != self.request.user:
            raise PermissionDenied("Вы не можете удалить чужую закладку.")

        return obj


# ========================= Эндпоинты для работы с API ===============================================


class TaskListAPIView(ListAPIView):
    """API-представление для получения списка задач в формате JSON.
    Интегрирует логику фильтрации `TaskService` с сериализаторами DRF. Возвращает
    клиенту не только массив задач, но и метаданные интерфейса (список закладок,
    активную закладку и примененные фильтры) в одном ответе.
    """

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication]
    pagination_class = TaskListAPIViewPagination

    # Явно задаем queryset, чтобы заглушить предупреждение Swagger в консоли
    queryset = Task.objects.none()

    @extend_schema(
        summary="Получение списка задач с метаданными",
        description="Возвращает массив задач текущего пользователя с учетом пагинации, а также метаданные фильтров и закладок.",
        responses={
            200: inline_serializer(
                name="TaskListWithMetaResponse",
                fields={
                    "meta": inline_serializer(
                        name="TaskListMeta",
                        fields={
                            "current_filters": inline_serializer(
                                name="TaskListFilters",
                                fields={
                                    "title": serializers.CharField(allow_null=True),
                                    "flag": serializers.CharField(allow_null=True),
                                    "sort": serializers.CharField(allow_null=True),
                                },
                            ),
                            "bookmarks": BookmarkSerializer(many=True),
                            "current_bookmark": BookmarkSerializer(allow_null=True),
                        },
                    ),
                    "tasks": TaskSerializer(many=True),
                },
            )
        },
    )
    def list(self, request, *args, **kwargs):
        """Формирует структурированный JSON-ответ со списком задач и метаданных."""
        # Логирование для диагностики
        logger.info(f"[API] Запрос списка задач. User: {request.user}, Authenticated: {request.user.is_authenticated}")
        logger.info(f"[API] Query params: {request.query_params}")

        # Получаем весь готовый контекст из сервиса
        service_context = TaskService.get_task_list_context(
            user=request.user, params=request.query_params
        )

        logger.info(f"[API] Получено задач в контексте: {service_context['tasks'].count()}")

        # Сериализуем список задач с поддержкой пагинации
        queryset = service_context["tasks"]
        page = self.paginate_queryset(queryset)
        if page is not None:
            tasks_data = self.get_serializer(page, many=True).data
        else:
            tasks_data = self.get_serializer(queryset, many=True).data

        # Сериализуем метаданные закладок
        bookmarks_serialized = BookmarkSerializer(
            service_context["bookmarks"], many=True
        ).data
        current_bookmark_serialized = (
            BookmarkSerializer(service_context["current_bookmark"]).data
            if service_context["current_bookmark"]
            else None
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


class BookmarkUpdateExternalApiView(RetrieveUpdateDestroyAPIView):
    """
    API-представление для просмотра(GET), обновления(PUT / PATCH) и удаления(DELETE) конкретной закладки.
    Аутентификация через JWT-токен в заголовке Authorization.
    """

    serializer_class = BookmarkUpdateSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [
        JWTAuthentication
    ]  # Защита токеном, а не сессией браузера

    def get_queryset(self):
        return Bookmark.objects.filter(owner=self.request.user)


class BookmarkListCreateAPIView(ListCreateAPIView):
    """
    API-представление для создания новой закладки
    или вывода списка закладок.
    """

    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Фильтруем список под текущего пользователя."""
        # ЗАЩИТА ДЛЯ SWAGGER: если схему генерирует робот, отдаем пустой кверисет
        if getattr(self, "swagger_fake_view", False) or "spectacular" in str(
            self.request
        ):
            return Bookmark.objects.none()
        return Bookmark.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        """Автоматически сохраняем авторизованного пользователя в поле owner."""
        serializer.save(owner=self.request.user)
