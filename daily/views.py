from django.views.generic import ListView
from .models import Task

class TaskListView(ListView):
    model = Task
    template_name = 'daily/task_list.html'
    context_object_name = 'tasks'  # Переменная, которая пойдет в HTML-шаблон

    def get_queryset(self):
        # Получаем базовый набор всех записей из PostgreSQL
        queryset = super().get_queryset()
        
        # 1. Фильтрация по наименованию контрагента
        name_query = self.request.GET.get('name', '').strip()
        if name_query:
            queryset = queryset.filter(name__icontains=name_query)
            
        # 2. Фильтрация по флагу управления
        flag_query = self.request.GET.get('flag', '')
        if flag_query != '':
            queryset = queryset.filter(status_flag=int(flag_query))
            
        # 3. Сортировка по времени создания или по умолчанию (PK)
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
