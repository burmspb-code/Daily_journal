import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import ListView, CreateView, DeleteView

from .forms import TaskEditForm
from .forms import TaskForm, BookmarkForm
from .models import Bookmark
from .models import Task

logger = logging.getLogger(__name__)


class TaskListView(LoginRequiredMixin, ListView):
    """Представление для вывода списка задач на веб-страницу."""

    model = Task
    template_name = "daily/task_list.html"
    context_object_name = "tasks"  # Переменная, которая пойдет в HTML-шаблон

    def get_queryset(self):
        """
        Возвращает отфильтрованный и отсортированный набор задач текущего пользователя.
        """
        user = self.request.user

        # select_related делает SQL JOIN, предотвращая проблему N+1
        queryset = Task.objects.filter(owner=user).select_related("bookmark", "owner")

        # 1. Фильтрация по текущей закладке
        bookmark_id = self.request.GET.get("bookmark")
        if bookmark_id:
            queryset = queryset.filter(bookmark_id=bookmark_id)
        else:
            # Ищем первую закладку ИМЕННО ЭТОГО пользователя
            first_bookmark = Bookmark.objects.filter(owner=user).order_by("id").first()
            if first_bookmark:
                queryset = queryset.filter(bookmark=first_bookmark)
            else:
                return Task.objects.none()

        # 2. Фильтрация по наименованию (лучше использовать __icontains для поиска по подстроке)
        name_query = self.request.GET.get("title", "").strip()
        if name_query:
            queryset = queryset.filter(title__icontains=name_query)

        # 3. Безопасная фильтрация по флагу управления
        flag_query = self.request.GET.get("flag", "").strip()
        if flag_query.isdigit():  # Защита от ValueError (HTTP 500)
            queryset = queryset.filter(status_flag=int(flag_query))

        # 4. Сортировка записей
        sort_mapping = {
            "newest": ["-created_at", "-id"],
            "oldest": ["created_at", "id"],
            "name_asc": ["title"],
            "name_desc": ["-title"],
        }

        sort_query = self.request.GET.get("sort", "").strip()
        order_by_fields = sort_mapping.get(sort_query, ["id"])

        return queryset.order_by(*order_by_fields)

    def get_context_data(self, **kwargs):
        """
        Формирует контекст данных для передачи в HTML-шаблон 'task_list.html'.

        Обеспечивает:
        1. Сохранение состояний фильтров и сортировки для удержания активных элементов в UI.
        2. Извлечение списка всех закладок текущего пользователя для навигационного меню.
        3. Определение текущей активной закладки.
        """
        # Получаем базовый контекст от родительского класса ListView
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 1. СОХРАНЕНИЕ ТЕКУЩИХ ФИЛЬТРОВ И СОРТИРОВКИ (для удержания состояния в UI)
        context["current_title"] = self.request.GET.get("title", "").strip()
        context["current_flag"] = self.request.GET.get("flag", "").strip()
        context["current_sort"] = self.request.GET.get("sort", "").strip()

        # 2. РАБОТА С ЗАКЛАДКАМИ
        # Вытягиваем закладки только текущего пользователя и сразу сортируем их по ID
        bookmarks_owner = Bookmark.objects.filter(owner=user).order_by("id")
        context["bookmarks"] = bookmarks_owner

        # Извлекаем ID выбранной закладки из GET-параметров URL (?bookmark=ID)
        bookmark_id = self.request.GET.get("bookmark", "").strip()

        if bookmark_id.isdigit():
            # Если ID передан и это число — находим соответствующий объект
            context["current_bookmark"] = bookmarks_owner.filter(
                id=int(bookmark_id)
            ).first()
        else:
            # Если параметр отсутствует или некорректен — берем самую первую закладку
            context["current_bookmark"] = bookmarks_owner.first()

        # Передаем форму редактирования под уникальным именем 'edit_form'
        context["edit_form"] = TaskEditForm(user=self.request.user)

        return context


class TaskCreateApiView(LoginRequiredMixin, View):
    """
    Самостоятельное API-представление для быстрого инлайн-создания задачи.

    Принимает POST-запрос с JSON-телом, валидирует данные через TaskForm
    и возвращает JSON с ID новой задачи для мгновенного добавления в таблицу.
    """

    def post(self, request, *args, **kwargs):
        # 1. Проверяем наличие закладок у пользователя перед созданием задачи
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

        # 2. Читаем и валидируем JSON из тела запроса
        try:
            json_data = json.loads(request.body)
        except json.JSONDecodeError, TypeError:
            return JsonResponse(
                {"status": "error", "message": "Некорректный JSON-формат"}, status=400
            )

        # 3. Собираем данные для формы. Если закладка не передана, берем первую доступную
        bookmark_id = json_data.get("bookmark_id") or first_bookmark.id

        form_data = {
            "title": str(json_data.get("title", "")).strip(),
            "bookmark": bookmark_id,
        }

        # 4. Инициализируем форму (передаем user для внутренней фильтрации querysets)
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

        # 5. Обработка ошибок валидации формы Django
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
