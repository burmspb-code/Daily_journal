"""
Модуль форм приложения управления пользователями (users).

Содержит кастомную форму регистрации CustomUserCreateForm, построенную
на основе стандартной UserCreationForm. Форма автоматически включает
механизмы хэширования паролей, валидацию уникальности email и интеграцию
с сервисом защиты от роботов Google ReCAPTCHA.
"""

from typing import ClassVar

from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from users.models import CustomUser

# Импортируем библиотеки для работы капчи
# from django_recaptcha.fields import ReCaptchaField
# from django_recaptcha.widgets import ReCaptchaV2Checkbox


class CustomUserCreateForm(UserCreationForm):
    """Форма для регистрации пользователя на основе кастомной модели."""

    class Meta(UserCreationForm.Meta):
        """Класс метаданных."""

        model = CustomUser
        fields = ("username", "email", "phone_number", "avatar", "tg_chat_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

        for field in self.fields.values():
            if field.widget.__class__.__name__ == 'Select':
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean_username(self):
        username = self.cleaned_data.get('username')

        # Ищем пользователя с таким username
        inactive_user = CustomUser.objects.filter(username=username).first()
        if inactive_user:
            if not inactive_user.is_active:
                # Если он не активен — удаляем «пустышку»
                inactive_user.delete()
            else:
                # Если активен — вызываем стандартную ошибку Django
                raise forms.ValidationError("Пользователь с таким Username уже существует.")

        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')

        # Ищем пользователя с таким email
        inactive_user = CustomUser.objects.filter(email=email).first()
        if inactive_user:
            if not inactive_user.is_active:
                # Если он не активен — удаляем «пустышку»
                inactive_user.delete()
            else:
                # Если активен — вызываем стандартную ошибку Django
                raise forms.ValidationError("Пользователь с таким Email уже существует.")

        return email

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
        fields = ("phone_number", "avatar", "tg_chat_id", "email_notifications", "telegram_notifications")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'telegram_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Автоматически добавляем Bootstrap-класс ко всем полям
        for _field_name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control"})

        self.fields["phone_number"].widget.attrs.update({"autocomplete": "tel"})

        # Убираем form-control у чекбоксов, так как они используют form-check-input
        self.fields["email_notifications"].widget.attrs.pop('class', None)
        self.fields["telegram_notifications"].widget.attrs.pop('class', None)

        # Если у пользователя нет tg_chat_id, отключаем чекбокс telegram_notifications
        if not self.instance or not self.instance.tg_chat_id:
            self.fields["telegram_notifications"].widget.attrs.update({'disabled': 'disabled'})
            self.fields["telegram_notifications"].help_text = "Для включения уведомлений необходимо указать ID Telegram"


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
