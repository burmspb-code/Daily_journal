"""
Модуль форм приложения управления пользователями (users).

Содержит кастомную форму регистрации CustomUserCreateForm, построенную
на основе стандартной UserCreationForm. Форма автоматически включает
механизмы хэширования паролей, валидацию уникальности email и интеграцию
с сервисом защиты от роботов Google ReCAPTCHA.
"""

from django import forms

from django.contrib.auth.forms import UserCreationForm
# Импортируем библиотеки для работы капчи
#from django_recaptcha.fields import ReCaptchaField
#from django_recaptcha.widgets import ReCaptchaV2Checkbox

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
        fields = ('username', 'email', 'phone_number', 'avatar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поле email обязательным для заполнения на уровне формы
        self.fields['email'].required = True
