import subprocess
import sys
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Запуск Django и Celery одновременно для разработки"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Запуск Django сервера и Celery..."))

        # Команда для запуска Django
        django_process = subprocess.Popen([sys.executable, "manage.py", "runserver"])

        # Команда для запуска Celery (с флагом для Windows)
        celery_process = subprocess.Popen([
            "celery", "-A", "config", "worker", "--loglevel=info", "-P", "threads"
        ])

        try:
            # Держим процесс активным
            django_process.wait()
            celery_process.wait()
        except KeyboardInterrupt:
            # Красиво закрываем оба процесса при Ctrl+C
            self.stdout.write(self.style.WARNING("\nОстановка процессов..."))
            django_process.terminate()
            celery_process.terminate()
