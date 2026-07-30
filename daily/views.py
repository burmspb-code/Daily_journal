import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import localtime
from django.views import View
from django.views.generic import ListView, CreateView, DeleteView

from .forms import TaskForm, BookmarkForm
from .models import Bookmark
from .models import Task

logger = logging.getLogger(__name__)


class TaskListView(LoginRequiredMixin, ListView):
    """Представление для вывода списка задач на веб-страницу."""
    model = Task
    template_name = 'daily/task_list.html'
    context_object_name = 'tasks'  # Переменная, которая пойдет в HTML-шаблон

    def get_queryset(self):
        """
        Возвращает отфильтрованный и отсортированный набор задач текущего пользователя.
        """
        user = self.request.user

        # select_related делает SQL JOIN, предотвращая проблему N+1
        queryset = Task.objects.filter(owner=user).select_related('bookmark', 'owner')

        # 1. Фильтрация по текущей закладке
        bookmark_id = self.request.GET.get('bookmark')
        if bookmark_id:
            queryset = queryset.filter(bookmark_id=bookmark_id)
        else:
            # Ищем первую закладку ИМЕННО ЭТОГО пользователя
            first_bookmark = Bookmark.objects.filter(owner=user).order_by('id').first()
            if first_bookmark:
                queryset = queryset.filter(bookmark=first_bookmark)
            else:
                return Task.objects.none()

        # 2. Фильтрация по наименованию (лучше использовать __icontains для поиска по подстроке)
        name_query = self.request.GET.get('title', '').strip()
        if name_query:
            queryset = queryset.filter(title__icontains=name_query)

        # 3. Безопасная фильтрация по флагу управления
        flag_query = self.request.GET.get('flag', '').strip()
        if flag_query.isdigit():  # Защита от ValueError (HTTP 500)
            queryset = queryset.filter(status_flag=int(flag_query))

        # 4. Сортировка записей
        sort_mapping = {
            'newest': ['-created_at', '-id'],
            'oldest': ['created_at', 'id'],
            'name_asc': ['title'],
            'name_desc': ['-title'],
        }

        sort_query = self.request.GET.get('sort', '').strip()
        order_by_fields = sort_mapping.get(sort_query, ['id'])

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
        context['current_title'] = self.request.GET.get('title', '').strip()
        context['current_flag'] = self.request.GET.get('flag', '').strip()
        context['current_sort'] = self.request.GET.get('sort', '').strip()

        # 2. РАБОТА С ЗАКЛАДКАМИ
        # Вытягиваем закладки только текущего пользователя и сразу сортируем их по ID
        bookmarks_owner = Bookmark.objects.filter(owner=user).order_by('id')
        context['bookmarks'] = bookmarks_owner

        # Извлекаем ID выбранной закладки из GET-параметров URL (?bookmark=ID)
        bookmark_id = self.request.GET.get('bookmark', '').strip()

        if bookmark_id.isdigit():
            # Если ID передан и это число — находим соответствующий объект
            context['current_bookmark'] = bookmarks_owner.filter(id=int(bookmark_id)).first()
        else:
            # Если параметр отсутствует или некорректен — берем самую первую закладку
            context['current_bookmark'] = bookmarks_owner.first()

        return context


