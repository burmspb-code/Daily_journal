import json
from django.http import JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from .models import Task, Bookmark
from .forms import TaskForm, BookmarkForm


class TaskListView(ListView):
    """Контроллек для вывода списка задач."""
    model = Task
    template_name = 'daily/task_list.html'
    context_object_name = 'tasks'  # Переменная, которая пойдет в HTML-шаблон

    def get_queryset(self):
        # Получаем базовый набор всех записей из PostgreSQL
        queryset = super().get_queryset()

        # Фильтрация задач по текущей закладке (чтобы не валить всё в кучу)
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

        # Фильтрация по наименованию задачи
        name_query = self.request.GET.get('name', '').strip()
        if name_query:
            queryset = queryset.filter(name=name_query)

        # Фильтрация по флагу управления
        flag_query = self.request.GET.get('flag', '')
        if flag_query != '':
            queryset = queryset.filter(status_flag=int(flag_query))

        # Сортировка по времени создания или по умолчанию (PK)
        sort_query = self.request.GET.get('sort', '')
        if sort_query == 'newest':
            queryset = queryset.order_by('-created_at', '-id')
        elif sort_query == 'oldest':
            queryset = queryset.order_by('created_at', 'id')
        else:
            queryset = queryset.order_by('id')  # Наш сброс — сортировка по порядку PK

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
        context['current_name'] = self.request.GET.get('name', '').strip()
        context['current_flag'] = self.request.GET.get('flag', '')
        context['current_sort'] = self.request.GET.get('sort', '')

        # 2. РАБОТА С ЗАКЛАДКАМИ
        # Вытягиваем абсолютно все закладки для рендеринга пунктов верхнего меню
        all_bookmarks = Bookmark.objects.all()
        context['bookmarks'] = all_bookmarks

        # Извлекаем ID выбранной закладки из GET-параметров URL (?bookmark=ID)
        bookmark_id = self.request.GET.get('bookmark')
        if bookmark_id:
            # Если ID передан в URL, находим соответствующий объект из общего списка
            context['current_bookmark'] = all_bookmarks.filter(id=bookmark_id).first()
        else:
            # Если параметр отсутствует (первый вход на страницу), дефолтом открываем самую первую закладку
            context['current_bookmark'] = all_bookmarks.order_by('id').first()

        # Извлекаем определенную закладку в локальную переменную для удобства фильтрации ниже
        current_bookmark = context['current_bookmark']

        # 3. ДИНАМИЧЕСКИЙ СБОР ЗАДАЧ ДЛЯ ФИЛЬТРА В ТАБЛИЦЕ (В ПОРЯДКЕ ОТОБРАЖЕНИЯ)
        if current_bookmark:
            # Берём отсортированный набор задач из таблицы и отсекаем пустые имена
            # Передаём объекты целиком, чтобы в шаблоне были доступны и id, и name
            context['unique_companies'] = self.get_queryset().exclude(name="")
        else:
            context['unique_companies'] = []

        return context


class TaskCreateView(CreateView):
    """Контроллер создания задачи с гарантированным динамическим редиректом."""
    model = Task
    context_object_name = "task"
    form_class = TaskForm

    def dispatch(self, request, *args, **kwargs):
        """Жесткая проверка: если закладок в базе нет, не выводим форму."""
        if not Bookmark.objects.exists():
            return redirect('daily:task_list')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """Передаем ID текущей активной закладки в форму."""
        initial = super().get_initial()
        bookmark_id = self.request.GET.get('bookmark')

        if bookmark_id:
            initial['bookmark'] = bookmark_id
        else:
            first_bookmark = Bookmark.objects.order_by('id').first()
            if first_bookmark:
                initial['bookmark'] = first_bookmark.id

        return initial

    def get_success_url(self):
        """
        Защищенный метод динамического редиректа.
        Гарантирует возврат пользователя на текущую открытую вкладку.
        """
        # Шаг 1: Пробуем вытащить ID закладки напрямую из адресной строки GET (?bookmark=2)
        bookmark_id = self.request.GET.get('bookmark')

        # Шаг 2: Если в GET пусто (маловероятно), берем ID из только что сохраненного объекта задачи
        if not bookmark_id and self.object and self.object.bookmark:
            bookmark_id = self.object.bookmark.id

        # Шаг 3: Если ID успешно найден, формируем точный кумулятивный URL
        if bookmark_id:
            return f"{reverse('daily:task_list')}?bookmark={bookmark_id}"

        # Шаг 4: Жесткий "план Б" — если закладка не определилась, возвращаем на базовый список без падения сервера
        return reverse("daily:task_list")


