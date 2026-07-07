from django import forms
from .models import Task, Bookmark


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['name', 'reminder_at', 'comment', 'bookmark']

        # Профессиональный штрих: задаем тип поля "Календарь + Время"
        widgets = {
            'reminder_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    # Переопределяем метод __init__ для обработки даты и установки дефолтной закладки
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Логика для существующей даты при редактировании
        if self.instance and self.instance.pk and self.instance.reminder_at:
            self.initial['reminder_at'] = self.instance.reminder_at.strftime('%Y-%m-%dT%H:%M')

        # 2. Логика для дефолтной Закладки 1 (если объект еще создается)
        if not self.instance or not self.instance.pk:
            bookmark, created = Bookmark.objects.get_or_create(
                name="Закладка 1",
                defaults={"description": "Автоматически созданная базовая закладка"}
            )
            self.initial['bookmark'] = bookmark.id
