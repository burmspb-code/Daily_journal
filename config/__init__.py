from .celery import app as celery_app

# Это гарантирует, что приложение Celery всегда импортируется
# при запуске Django, и shared_task будут работать корректно.
__all__ = ("celery_app",)
