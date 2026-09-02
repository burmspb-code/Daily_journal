"""
Модуль форм приложения управления пользователями (users).

Содержит кастомную форму регистрации CustomUserCreateForm, построенную
на основе стандартной UserCreationForm. Форма автоматически включает
механизмы хэширования паролей, валидацию уникальности email и интеграцию
с сервисом защиты от роботов Google ReCAPTCHA.
"""

from django import forms

from django.contrib.auth.forms import UserCreationForm, UserChangeForm

# Импортируем библиотеки для работы капчи
# from django_recaptcha.fields import ReCaptchaField
# from django_recaptcha.widgets import ReCaptchaV2Checkbox

from users.models import CustomUser


class CustomUserCreateForm(UserCreationForm):
    """Форма для регистрации пользователя на основе кастомной модели."""

    # Капча объявлена как обязательное поле класса для защиты от спам-регистраций
    # captcha = ReCaptchaField(
    #     label="Проверка на робота",
    #     widget=ReCaptchaV2Checkbox(),
    #     error_messages={"required": "Пожалуйста, подтвердите, что вы не робот."},
    # )

    class Meta(UserCreationForm.Meta):
        """Класс метаданных."""

        model = CustomUser
        # Явно перечисляем поля, которые пользователь заполняет при регистрации.
        # Поля password1 и password2 добавятся автоматически от UserCreationForm.
        fields = ("username", "email", "phone_number", "avatar", "tg_chat_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поле email обязательным для заполнения на уровне формы
        self.fields["email"].required = True
        
        # Добавляем Bootstrap классы к виджетам
        for field in self.fields.values():
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
    
    def add_is_invalid_class(self):
        """Добавляет класс is-invalid к полям с ошибками после валидации."""
        for field in self.errors:
            if field in self.fields:
                current_class = self.fields[field].widget.attrs.get('class', '')
                self.fields[field].widget.attrs.update({
                    'class': f'{current_class} is-invalid'
                })


class UserProfileForm(forms.ModelForm):
    """Форма для редактирования профиля пользователя."""

    class Meta:
        model = CustomUser
        # Перечисляем поля, которые пользователю разрешено редактировать
        fields = ("phone_number", "avatar", "tg_chat_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Автоматически добавляем Bootstrap-класс ко всем полям
        for field_name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control"})

        self.fields["phone_number"].widget.attrs.update({"autocomplete": "tel"})


class CustomUserAdminCreationForm(UserCreationForm):
    """Специальная форма для создания пользователя В АДМИНКЕ."""

    class Meta(UserCreationForm.Meta):
        """Класс метаданных."""

        model = CustomUser
        fields = ("username", "email")  # В админке при создании просим только это

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True


class CustomUserChangeForm(UserChangeForm):
    """Форма для редактирования пользователя в админке."""

    class Meta(UserChangeForm.Meta):
        """Класс метаданных."""

        model = CustomUser
        fields = "__all__"
