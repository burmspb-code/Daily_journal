from django.shortcuts import render
from .models import Task

def task_list(request):
    # Запрашиваем все задачи из вашей базы данных на VPS
    tasks = Task.objects.all()
    
    # Передаем список задач в контекст шаблона task_list.html
    return render(request, 'daily/task_list.html', {'tasks': tasks})
