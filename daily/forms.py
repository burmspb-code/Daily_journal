from django import forms
from .models import Task, Bookmark


class TaskForm(forms.ModelForm):
    """Класс для опеделения полей формы для ввода информации."""
    class Meta:
        """Класс метаданных."""
        model = Task
        fields = ['title', 'reminder_at', 'comment', 'bookmark']

        # Профессиональный штрих: задаем тип поля "Календарь + Время"
        widgets = {
            'reminder_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    # Переопределяем метод __init__ для обработки даты
    def __init__(self, *args, **kwargs):
        # 1. Извлекаем пользователя из переданных аргументов контроллера
        self.user = kwargs.pop('user', None)

        super().__init__(*args, **kwargs)

        # 1. Логика для существующей даты при редактировании
        if self.instance and self.instance.pk and self.instance.reminder_at:
            self.initial['reminder_at'] = self.instance.reminder_at.strftime('%Y-%m-%dT%H:%M')

        # 2. Если пользователь передан, фильтруем выпадающий список закладок
        if self.user:
            self.fields['bookmark'].queryset = Bookmark.objects.filter(owner=self.user)
            self.fields['bookmark'].empty_label = "Выберите закладку"


class BookmarkForm(forms.ModelForm):
    """Класс для опеделения полей формы для ввода информации."""
    class Meta:
        """Класс метаданных."""
        model = Bookmark
        fields = ['title', 'description']
