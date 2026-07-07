import json
from django.http import JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Task
from .forms import TaskForm


class TaskListView(ListView):
    model = Task
    template_name = 'daily/task_list.html'
    context_object_name = 'tasks'  # Переменная, которая пойдет в HTML-шаблон

    def get_queryset(self):
        # Получаем базовый набор всех записей из PostgreSQL
        queryset = super().get_queryset()
        
        # Фильтрация по наименованию контрагента
        name_query = self.request.GET.get('name', '').strip()
        if name_query:
            queryset = queryset.filter(name__icontains=name_query)
            
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
        # Метод собирает переменные для полей формы, чтобы они не очищались после отправки
        context = super().get_context_data(**kwargs)
        context['current_name'] = self.request.GET.get('name', '').strip()
        context['current_flag'] = self.request.GET.get('flag', '')
        context['current_sort'] = self.request.GET.get('sort', '')
        
        # Собираем уникальные, непустые имена компаний в алфавитном порядке
        context['unique_companies'] = Task.objects.exclude(name="").values_list('name', flat=True).distinct().order_by('name')
        
        return context


class TaskCreateView(CreateView):
    model = Task
    context_object_name = "task"
    form_class = TaskForm
    success_url = reverse_lazy("daily:task_list")
    success_message = "Новыя задача успешно создана!"


class TaskUpdateApiView(UpdateView):
    model = Task
    # Указываем поля, которые РАЗРЕШЕНО редактировать пользователю
    fields = ['name', 'comment', 'reminder_at']

    def _get_json_data(self):
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
        data = self._get_json_data()
        task_id = data.get('id')
        try:
            return self.get_queryset().get(id=task_id)
        except (self.model.DoesNotExist, ValueError):
            return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['data'] = self._get_json_data()
        return kwargs

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            return JsonResponse({'status': 'error', 'message': 'Задача не найдена'}, status=404)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
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
        return JsonResponse({
            'status': 'error',
            'message': 'Ошибка валидации полей',
            'errors': form.errors.get_json_data()
        }, status=400)


class TaskDeleteApiView(DeleteView):
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