class TaskCreateView(LoginRequiredMixin, CreateView):
    """
    Представление для создания задачи через AJAX/HTMX.

    Автоматически привязывает авторизованного пользователя к задаче
    и возвращает JSON-ответ для динамического перенаправления на фронтенде.
    """
    model = Task
    context_object_name = "task"
    form_class = TaskForm

    first_bookmark = None

    def dispatch(self, request, *args, **kwargs):
        """Жесткая проверка: если у пользователя нет личных закладок, блокируем форму."""
        # ИСПРАВЛЕНО: используем аргумент request вместо self.request
        self.first_bookmark = Bookmark.objects.filter(owner=request.user).order_by('id').first()

        if not self.first_bookmark:
            return redirect('daily:task_list')

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """Передаем ID текущей активной закладки в форму с проверкой прав доступа."""
        initial = super().get_initial()
        bookmark_id = self.request.GET.get('bookmark')

        if bookmark_id:
            # ЗАЩИТА: Проверяем, существует ли такая закладка ИМЕННО у этого пользователя
            user_bookmark_exists = Bookmark.objects.filter(id=bookmark_id, owner=self.request.user).exists()
            if user_bookmark_exists:
                initial['bookmark'] = bookmark_id
            else:
                # Если ID чужой или поддельный — принудительно ставим его личную закладку
                initial['bookmark'] = self.first_bookmark.id
        elif self.first_bookmark:
            initial['bookmark'] = self.first_bookmark.id

        return initial

    def get_success_url(self):
        """Формирует точный URL-адрес для возврата на текущую открытую вкладку."""
        bookmark_id = self.request.GET.get('bookmark')

        if not bookmark_id and self.object and self.object.bookmark:
            bookmark_id = self.object.bookmark.id

        if bookmark_id:
            return f"{reverse('daily:task_list')}?bookmark={bookmark_id}"

        return reverse("daily:task_list")

    def form_valid(self, form):
        """
        Обработка успешной валидации формы.

        Привязывает текущего пользователя к задаче и возвращает JSON-ответ
        вместо классического серверного редиректа.
        """
        # 1. Привязываем автора
        form.instance.owner = self.request.user

        # 2. Возвращаем стандартный метод (он сам сделает обычный редирект)
        return super().form_valid(form)

    def get_form_kwargs(self):
        """Передает объект текущего пользователя в аргументы инициализации формы."""
        kwargs = super().get_form_kwargs()
        # Внедряем текущего авторизованного пользователя в словарь kwargs
        kwargs['user'] = self.request.user
        return kwargs