class TaskUpdateApiView(UpdateView):
    """Контроллер редактирования задачи."""
    model = Task
    # Указываем поля, которые РАЗРЕШЕНО редактировать пользователю
    fields = ['name', 'comment', 'reminder_at']

    def _get_json_data(self):
        """
            Парсит JSON из тела запроса, кэширует результат и адаптирует формат дат HTML5.

            В случае некорректного JSON возвращает пустой словарь.
        """
        if not hasattr(self, 'json_data'):
            try:
                self.json_data = json.loads(self.request.body)
                # Корректируем формат даты из HTML5 (YYYY-MM-DDTHH:mm) в формат Django (YYYY-MM-DD HH:mm)
                if self.json_data.get('reminder_at'):
                    self.json_data['reminder_at'] = self.json_data['reminder_at'].replace('T', ' ')
            except (json.JSONDecodeError, TypeError):
                self.json_data = {}
        return self.json_data

    def get_object(self, queryset=None):
        """
            Извлекает ID задачи из JSON-данных запроса и находит объект в базе данных.

            В случае отсутствия объекта или передачи некорректного ID
            безопасно возвращает None вместо вызова исключения Http404.
        """
        data = self._get_json_data()
        task_id = data.get('id')
        try:
            return self.get_queryset().get(id=task_id)
        except (self.model.DoesNotExist, ValueError):
            return None

    def get_form_kwargs(self):
        """
            Внедряет данные из JSON-тела запроса в аргументы для инициализации формы.

            Переопределяет стандартный источник данных (из request.POST на JSON-словарь)
            для обеспечения корректной работы формы с AJAX/JSON-запросами.
        """
        kwargs = super().get_form_kwargs()
        kwargs['data'] = self._get_json_data()
        return kwargs

    def post(self, request, *args, **kwargs):
        """
            Проверяет существование объекта перед обработкой формы.

            Если объект не найден, возвращает JSON-ответ со статусом 404.
            В противном случае передает управление стандартному обработчику POST-запросов.
        """
        self.object = self.get_object()
        if self.object is None:
            return JsonResponse({'status': 'error', 'message': 'Задача не найдена'}, status=404)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Сохраняет валидную форму и возвращает обновленный статус объекта в формате JSON."""
        # Сохраняем измененные name, comment и reminder_at
        self.object = form.save()

        # Перезагружаем объект из базы, чтобы сработал ваш автоматический расчет флага (если он прописан в методе save() модели)
        self.object.refresh_from_db()

        # Возвращаем статус успеха и автоматически пересчитанный флаг обратно на фронтенд
        return JsonResponse({
            'status': 'success',
            'new_flag': self.object.status_flag  # Передаем обновленный статус для динамической перекраски
        })

    def form_invalid(self, form):
        """Возвращает JSON-ответ с ошибками валидации формы и HTTP-статусом 400."""
        return JsonResponse({
            'status': 'error',
            'message': 'Ошибка валидации полей',
            'errors': form.errors.get_json_data()
        }, status=400)


class TaskDeleteApiView(DeleteView):
    """Контроллер удаления задачи."""
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


class BookmarkCreateView(CreateView):
    """Контроллер создания новой закладки."""
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
