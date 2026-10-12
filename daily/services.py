"""Сервисный слой для бизнес-логики основного приложения (daily).

Содержит классы и методы для инкапсуляции бизнес-логики, фильтрации данных
и подготовки контекста для интерфейсов (веб-страниц и REST API).
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from daily.models import NotificationAttempt, Task
from daily.tasks import send_email_notification, send_telegram_notification

from .models import Bookmark

logger = logging.getLogger(__name__)

StatusChoices = Task.StatusChoices

# Заранее подготовленный словарь соответствия единиц времени и таймаутов просрочки
# Ключ — periodicity_unit, значение — интервал timedelta до перевода в OVERDUE
OVERDUE_TIMEOUTS = {
    'none': timedelta(minutes=15),    # Дефолт для разовых задач
    'minutes': timedelta(minutes=1),  # Минуты -> 1 минута на реакцию
    'hours': timedelta(minutes=5),    # Часы -> 5 минут на реакцию
    'days': timedelta(minutes=10),    # Дней -> 10 минут на реакцию
    'weeks': timedelta(minutes=15),   # Недель -> 15 минут на реакцию
    'months': timedelta(minutes=30),  # Месяцев -> 30 минут на реакцию
    'years': timedelta(hours=1),      # Лет -> 1 час на реакцию
}


class TaskService:
    """Сервисный класс для работы с бизнес-логикой задач.

    Предоставляет методы для агрегации данных, фильтрации, сортировки
    и минимизации количества SQL-запросов к моделям Task и Bookmark.
    """

    @staticmethod
    def get_task_list_context(user, params: dict) -> dict:
        """Формирует единый контекст данных для списка задач.

        Метод агрегирует параметры фильтрации, загружает связанные закладки
        в оперативную память для предотвращения проблемы N+1 и запрашивает
        финальный QuerySet задач. Используется совместно в Django Views и DRF API.

        Args:
            user (User): Объект текущего аутентифицированного пользователя.
            params (dict): Словарь GET-параметров запроса (или query_params в DRF).

        Returns:
            dict: Словарь с контекстом данных:
                - tasks (QuerySet): Отфильтрованный набор задач.
                - bookmarks (list): Список всех объектов Bookmark пользователя.
                - current_bookmark (Bookmark|None): Текущая активная закладка.
                - current_title (str): Применённая строка поиска по названию.
                - current_flag (str): Применённый ID флага статуса.
                - current_sort (str): Ключ текущей сортировки.
        """
        if not user or not user.is_authenticated:
            return {
                "tasks": Task.objects.none(),
                "bookmarks": [],
                "current_bookmark": None,
                "current_title": "",
                "current_flag": "",
                "current_sort": "",
            }

        # Считываем параметры один раз
        title_param = params.get("title", "").strip()
        flag_param = params.get("flag", "").strip()
        sort_param = params.get("sort", "").strip()
        bookmark_param = str(params.get("bookmark", "")).strip()

        # Оптимизация: загружаем все закладки в память ОДНИМ запросом
        bookmarks = list(Bookmark.objects.filter(owner=user).order_by("id"))

        # Определяем текущую активную закладку в памяти
        current_bookmark = None
        if bookmark_param.isdigit():
            target_id = int(bookmark_param)
            current_bookmark = next((b for b in bookmarks if b.id == target_id), None)

        # Если ID не передан или чужой — берем первую закладку пользователя
        if not current_bookmark and bookmarks:
            current_bookmark = bookmarks[0]

        # Получаем отфильтрованные задачи, передавая уже найденную закладку
        tasks_queryset = TaskService._get_filtered_tasks_queryset(
            user=user,
            current_bookmark=current_bookmark,
            title_query=title_param,
            flag_query=flag_param,
            sort_query=sort_param,
        )

        return {
            "tasks": tasks_queryset,
            "bookmarks": bookmarks,
            "current_bookmark": current_bookmark,
            "current_title": title_param,
            "current_flag": flag_param,
            "current_sort": sort_param,
        }

    @staticmethod
    def _get_filtered_tasks_queryset(
        user, current_bookmark, title_query: str, flag_query: str, sort_query: str
    ) -> QuerySet:
        """Внутренний метод для фильтрации и сортировки QuerySet задач.

        Выполняет SQL JOIN с таблицами Bookmark и User. Исключает повторные
        запросы к БД для поиска закладок за счет использования уже готового
        объекта `current_bookmark`.

        Args:
            user (User): Объект владельца задач.
            current_bookmark (Bookmark|None): Объект выбранной закладки.
            title_query (str): Поисковый запрос для фильтрации по названию (icontains).
            flag_query (str): Строковое представление ID флага статуса.
            sort_query (str): Ключ направления сортировки (newest, oldest, etc.).

        Returns:
            QuerySet: Оптимизированный и отсортированный набор объектов Task.
        """
        # SQL JOIN для предотвращения N+1
        queryset = Task.objects.filter(owner=user).select_related("bookmark", "owner")

        # Фильтрация по объекту закладки, который мы уже нашли в памяти
        if current_bookmark:
            queryset = queryset.filter(bookmark=current_bookmark)
        else:
            # У пользователя вообще нет закладок
            return Task.objects.none()

        # Поиск по названию
        if title_query:
            queryset = queryset.filter(title__icontains=title_query)

        # Фильтрация по флагу статуса
        if flag_query.isdigit():
            queryset = queryset.filter(status_flag=int(flag_query))

        # Безопасная сортировка
        sort_mapping = {
            "newest": ["-created_at", "-id"],
            "oldest": ["created_at", "id"],
            "name_asc": ["title"],
            "name_desc": ["-title"],
        }
        order_by_fields = sort_mapping.get(sort_query, ["id"])

        return queryset.order_by(*order_by_fields)


class ReminderNotificationService:
    """Сервисный класс для работы с бизнес-логикой уведомлений и контроля просрочки.

    Предоставляет методы для автоматической обработки, фильтрации и отправки
    наступивших напоминаний, а также для динамического перевода невыполненных
    задач в статус просроченных на основе конфигурационной матрицы таймаутов.

    Отправка уведомлений (Email, Telegram) вынесена в отдельные асинхронные
    Celery-задачи. Сервис только ищет задачи, создаёт записи NotificationAttempt
    и ставит задачи в очередь через .delay(). Это предотвращает блокировку
    воркера синхронными HTTP-запросами и обеспечивает повторные попытки (retry).
    """

    def __init__(self):
        self.now = timezone.now()

    def execute(self) -> dict:
        """Главный управляющий метод конвейера фоновой обработки задач.

        Метод координирует последовательное выполнение двух ключевых этапов:
        выборку и постановку в очередь новых наступивших напоминаний, а затем —
        поиск и перевод залежавшихся задач в статус OVERDUE. Предназначен для
        регулярного вызова внутри минутного планировщика Celery Beat.

        Returns:
            dict: Словарь со статистикой выполнения операции:
                - sent (int): Количество задач, поставленных в очередь на отправку.
                - overdue (int): Количество задач, переведённых в статус просроченных.
        """
        sent_count = self._process_new_reminders()
        overdue_count = self._check_and_set_dynamic_overdue()

        return {
            "sent": sent_count,
            "overdue": overdue_count,
        }

    @transaction.atomic
    def _process_new_reminders(self) -> int:
        """Ищет наступившие напоминания и ставит задачи отправки в очередь Celery.

        Метод делает один оптимизированный SQL-запрос к базе данных, выбирая
        все наступившие задачи в статусе CREATED. Для каждой задачи проверяет
        наличие успешной записи NotificationAttempt по каждому каналу. Если
        успешной отправки ещё не было — создаёт запись pending и ставит
        асинхронную Celery-задачу через .delay().

        Returns:
            int: Количество задач, для которых инициирована отправка.
        """
        active_reminders = (
            Task.objects
            .filter(reminder_at__lte=self.now, status_flag=StatusChoices.CREATED)
            .select_related("owner")
            .order_by("id")
        )

        count = 0

        for task in active_reminders:
            logger.info(
                f"== [ОТПРАВКА] Задача ID {task.id} → {task.owner.email} =="
            )

            deadline_str = task.reminder_at.strftime("%Y-%m-%d %H:%M")
            task_changed = False

            # --- Email ---
            if task.owner.email_notifications:
                already_sent = NotificationAttempt.objects.filter(
                    task=task,
                    channel=NotificationAttempt.CHANNEL_EMAIL,
                    status=NotificationAttempt.STATUS_SENT,
                ).exists()

                if not already_sent:
                    attempt = NotificationAttempt.objects.create(
                        task=task,
                        channel=NotificationAttempt.CHANNEL_EMAIL,
                        status=NotificationAttempt.STATUS_PENDING,
                    )
                    send_email_notification.delay(
                        attempt_id=attempt.id,
                        to_email=task.owner.email,
                        task_name=task.title,
                        deadline=deadline_str,
                    )
                    task_changed = True
                    logger.info(f"  → Email: задача {attempt.id} поставлена в очередь")

            # --- Telegram ---
            if task.owner.telegram_notifications and task.owner.tg_chat_id:
                already_sent = NotificationAttempt.objects.filter(
                    task=task,
                    channel=NotificationAttempt.CHANNEL_TELEGRAM,
                    status=NotificationAttempt.STATUS_SENT,
                ).exists()

                if not already_sent:
                    attempt = NotificationAttempt.objects.create(
                        task=task,
                        channel=NotificationAttempt.CHANNEL_TELEGRAM,
                        status=NotificationAttempt.STATUS_PENDING,
                    )
                    send_telegram_notification.delay(
                        attempt_id=attempt.id,
                        chat_id=task.owner.tg_chat_id,
                        task_name=task.title,
                        deadline=deadline_str,
                    )
                    task_changed = True
                    logger.info(f"  → Telegram: задача {attempt.id} поставлена в очередь")

            # --- Перевод статуса ---
            # Меняем статус только если хотя бы по одному каналу была попытка
            if task_changed:
                task.status_flag = StatusChoices.IN_PROGRESS
                task.status_changed_at = self.now
                task.save(update_fields=[
                    "status_flag",
                    "status_changed_at",
                ])
                count += 1

        return count

    def _check_and_set_dynamic_overdue(self) -> int:
        """Контролирует, фиксирует и записывает просрочку активных напоминаний.

        Метод сканирует все задачи со статусом IN_PROGRESS, динамически извлекает
        из словаря OVERDUE_TIMEOUTS соответствующий лимит времени на реакцию для
        каждой единицы периодичности и переводит задачи, превысившие этот лимит,
        в статус OVERDUE. Записывает причину просрочки в лог строки.

        Returns:
            int: Количество задач, признанных просроченными за текущую итерацию.
        """
        active_tasks = Task.objects.filter(status_flag=StatusChoices.IN_PROGRESS)
        overdue_tasks_ids = []

        for task in active_tasks:
            timeout_delta = OVERDUE_TIMEOUTS.get(
                task.periodicity_unit, OVERDUE_TIMEOUTS["none"]
            )
            deadline_time = task.reminder_at + timeout_delta

            if self.now > deadline_time:
                logger.warning(
                    f"== [ПРОСРОЧКА] Задача ID {task.id} превысила лимит "
                    f"на реакцию ({timeout_delta}) =="
                )

                task.status_flag = StatusChoices.OVERDUE
                task.status_changed_at = self.now
                task.save(update_fields=[
                    "status_flag",
                    "status_changed_at",
                ])

                overdue_tasks_ids.append(task.id)

        return len(overdue_tasks_ids)