class TaskCreateApiView(TaskCreateView):
    """
    API-представление для быстрого инлайн-создания задачи.
    Наследует всю логику валидации, защиты и привязки owner из TaskCreateView,
    но возвращает JSON вместо перезагрузки страницы.
    """

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Некорректный JSON-формат'}, status=400)

        # 1. Формируем чистые данные для формы из JSON
        form_data = {
            'title': data.get('title', '').strip(),
            'bookmark': data.get('bookmark_id')
        }

        # 2. Получаем базовые аргументы формы (там сидят 'user', 'initial' и пустой 'data')
        kwargs_data = self.get_form_kwargs()

        # 3. ИСПРАВЛЕНО: Принудительно заменяем пустой request.POST на наш form_data из JSON
        kwargs_data['data'] = form_data

        # 4. Инициализируем форму без конфликтов аргументов
        form = self.get_form_class()(**kwargs_data)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Вызывается, если название заполнено и закладка принадлежит пользователю."""
        form.instance.owner = self.request.user
        self.object = form.save()  # Сохраняем задачу в базу данных

        # Форматируем дату в локальном часовом поясе пользователя
        local_created_at = localtime(self.object.created_at)
        formatted_date = local_created_at.strftime('%d.%m.%Y %H:%M')

        return JsonResponse({
            'status': 'success',
            'id': self.object.id,
            'created_at': formatted_date
        })

    def form_invalid(self, form):
        """Вызывается в случае провала валидации (например, пустой title)."""
        # Собираем все ошибки формы в одну строку для вывода в alert фронтенда
        errors = ", ".join([f"{v[0]}" for k, v in form.errors.items()])
        return JsonResponse({
            'status': 'error',
            'message': errors or 'Ошибка валидации формы'
        }, status=400)


class TaskUpdateApiView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Невалидный JSON-формат'}, status=400)

        task_id = data.get('id')
        try:
            task = Task.objects.get(id=task_id, owner=request.user)
        except (Task.DoesNotExist, ValueError):
            return JsonResponse({'status': 'error', 'message': 'Задача не найдена'}, status=404)

        # 3. Обновляем название задачи
        if 'title' in data:
            title_value = data['title'].strip()
            if not title_value:
                return JsonResponse({'status': 'error', 'message': 'Наименование не может быть пустым'}, status=400)
            task.title = title_value

        # Обновляем комментарий
        if 'comment' in data:
            task.comment = data['comment'].strip()

        # 4. Обрабатываем дату напоминания (ИСПРАВЛЕНО И ЗАЩИЩЕНО)
        formatted_reminder_at = "*"

        if 'remind_at' in data:  # Ключ от JS календаря
            reminder_str = data['remind_at']
            if reminder_str:
                # Стандартизируем строку для парсера Django
                normalized_date = reminder_str.replace(' ', 'T')
                parsed_date = parse_datetime(normalized_date)

                if parsed_date:
                    # Делаем дату осведомленной о часовом поясе вашего Django-проекта
                    if timezone.is_naive(parsed_date):
                        parsed_date = timezone.make_aware(parsed_date, timezone.get_current_timezone())
                    task.reminder_at = parsed_date

                    # Форматируем для вывода обратно в ячейку таблицы
                    formatted_reminder_at = timezone.localtime(task.reminder_at).strftime('%d.%m.%Y %H:%M')
                else:
                    return JsonResponse({'status': 'error', 'message': 'Неверный формат даты и времени'}, status=400)
            else:
                task.reminder_at = None

        # 5. Авторасчет статуса (просрочено/в работе)
        if task.reminder_at and task.reminder_at < timezone.now():
            task.status_flag = 3
        else:
            if getattr(task, 'status_flag', None) == 3:
                task.status_flag = 0

        # 6. Валидация и безопасное сохранение
        try:
            task.full_clean()  # Если тут упадет, мы поймаем ошибку ниже, а не выбросим 500
            task.save()
        except ValidationError as ve:
            # Собираем понятные ошибки валидации полей модели
            error_msg = ", ".join([f"{k}: {v[0]}" for k, v in ve.message_dict.items()])
            return JsonResponse({'status': 'error', 'message': f'Ошибка валидации: {error_msg}'}, status=400)
        except Exception as e:
            # Логируем критическую ошибку в консоль PyCharm, чтобы вы её видели
            print(f"--- КРИТИЧЕСКАЯ ОШИБКА БАЗЫ ДАННЫХ: {str(e)} ---")
            return JsonResponse({'status': 'error', 'message': f'Ошибка базы данных: {str(e)}'}, status=400)

        return JsonResponse({
            'status': 'success',
            'new_flag': getattr(task, 'status_flag', 0),
            'remind_at_display': formatted_reminder_at
        })


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
            task_ids = data.get('task_ids', [])

            if not task_ids:
                return JsonResponse({'status': 'error', 'message': 'Не выбрано ни одной задачи'}, status=400)

            # Выполняем удаление через queryset
            queryset = self.get_queryset().filter(id__in=task_ids)
            deleted_count, _ = queryset.delete()

            return JsonResponse({
                'status': 'success',
                'message': f'Успешно удалено задач: {deleted_count}'
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class BookmarkCreateView(LoginRequiredMixin, CreateView):
    """
    Представление для создания новой закладки.

    Обрабатывает AJAX-запросы и возвращает результат в формате JSON.
    """
    model = Bookmark
    form_class = BookmarkForm
    template_name = 'daily/bookmark_form.html'  # Укажите путь к вашему HTML-шаблону формы
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

    Принимает JSON с идентификатором и новым названием, обновляя
    исключительно поле 'title' в обход полной формы.
    """

    def post(self, request, *args, **kwargs):
        try:
            # 1. Читаем JSON из тела AJAX-запроса
            data = json.loads(request.body)
            bookmark_id = data.get('id')
            # Исправили имя переменной для соответствия полю модели
            new_title = data.get('title', '').strip()

            # 2. Быстрая проверка данных
            if not bookmark_id:
                return JsonResponse({'error': 'ID закладки не передан'}, status=400)
            if not new_title:
                return JsonResponse({'error': 'Название не может быть пустым'}, status=400)

            # 3. Находим закладку в базе данных с проверкой владельца (Безопасность!)
            bookmark = Bookmark.objects.get(pk=bookmark_id, owner=request.user)

            # 4. Обновляем только название и сохраняем
            bookmark.title = new_title
            bookmark.save(update_fields=['title'])  # Обновляет исключительно title в БД

            return JsonResponse({'status': 'success'}, status=200)

        except Bookmark.DoesNotExist:
            return JsonResponse({'error': 'Закладка не найдена или доступ запрещен'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Некорректный формат JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Внутренняя ошибка сервера: {str(e)}'}, status=500)
