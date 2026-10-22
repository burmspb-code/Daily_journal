from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import TariffPlans  # Укажите ваше приложение, где лежит модель тарифов

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_tariff_plan(sender, instance, created, **kwargs):
    """Автоматически создает базовый тарифный план при регистрации нового пользователя.

    Аргументы:
        sender (Model): Класс модели, которая отправляет сигнал (User).
        instance (Object): Конкретный созданный/обновленный экземпляр пользователя.
        created (bool): Флаг, равен True только если запись создана впервые.
    """
    if created:
        # Так как это OneToOneField, мы просто создаем объект, связывая его с юзером.
        # Метод save() в модели TariffPlans сам подтянет базовые константы.
        TariffPlans.objects.create(user=instance)
