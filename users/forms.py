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
        existing_user = CustomUser.objects.filter(username=username).first()
        if existing_user:
            if existing_user.is_active:
                # Если активен — вызываем стандартную ошибку Django
                raise forms.ValidationError("Пользователь с таким Username уже существует.")

            # Неактивный аккаунт НЕ удаляем: возможно, ему уже отправлено
            # письмо со ссылкой активации, и удаление обрушит её.
            # Пользователю предлагается запросить новую ссылку.
            raise forms.ValidationError(
                "Этот Username уже занят неактивным аккаунтом. "
                "Если письмо с подтверждением не дошло, запросите "
                "повторную отправку ссылки активации."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')

        # Ищем пользователя с таким email
        existing_user = CustomUser.objects.filter(email=email).first()
        if existing_user:
            if existing_user.is_active:
                # Если активен — вызываем стандартную ошибку Django
                raise forms.ValidationError("Пользователь с таким Email уже существует.")

            # Неактивный аккаунт НЕ удаляем: возможно, ему уже отправлено
            # письмо со ссылкой активации, и удаление обрушит её.
            # Пользователю предлагается запросить новую ссылку.
            raise forms.ValidationError(
                "На этот Email уже зарегистрирован неактивный аккаунт. "
                "Если письмо с подтверждением не дошло, запросите "
                "повторную отправку ссылки активации."
            )

        return email

    def add_is_invalid_class(self):
        """Добавляет класс is-invalid к полям с ошибками после валидации."""
        for field in self.errors:
            if field in self.fields:
                current_class = self.fields[field].widget.attrs.get('class', '')
                self.fields[field].widget.attrs.update({
                    'class': f'{current_class} is-invalid'
                })

class ResendActivationForm(forms.Form):
    """Форма для повторной отправки ссылки активации.

    Запрашивается только email: пользователю не нужно вспоминать Username.
    """

    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "you@example.com",
                "autocomplete": "email",
                "autofocus": True,
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})


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
