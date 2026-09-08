from typing import ClassVar

from django import forms

from .models import Bookmark, Task


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
        fields = ("title", "reminder_at", "comment", "bookmark")
        widgets: ClassVar[dict] = {
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
    Форма редактирования задачи с календарем и поддержкой периодичности.
    """

    class Meta(TaskForm.Meta):
        # ИСПРАВЛЕНО: Заменили 'periodicity' на два новых чистых поля из модели Task
        fields = (
            "title",
            "reminder_at",
            "periodicity_value",
            "periodicity_unit",
            "comment",
            "bookmark"
        )

        # Переопределяем виджеты жестко на уровне мета-данных Django в фирменном темном стиле
        widgets: ClassVar[dict] = {
            # Явно принуждаем Django использовать виджет даты и времени HTML5
            "reminder_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "type": "datetime-local",
                    "class": "form-control form-control-sm bg-secondary text-white border-0",
                    "id": "id_reminder_at",
                },
            ),
            # Вместо кастомного виджета настраиваем дефолтный числовой инпут
            "periodicity_value": forms.NumberInput(
                attrs={
                    "class": "form-control bg-dark text-white border-secondary",
                    "min": "1",
                    "placeholder": "Кол-во",
                    "id": "id_periodicity_0",
                }
            ),
            # Настраиваем дефолтный селект выбора единицы времени
            "periodicity_unit": forms.Select(
                attrs={
                    "class": "form-select bg-dark text-white border-secondary",
                    "id": "id_periodicity_1",
                }
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
            # ИСКЛЮЧАЕМ ВСЕ ПОЛЯ ПЕРИОДИЧНОСТИ: у них виджеты уже идеально настроены в Meta.widgets
            if field_name in ["periodicity_value", "periodicity_unit", "reminder_at"]:
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
        fields = ("title", "description")
