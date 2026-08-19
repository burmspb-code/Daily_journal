from datetime import timedelta

from django import forms

from .models import Bookmark
from .models import Task


class DarkDurationWidget(forms.MultiWidget):
    """
    Форма для ввода пользователем периодичности выполнения задач.
    """

    def __init__(self, attrs=None):
        # Конфигурируем два внутренних инпута в вашем фирменном темном стиле
        widgets = [
            forms.NumberInput(
                attrs={
                    "class": "form-control bg-dark text-white border-secondary",
                    "min": "1",
                    "placeholder": "Кол-во",
                    "id": "edit-task-period-value",
                }
            ),
            forms.Select(
                attrs={
                    "class": "form-select bg-dark text-white border-secondary",
                    "id": "edit-task-period-unit",
                },
                choices=[
                    ("none", "Не повторять"),
                    ("minutes", "Минут"),
                    ("hours", "Часов"),
                    ("days", "Дней"),
                    ("weeks", "Недель"),
                    ("months", "Месяцев"),
                    ("years", "Лет"),
                ],
            ),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        """Разбивает timedelta из базы данных на число и тип периода."""
        if isinstance(value, timedelta):
            seconds = value.total_seconds()
            if seconds == 0:
                return [None, "none"]
            if seconds % 31536000 == 0:
                return [int(seconds / 31536000), "years"]
            if seconds % 2592000 == 0:
                return [int(seconds / 2592000), "months"]
            if seconds % 604800 == 0:
                return [int(seconds / 604800), "weeks"]
            if seconds % 86400 == 0:
                return [int(seconds / 86400), "days"]
            if seconds % 3600 == 0:
                return [int(seconds / 3600), "hours"]
            return [int(seconds / 60), "minutes"]
        return [None, "none"]

    def value_from_datadict(self, data, files, name):
        """Собирает отправленные данные обратно в timedelta, поддерживая любые префиксы имён."""
        # 1. Пытаемся найти ключи динамически по их окончаниям во входящем словаре POST
        val_0 = None
        val_1 = None
        print(f"Проверка --- {data.items()} ---")
        for key, value in data.items():
            if key.endswith(f"{name}_0"):
                val_0 = value
            elif key.endswith(f"{name}_1"):
                val_1 = value

        # Если динамический поиск не дал результатов, пробуем стандартный подход Django
        if val_0 is None:
            val_0 = data.get(f"{name}_0")
        if val_1 is None:
            val_1 = data.get(f"{name}_1")

        # Если период установлен в "Не повторять" или отсутствует
        if val_1 == "none" or not val_1:
            return None

        try:
            amount = int(val_0)
            if val_1 == "minutes":
                return timedelta(minutes=amount)
            if val_1 == "hours":
                return timedelta(hours=amount)
            if val_1 == "days":
                return timedelta(days=amount)
            if val_1 == "weeks":
                return timedelta(weeks=amount)
            if val_1 == "months":
                return timedelta(days=amount * 30)
            if val_1 == "years":
                return timedelta(days=amount * 365)
        except ValueError, TypeError:
            return None


class TaskForm(forms.ModelForm):
    """
    Базовая форма для создания и редактирования задач.

    Эта форма определяет основные поля задачи и логику фильтрации
    доступных закладок в зависимости от текущего пользователя.
    Наследуется Django ModelForm для автоматической валидации данных модели Task.
    """

    class Meta:
        """
        Мета-класс конфигурации формы.

        Определяет модель, с которой связана форма, список отображаемых полей
        и настройки виджетов (HTML-элементов) для конкретных полей.
        """

        model = Task
        # Поля, доступные для редактирования: название, напоминание, комментарий, закладка.
        # Поле status_flag исключено намеренно, так как оно рассчитывается автоматически.
        fields = ["title", "reminder_at", "comment", "bookmark"]
        widgets = {
            # Настройка виджета для поля напоминания: тип input='datetime-local'
            # позволяет использовать нативный календарь браузера.
            "reminder_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Инициализатор формы.

        Извлекает объект пользователя из kwargs (если передан) и ограничивает
        выбор закладок только теми, которые принадлежат этому пользователю.

        Args:
            *args: Позиционные аргументы, передаваемые в родительский класс.
            **kwargs: Именованные аргументы. Ожидается ключ 'user' для фильтрации.
        """
        # Извлекаем пользователя из kwargs, удаляя его из словаря, чтобы не передать дальше
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["title"].required = False

        # Если пользователь передан, фильтруем queryset для поля 'bookmark'
        if self.user:
            self.fields["bookmark"].queryset = Bookmark.objects.filter(owner=self.user)
            # Устанавливаем текст заглушки для пустого выбора
            self.fields["bookmark"].empty_label = "Выберите закладку"


class TaskEditForm(TaskForm):
    """
    Форма редактирования задачи с исправленным календарем и поддержкой периодичности.
    """

    class Meta(TaskForm.Meta):
        fields = ["title", "reminder_at", "periodicity", "comment", "bookmark"]

        # Переопределяем виджеты жестко на уровне мета-данных Django
        widgets = {
            "periodicity": DarkDurationWidget(),
            # Явно принуждаем Django использовать виджет даты и времени HTML5
            "reminder_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "type": "datetime-local",
                    "class": "form-control form-control-sm bg-secondary text-white border-0",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Словарь базовых CSS-классов для разных типов полей
        base_classes = {
            "bookmark": "form-select form-select-sm bg-dark text-white border-secondary",
            "comment": "form-control form-control-sm bg-secondary text-white border-0",
            "default": "form-control form-control-sm bg-secondary text-white border-0",
        }

        # Применяем стили ко всем полям формы
        for field_name, field in self.fields.items():
            # ИСКЛЮЧАЕМ ОБА ПОЛЯ: у них виджеты уже идеально настроены в Meta.widgets
            if field_name in ["periodicity", "reminder_at"]:
                continue

            # Устанавливаем количество строк для текстового поля комментария
            if field_name == "comment":
                field.widget.attrs.update({"rows": 3})

            # Получаем соответствующий класс или используем класс по умолчанию
            css_class = base_classes.get(field_name, base_classes["default"])
            field.widget.attrs.update({"class": css_class})


class BookmarkForm(forms.ModelForm):
    """
    Форма для управления закладками (создание и редактирование).

    Позволяет пользователю вводить название и описание закладки.
    Наследуется от ModelForm для работы с моделью Bookmark.
    """

    class Meta:
        """
        Мета-класс конфигурации формы закладок.

        Определяет модель и список полей, доступных для заполнения.
        """

        model = Bookmark
        # Поля формы: заголовок и описание
        fields = ["title", "description"]
