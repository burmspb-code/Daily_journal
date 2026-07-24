import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .forms import TaskForm, BookmarkForm
from .models import Task, Bookmark


class TaskListView(LoginRequiredMixin, ListView):
    """Представление для вывода списка задач на веб-страницу."""
    model = Task
    template_name = 'daily/task_list.html'
    context_object_name = 'tasks'  # Переменная, которая пойдет в HTML-шаблон

    def get_queryset(self):
        """Возвращает отфильтрованный и отсортированный набор задач.

        Выполняет многоступенчатую обработку выборки из базы данных PostgreSQL
        на основе GET-параметров запроса:
        1. Изолирует задачи, принадлежащие только текущей активной закладке.
        2. Фильтрует записи по точному совпадению наименования (если выбрано).
        3. Фильтрует записи по цифровому флагу статуса управления.
        4. Применяет запрошенный тип сортировки (по хронологии, алфавиту или ID).

        Returns:
            QuerySet: Отфильтрованный и упорядоченный набор объектов Task.
        """
        # Выбираем задачи только текущего пользователя
        queryset = Task.objects.filter(owner=self.request.user)

        # 1. Фильтрация задач по текущей закладке (чтобы не валить всё в кучу)
        bookmark_id = self.request.GET.get('bookmark')
        if bookmark_id:
            queryset = queryset.filter(bookmark_id=bookmark_id)
        else:
            # Если старт страницы, берем задачи первой закладки (если она есть)
            first_bookmark = Bookmark.objects.order_by('id').first()
            if first_bookmark:
                queryset = queryset.filter(bookmark=first_bookmark)
            else:
                queryset = queryset.none()  # Если закладок нет вообще — возвращаем пустоту

        # 2. Фильтрация по наименованию задачи
        name_query = self.request.GET.get('title', '').strip()
        if name_query:
            queryset = queryset.filter(title=name_query)

        # 3. Фильтрация по флагу управления
        flag_query = self.request.GET.get('flag', '')
        if flag_query != '':
            queryset = queryset.filter(status_flag=int(flag_query))

        # 4. Многовариантная сортировка записей
        sort_query = self.request.GET.get('sort', '').strip()

        if sort_query == 'newest':
            queryset = queryset.order_by('-created_at', '-id')
        elif sort_query == 'oldest':
            queryset = queryset.order_by('created_at', 'id')
        elif sort_query == 'name_asc':
            # Алфавитный порядок (А -> Я)
            queryset = queryset.order_by('title')
        elif sort_query == 'name_desc':
            # Обратный алфавитный порядок (Я -> А)
            queryset = queryset.order_by('-title')
        else:
            # Наш сброс («Исходное состояние») — сортировка по порядку PK
            queryset = queryset.order_by('id')

        return queryset

    def get_context_data(self, **kwargs):
        """
        Формирует контекст данных для передачи в HTML-шаблон 'task_list.html'.

        Обеспечивает:
        1. Сохранение состояний фильтров и сортировки в формах ввода после перезагрузки страницы.
        2. Извлечение списка всех закладок для построения навигационного меню.
        3. Определение текущей активной закладки на основе GET-параметров.
        4. Изолированный сбор уникальных имён задач, принадлежащих исключительно
           текущей активной закладке (предотвращает появление чужих фильтров).
        """
        # Получаем базовый контекст от родительского класса ListView
        context = super().get_context_data(**kwargs)

        # 1. СОХРАНЕНИЕ ТЕКУЩИХ ФИЛЬТРОВ И СОРТИРОВКИ (для удержания состояния в UI)
        # Извлекаем параметры из адресной строки, чтобы подсветить активные кнопки
        context['current_title'] = self.request.GET.get('title', '').strip()
        context['current_flag'] = self.request.GET.get('flag', '')
        context['current_sort'] = self.request.GET.get('sort', '')

        # 2. РАБОТА С ЗАКЛАДКАМИ
        # Вытягиваем абсолютно все закладки для рендеринга пунктов верхнего меню
        bookmarks_owner = Bookmark.objects.filter(owner=self.request.user)
        context['bookmarks'] = bookmarks_owner

        # Извлекаем ID выбранной закладки из GET-параметров URL (?bookmark=ID)
        bookmark_id = self.request.GET.get('bookmark')
        if bookmark_id:
            # Если ID передан в URL, находим соответствующий объект из общего списка
            context['current_bookmark'] = bookmarks_owner.filter(id=bookmark_id).first()
        else:
            # Если параметр отсутствует (первый вход на страницу), дефолтом открываем самую первую закладку
            context['current_bookmark'] = bookmarks_owner.order_by('id').first()

        # Извлекаем определенную закладку в локальную переменную для удобства фильтрации ниже
        current_bookmark = context['current_bookmark']

        # 3. ДИНАМИЧЕСКИЙ СБОР ЗАДАЧ ДЛЯ ФИЛЬТРА В ТАБЛИЦЕ (В ПОРЯДКЕ ОТОБРАЖЕНИЯ)
        if current_bookmark:
            # Выбираем только id и title, убираем дубликаты. База данных отработает мгновенно!
            context['unique_companies'] = (
                self.get_queryset()
                .exclude(title="")
                .values('id', 'title')
                .distinct()
            )
        else:
            context['unique_companies'] = []

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


