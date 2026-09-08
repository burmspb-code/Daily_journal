from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

# Импортируем именно админские формы
from users.forms import CustomUserAdminCreationForm, CustomUserChangeForm
from users.models import CustomUser, TariffPlans


class TariffPlansInline(admin.StackedInline):
    """Позволяет редактировать тарифный план прямо внутри карточки пользователя."""
    model = TariffPlans
    can_delete = False  # Запрещаем удалять тариф отдельно от пользователя
    verbose_name_plural = "Текущий тарифный план"
    extra = 1  # Всегда показывать форму для создания тарифа, если его нет
    max_num = 1  # Разрешить только один тариф на пользователя
    # Блокируем автоматические лимиты для редактирования
    readonly_fields = ("max_tasks", "max_bookmarks")
    # Убираем поле user - Django автоматически заполнит его при создании через инлайн
    fields = ("plan_name", "max_tasks", "max_bookmarks", "expires_at", "is_archive")


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Настройка отображения кастомной модели пользователя в админке."""

    add_form = CustomUserAdminCreationForm
    form = CustomUserChangeForm

    # ДОБАВЛЕНО: 'get_tariff_plan' в список колонок таблицы
    list_display = (
        "username",
        "email",
        "get_tariff_plan",  # Выводит красивое название тарифа
        "phone_number",
        "avatar",
        "is_staff",
        "is_superuser",
        "is_active",
    )

    list_display_links = ("username", "email")
    list_filter = ("is_staff", "is_superuser", "is_active", "tariff_plan__plan_name") # Можно фильтровать по тарифам
    search_fields = ("username", "email", "phone_number")
    ordering = ("username", "is_staff", "is_superuser", "is_active")

    # Инлайн-форма тарифа в карточку пользователя
    inlines = (TariffPlansInline,)

    fieldsets = (
        (
            "Личная информация",
            {"fields": ("username", "email", "phone_number", "avatar")},
        ),
        (
            "Права доступа",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Важные даты",
            {"fields": ("last_login", "date_joined")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email"),
            },
        ),
    )

    readonly_fields = ("last_login", "date_joined")

    def save_model(self, request, obj, form, change):
        """Принудительно создаем тарифный план при сохранении пользователя."""
        super().save_model(request, obj, form, change)
        # Создаем тариф, если его нет у пользователя
        if not hasattr(obj, 'tariff_plan') or not obj.tariff_plan:
            TariffPlans.objects.get_or_create(user=obj)

    def save_formset(self, request, form, formset, change):
        """Принудительно сохраняем инлайн-форму тарифа даже без изменений."""
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TariffPlans):
                # Если это новый тариф без пользователя, привязываем к текущему пользователю
                if not instance.user_id:
                    instance.user = form.instance
                instance.save()
        formset.save_m2m()

    # Метод для отображения тарифа в таблице
    @admin.display(description="Тарифный план")
    def get_tariff_plan(self, obj):
        """Безопасно возвращает актуальное название тарифа для таблицы."""
        try:
            # Используем related_name для доступа к тарифу через объект пользователя
            return obj.tariff_plan.get_plan_name_display()
        except TariffPlans.DoesNotExist:
            return "Нет тарифа"


@admin.register(TariffPlans)
class TariffPlansAdmin(admin.ModelAdmin):
    """Настройка отображения тарифных планов в админ-панели Django."""

    # Поля, которые будут видны в виде таблицы в общем списке
    list_display = (
        "user",
        "plan_name",
        "max_tasks",
        "max_bookmarks",
        "expires_at",
        "is_archive"
    )

    # Фильтры в правой колонке для быстрого поиска
    list_filter = ("plan_name", "is_archive", "expires_at")

    # Поиск по имени пользователя или его email
    search_fields = ("user__username", "user__email")

    # Защита автоматических полей от ручного редактирования
    # Оставляем доступными для изменения только сам тариф, пользователя, архив и дату
    readonly_fields = ("max_tasks", "max_bookmarks")

    # Группировка полей внутри карточки редактирования (для красоты и порядка)
    fieldsets = (
        ("Основная информация", {
            "fields": ("user", "plan_name", "is_archive")
        }),
        ("Автоматические лимиты (Зависят от тарифа)", {
            "fields": ("max_tasks", "max_bookmarks"),
            "description": "Эти поля заполняются автоматически при выборе тарифного плана."
        }),
        ("Срок действия подписки", {
            "fields": ("expires_at",),
        }),
    )
