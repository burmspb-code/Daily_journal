from django import forms
from .models import Task, Bookmark


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
    Форма редактирования задачи (специализированная версия TaskForm).

    Предназначена исключительно для обновления существующих задач.
    В отличие от базовой формы, здесь применяется дополнительная стилизация
    под темную тему интерфейса (Bootstrap классы) и жесткая фиксация
    набора редактируемых полей.

    Важно: Поле status_flag намеренно НЕ объявлено здесь и исключено из Meta.
    Это реализует логику "Авторасчета статуса": пользователь не может менять
    статус вручную, он отображается только для чтения в шаблоне.
    """

    class Meta(TaskForm.Meta):
        """
        Мета-класс, наследующий настройки от TaskForm.

        Переопределяет список полей, явно подтверждая отсутствие status_flag.
        Это гарантирует, что цикл {% for field in form %} в шаблоне
        никогда не сгенерирует поле для ручного выбора статуса.
        """

        # Явно указываем поля, чтобы избежать случайного включения скрытых полей
        fields = ["title", "reminder_at", "comment", "bookmark"]

    def __init__(self, *args, **kwargs):
        """
        Инициализатор формы редактирования.

        Применяет специфические CSS-классы для каждого поля формы,
        адаптируя стандартный вид Django под дизайн приложения (темная тема).
        Также гарантирует правильный тип ввода для поля даты/времени.

        Args:
            *args: Позиционные аргументы для родительского конструктора.
            **kwargs: Именованные аргументы.
        """
        super().__init__(*args, **kwargs)

        # Словарь базовых CSS-классов для разных типов полей
        base_classes = {
            "bookmark": "form-select form-select-sm bg-dark text-white border-secondary",
            "comment": "form-control form-control-sm bg-secondary text-white border-0",
            "default": "form-control form-control-sm bg-secondary text-white border-0",
        }

        # Применяем стили ко всем полям формы
        for field_name, field in self.fields.items():
            # Устанавливаем количество строк для текстового поля комментария
            if field_name == "comment":
                field.widget.attrs.update({"rows": 3})

            # Получаем соответствующий класс или используем класс по умолчанию
            css_class = base_classes.get(field_name, base_classes["default"])
            field.widget.attrs.update({"class": css_class})

        # Гарантируем, что поле напоминания имеет тип datetime-local
        self.fields["reminder_at"].widget.format = "%Y-%m-%dT%H:%M"
        self.fields["reminder_at"].widget.attrs.update(
            {
                "type": "datetime-local",
                "class": base_classes.get("default"),  # применяем ваш стиль
            }
        )


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
