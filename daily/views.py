import json
from django.http import JsonResponse
from django.views.generic import ListView, CreateView, UpdateView
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
        return context
    
class TaskCreateView(CreateView):
    model = Task
    context_object_name = "task"
    form_class = TaskForm
    success_url = reverse_lazy("daily:task_list")
    success_message = "Новыя задача успешно создана!"


class TaskUpdateApiView(UpdateView):
    model = Task
    # Указываем поля модели, которые разрешено редактировать через форму
    fields = ['name', 'comment'] 

    def get_form_kwargs(self):
        """
        Переопределяем сбор данных для формы.
        Вместо стандартного request.POST читаем данные из JSON-тела Fetch-запроса.
        """
        kwargs = super().get_form_kwargs()
        try:
            # Читаем JSON-пакет из тела запроса
            data = json.loads(self.request.body)
            
            # Подменяем стандартный QueryDict на наш словарь из JSON
            kwargs['data'] = data
        except Exception:
            kwargs['data'] = {}
        return kwargs

    def get_object(self, queryset=None):
        """
        Переопределяем поиск объекта.
        Обычно UpdateView ищет pk в URL-адресе, но у нас pk прилетает внутри JSON-тела.
        """
        try:
            data = json.loads(self.request.body)
            task_id = data.get('id')
            return self.get_queryset().get(id=task_id)
        except (json.JSONDecodeError, self.model.DoesNotExist):
            return None

    def post(self, request, *args, **kwargs):
        """
        Переопределяем точку входа POST.
        Делаем проверку, нашли ли мы объект перед тем, как валидировать форму.
        """
        self.object = self.get_object()
        if self.object is None:
            return JsonResponse({'status': 'error', 'message': 'Задача не найдена'}, status=404)
        
        # Запускаем стандартную валидацию формы UpdateView
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """
        Если форма успешно валидирована, сохраняем объект 
        и вместо редиректа возвращаем JsonResponse для нашего JS.
        """
        self.object = form.save()
        return JsonResponse({'status': 'success'})

    def form_invalid(self, form):
        """
        Если в форме есть ошибки (например, пустое имя), 
        возвращаем JSON со списком ошибок и статус-кодом 400.
        """
        return JsonResponse({
            'status': 'error', 
            'message': 'Ошибка валидации полей', 
            'errors': form.errors.get_json_data()
        }, status=400)
    