class TaskUpdateApiView(LoginRequiredMixin, UpdateView):
    """
    Представление для редактирования задачи.
    Обеспечивает безопасность данных и принимает изменения в формате JSON.
    """
    model = Task
    fields = ['title', 'comment', 'reminder_at']

    def get_queryset(self):
        """Блокирует доступ к чужим задачам на уровне SQL-запроса."""
        return super().get_queryset().filter(owner=self.request.user)

    def _get_json_data(self):
        """Парсит JSON из тела запроса, кэширует результат и адаптирует формат дат HTML5."""
        if not hasattr(self, 'json_data'):
            try:
                self.json_data = json.loads(self.request.body)
                if self.json_data.get('reminder_at'):
                    self.json_data['reminder_at'] = self.json_data['reminder_at'].replace('T', ' ')
            except (json.JSONDecodeError, TypeError):
                self.json_data = {}
        return self.json_data

    def get_object(self, queryset=None):
        """
        Извлекает ID задачи и находит объект в базе данных.
        Благодаря переопределенному get_queryset(), чужие ID вернут None.
        """
        data = self._get_json_data()
        task_id = data.get('id')
        try:
            return self.get_queryset().get(id=task_id)
        except (self.model.DoesNotExist, ValueError):
            return None

    def get_form_kwargs(self):
        """Внедряет данные JSON и текущего пользователя в аргументы формы."""
        kwargs = super().get_form_kwargs()
        kwargs['data'] = self._get_json_data()
        # ИСПРАВЛЕНО (Лучшая практика): Передаем пользователя в форму
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        """Проверяет существование объекта и прав на него перед обработкой."""
        self.object = self.get_object()
        if self.object is None:
            # Теперь здесь вернется 404 и при попытке взлома чужой записи
            return JsonResponse({'status': 'error', 'message': 'Задача не найдена или доступ запрещен'}, status=404)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Сохраняет валидную форму и возвращает обновленный статус объекта в формате JSON."""
        self.object = form.save()
        self.object.refresh_from_db()

        return JsonResponse({
            'status': 'success',
            'new_flag': self.object.status_flag
        })

    def form_invalid(self, form):
        """Возвращает JSON-ответ с ошибками валидации формы и HTTP-статусом 400."""
        return JsonResponse({
            'status': 'error',
            'message': 'Ошибка валидации полей',
            'errors': form.errors.get_json_data()
        }, status=400)


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
            task_ids = data.get('ids', [])

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
