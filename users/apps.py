from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # Стандартное поле для ID
    name = "users"
    verbose_name = "Управление пользователями"  # Красивое имя приложения в админке

    def ready(self):
        """Этот метод вызывается автоматически, когда Django запускается."""
        # Импортируем сигналы именно здесь, чтобы избежать круговых импортов
