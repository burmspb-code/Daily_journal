from django import forms
from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['name', 'reminder_at', 'comment']

        # Профессиональный штрих: задаем тип поля "Календарь + Время"
        widgets = {
            'reminder_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, 
                format='%Y-%m-%dT%H:%M'
            ),
        }

    # Переопределяем метод __init__, чтобы Django корректно читал существующую дату при редактировании
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.reminder_at:
            self.initial['reminder_at'] = self.instance.reminder_at.strftime('%Y-%m-%dT%H:%M')
