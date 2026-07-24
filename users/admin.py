from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.models import CustomUser
# Импортируем именно админские формы
from users.forms import CustomUserAdminCreationForm, CustomUserChangeForm


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Настройка отображения кастомной модели пользователя в админке."""

    add_form = CustomUserAdminCreationForm
    form = CustomUserChangeForm

    # Поля для отображения в таблице
    list_display = (
        'username',
        'email',
        'phone_number',
        'avatar',
        "is_staff",
        "is_superuser",
        "is_active",
    )

    # Клик по этим полям будет открывать страницу редактирования пользователя
    list_display_links = ('username', 'email')

    # Поля, по которым можно фильтровать пользователей в правой панели
    list_filter = ('is_staff', 'is_superuser', 'is_active')

    # Поля, по которым работает поиск вверху таблицы
    search_fields = ('username', 'email', 'phone_number')

    # Сортировка
    ordering = ('username', 'is_staff', 'is_superuser', 'is_active')

    # НАСТРОЙКА ПОЛЕЙ ПРИ РЕДАКТИРОВАНИИ (Исправлено: возвращены обязательные поля Django)
    fieldsets = (
        (
            "Личная информация",
            {
                "fields": ("username", "email", "phone_number", "avatar")
            },
        ),
        (
            "Права доступа",
            {
                # groups и user_permissions обязательны для работы UserAdmin!
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
            },
        ),
        (
            "Важные даты",
            {
                # Даты входа и регистрации также необходимы базовому классу
                "fields": ("last_login", "date_joined")
            },
        ),
    )

    # Показывает эти поля при создании нового пользователя через админку
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),  # Этот CSS-класс делает поля ввода шире
                # Для стандартных форм Django Auth здесь не нужно писать 'password'.
                # Форма сама автоматически добавит поля ввода и подтверждения пароля.
                "fields": ("username", "email"),
            },
        ),
    )

    # Делаем даты системными (только для чтения), чтобы их нельзя было случайно изменить
    readonly_fields = ('last_login', 'date_joined')
