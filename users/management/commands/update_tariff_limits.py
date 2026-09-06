from django.core.management.base import BaseCommand
from users.models import TariffPlans


class Command(BaseCommand):
    help = 'Обновляет лимиты задач и закладок для всех существующих тарифных планов'

    def handle(self, *args, **options):
        tariffs = TariffPlans.objects.all()
        count = tariffs.count()

        if count == 0:
            self.stdout.write(self.style.WARNING('Нет тарифных планов для обновления.'))
            return

        self.stdout.write(f'Найдено {count} тарифных планов. Обновляем лимиты...')

        updated_count = 0
        for tariff in tariffs:
            old_max_tasks = tariff.max_tasks
            old_max_bookmarks = tariff.max_bookmarks

            # Вызываем save() для обновления лимитов согласно новым константам
            tariff.save()

            if tariff.max_tasks != old_max_tasks or tariff.max_bookmarks != old_max_bookmarks:
                updated_count += 1
                self.stdout.write(
                    f'Обновлен тариф для {tariff.user.username}: '
                    f'задачи {old_max_tasks} -> {tariff.max_tasks}, '
                    f'закладки {old_max_bookmarks} -> {tariff.max_bookmarks}'
                )

        self.stdout.write(
            self.style.SUCCESS(f'Успешно обновлено {updated_count} из {count} тарифных планов')
        )
