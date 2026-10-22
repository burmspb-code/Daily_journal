"""Сервисный слой для бизнес-логики основного приложения (daily).

Содержит классы и методы для инкапсуляции бизнес-логики, фильтрации данных
и подготовки контекста для интерфейсов (веб-страниц и REST API).
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from daily.models import Bookmark, NotificationAttempt, Task
from daily.tasks import send_email_notification, send_telegram_notification

logger = logging.getLogger(__name__)

StatusChoices = Task.StatusChoices


def _dispatch(items: list) -> None:
    """Ставит в очередь Celery список отложенных вызовов доставки.

    Вызывается через `transaction.on_commit`, поэтому запускается уже после
    успешного COMMIT. Ошибка отправки одного сообщения не должна отменять
    остальные, поэтому каждый вызов обёрнут в try/except.

    Args:
        items: Список кортежей (celery_task, kwargs).
    """
    for celery_task, kwargs in items:
        try:
            celery_task.delay(**kwargs)
        except Exception:
            logger.error(
                f"❌ Не удалось поставить задачу {celery_task.name} в очередь: "
                f"attempt_id={kwargs.get('attempt_id')}",
                exc_info=True,
            )

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

# Единицы периода, которые считаются корректными для периодической задачи.
PERIODIC_UNITS = ('minutes', 'hours', 'days', 'weeks', 'months', 'years')

# TODO: заменить на календарно точный расчёт месяцев и лет (add_months).
# Пока используется упрощённая аппроксимация, чтобы не блокировать v1.
DAYS_IN_MONTH = 30
DAYS_IN_YEAR = 365


def is_periodic(task) -> bool:
    """Возвращает True, если задача является периодической.

    Периодической считается задача с известной единицей периода и положительным
    значением периода. Проверка значения защищает от «полунастроенных» задач,
    которые иначе могли бы зацикливаться на каждом прогоне планировщика.
    """
    return (
        task.periodicity_unit in PERIODIC_UNITS
        and bool(task.periodicity_value)
        and task.periodicity_value > 0
    )


def get_period_delta(task):
    """Возвращает шаг периода задачи в виде timedelta.

    Для месяцев и лет пока используется упрощённая аппроксимация (30/365 дней).
    """
    if not is_periodic(task):
        return None

    value = task.periodicity_value

    if task.periodicity_unit == 'months':
        return timedelta(days=DAYS_IN_MONTH * value)
    if task.periodicity_unit == 'years':
        return timedelta(days=DAYS_IN_YEAR * value)

    return timedelta(**{task.periodicity_unit: value})


def get_next_occurrence(reminder_at, period, now):
    """Возвращает ближайший момент сетки периода строго больше ``now``.

    Сдвиг выполняется по сетке от исходного ``reminder_at``, а не от момента
    реакции пользователя. Если ``now`` ещё не достиг ``reminder_at`` (или задача
    не периодическая), возвращается исходное значение.
    """
    if reminder_at is None or period is None or period <= timedelta(0):
        return reminder_at

    if now <= reminder_at:
        return reminder_at

    elapsed_periods = (now - reminder_at) // period
    return reminder_at + period * (elapsed_periods + 1)


def close_occurrence(task, now=None) -> bool:
    """Закрывает текущее наступление периодической задачи.

    Сдвигает ``reminder_at`` на следующее наступление по сетке, но только если
    текущее наступление уже наступило (``reminder_at <= now``). Благодаря этому
    повторный вызов из статуса OVERDUE не двигает время ещё раз.

    Returns:
        bool: True, если ``reminder_at`` был изменён.
    """
    if not is_periodic(task):
        return False

    now = now or timezone.now()
    next_at = get_next_occurrence(task.reminder_at, get_period_delta(task), now)

    if next_at is None or next_at == task.reminder_at:
        return False

    task.reminder_at = next_at
    return True


def format_reminder_at(value) -> str:
    """Форматирует время напоминания для сообщений пользователю."""
    if value is None:
        return "не задано"
    return timezone.localtime(value).strftime('%d.%m.%Y %H:%M')


def complete_task(task, now=None) -> dict:
    """Завершает текущий цикл задачи по действию пользователя «Выполнено».

    Для разовой задачи сохраняет статус COMPLETED (как и раньше). Для
    периодической задачи статус COMPLETED в БД не пишется: цикл закрывается
    сдвигом ``reminder_at`` и возвратом в CREATED. Если наступление ещё не
    наступило (статус CREATED и время в будущем), действие ничего не меняет и
    лишь сообщает пользователю запланированное время.

    Returns:
        dict: Результат операции для веб-интерфейса и API.
    """
    now = now or timezone.now()

    if not is_periodic(task):
        task.status_flag = StatusChoices.COMPLETED
        task.status_changed_at = now
        task.save(update_fields=['status_flag', 'status_changed_at'])
        return {
            'changed': True,
            'completed': True,
            'is_periodic': False,
            'status': task.status_flag,
            'status_display': task.get_status_flag_display(),
            'reminder_at': task.reminder_at,
            'message': 'Задача выполнена.',
        }

    # Периодическая задача в статусе CREATED с ещё не наступившим временем:
    # реагировать не на что, цикл двигать рано.
    if task.status_flag == StatusChoices.CREATED and task.reminder_at and task.reminder_at > now:
        return {
            'changed': False,
            'completed': False,
            'is_periodic': True,
            'status': task.status_flag,
            'status_display': task.get_status_flag_display(),
            'reminder_at': task.reminder_at,
            'message': f"Время напоминания запланировано на {format_reminder_at(task.reminder_at)}.",
        }

    shifted = close_occurrence(task, now)
    task.status_flag = StatusChoices.CREATED
    task.status_changed_at = now

    update_fields = ['status_flag', 'status_changed_at']
    if shifted:
        update_fields.append('reminder_at')
    task.save(update_fields=update_fields)

    return {
        'changed': True,
        'completed': False,
        'is_periodic': True,
        'status': task.status_flag,
        'status_display': task.get_status_flag_display(),
        'reminder_at': task.reminder_at,
        'message': f"Цикл завершён. Следующее напоминание: {format_reminder_at(task.reminder_at)}.",
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

        Метод выбирает все задачи, у которых ``reminder_at`` уже наступил и
        которые ждут обработки: новые (CREATED) и периодические, ожидающие
        следующего цикла (OVERDUE). Задачи в статусе IN_PROGRESS не трогаются —
        это «уведомление отправлено, ждём реакции пользователя». Разовые задачи
        в OVERDUE тоже не трогаются, иначе уведомление уходило бы повторно.

        Строки блокируются через `select_for_update(skip_locked=True)`:
        параллельный прогон Celery Beat пропустит уже захваченные задачи, а не
        создаст для них вторую пару уведомлений.

        Для каждого канала проверяется наличие активной попытки доставки —
        уже успешной ИЛИ ещё выполняющейся (pending, способная завершиться
        собственным retry). Дедупликация привязана к конкретному наступлению
        (``scheduled_for = reminder_at``), поэтому после сдвига периодической
        задачи создаётся новая попытка. Сама доставка ставится в очередь через
        `transaction.on_commit`, чтобы воркер не начал выполнение раньше коммита.

        Returns:
            int: Количество задач, для которых инициирована отправка.
        """
        periodic_units = list(PERIODIC_UNITS)

        active_reminders = (
            Task.objects
            .filter(
                Q(status_flag=StatusChoices.CREATED)
                | Q(status_flag=StatusChoices.OVERDUE, periodicity_unit__in=periodic_units)
            )
            .filter(reminder_at__lte=self.now)
            .select_related("owner")
            .select_for_update(skip_locked=True, of=("self",))
            .order_by("id")
        )

        count = 0
        # Список для отложенного запуска Celery-задач строго после коммита БД
        tasks_to_delay = []

        for task in active_reminders:
            # reminder_at хранится как UTC-aware. Без localtime() в текст
            # попадало бы UTC, и дедлайн в уведомлении отставал бы на смещение
            # часового пояса (для Europe/Moscow — на 3 часа).
            deadline_str = timezone.localtime(task.reminder_at).strftime("%Y-%m-%d %H:%M")
            # Насколько задача опоздала к моменту отправки: если now ушёл дальше
            # дедлайна реакции, уведомление помечается как «Пропущенное».
            timeout_delta = OVERDUE_TIMEOUTS.get(
                task.periodicity_unit, OVERDUE_TIMEOUTS['none']
            )
            is_late = self.now > task.reminder_at + timeout_delta
            late_marker = '[ПРОПУЩЕНО] ' if is_late else ''

            logger.info(
                f"== [ОТПРАВКА] {late_marker}Задача ID {task.id} → "
                f"Пользователь ID {task.owner_id} =="
            )

            task_changed = False

            # --- Email ---
            if task.owner.email_notifications:
                if self._enqueue_notification(
                    task=task,
                    channel=NotificationAttempt.CHANNEL_EMAIL,
                    celery_task=send_email_notification,
                    delivery_kwargs={
                        "to_email": task.owner.email,
                        "task_name": task.title,
                        "deadline": deadline_str,
                        "is_late": is_late,
                    },
                    tasks_to_delay=tasks_to_delay,
                ):
                    task_changed = True

            # --- Telegram ---
            if task.owner.telegram_notifications and task.owner.tg_chat_id:
                if self._enqueue_notification(
                    task=task,
                    channel=NotificationAttempt.CHANNEL_TELEGRAM,
                    celery_task=send_telegram_notification,
                    delivery_kwargs={
                        "chat_id": str(task.owner.tg_chat_id),
                        "task_name": task.title,
                        "deadline": deadline_str,
                        "is_late": is_late,
                    },
                    tasks_to_delay=tasks_to_delay,
                ):
                    task_changed = True

            # --- Перевод статуса ---
            # Статус IN_PROGRESS ставится независимо от наличия включённых
            # каналов: задача уже «наступила», ждём реакции пользователя.
            if task.status_flag != StatusChoices.IN_PROGRESS:
                task.status_flag = StatusChoices.IN_PROGRESS
                task.status_changed_at = self.now
                task.save(update_fields=[
                    "status_flag",
                    "status_changed_at",
                ])
                count += 1
            elif task_changed:
                logger.info(
                    f"  → Задача ID {task.id} уже в работе, но создана новая попытка"
                )

        # Безопасный запуск Celery-задач. Вызовутся только тогда,
        # когда транзакция полностью и успешно запишется в базу данных.
        if tasks_to_delay:
            transaction.on_commit(lambda items=list(tasks_to_delay): _dispatch(items))

        return count

    @staticmethod
    def _enqueue_notification(
        task,
        channel: str,
        celery_task,
        delivery_kwargs: dict,
        tasks_to_delay: list,
    ) -> bool:
        """Создаёт запись NotificationAttempt и планирует доставку в очередь.

        Args:
            task: Задача, для которой создаётся уведомление.
            channel: Канал доставки (`NotificationAttempt.CHANNEL_*`).
            celery_task: Celery-задача, которую нужно запустить.
            delivery_kwargs: Аргументы будущего вызова Celery-задачи.
            tasks_to_delay: Список, в который копятся отложенные вызовы.

        Returns:
            bool: True, если попытка создана и запланирована к отправке.
        """
        # Повторно брать в работу нельзя, пока по каналу для ЭТОГО наступления
        # (scheduled_for) есть либо уже доставленное уведомление, либо
        # незавершённая попытка (pending), которая может доставить его в ходе
        # собственного retry. Привязка к scheduled_for позволяет periodic-задаче
        # отправить уведомление заново после сдвига reminder_at.
        has_active_attempt = NotificationAttempt.objects.filter(
            task=task,
            channel=channel,
            scheduled_for=task.reminder_at,
            status__in=(
                NotificationAttempt.STATUS_PENDING,
                NotificationAttempt.STATUS_SENT,
            ),
        ).exists()

        if has_active_attempt:
            logger.info(f"  → {channel}: активная попытка уже есть, пропускаем")
            return False

        attempt = NotificationAttempt.objects.create(
            task=task,
            channel=channel,
            status=NotificationAttempt.STATUS_PENDING,
            scheduled_for=task.reminder_at,
        )

        # Вместо .delay() складываем параметры в список для on_commit
        tasks_to_delay.append((
            celery_task,
            {
                "attempt_id": attempt.id,
                **delivery_kwargs,
            },
        ))
        logger.info(f"  → {channel}: попытка {attempt.id} запланирована к отправке")
        return True

    def _check_and_set_dynamic_overdue(self) -> int:
        """Контролирует, фиксирует и записывает просрочку активных напоминаний.

        Метод сканирует все задачи со статусом IN_PROGRESS, динамически извлекает
        из словаря OVERDUE_TIMEOUTS соответствующий лимит времени на реакцию для
        каждой единицы периодичности и переводит задачи, превысившие этот лимит,
        в статус OVERDUE. Для периодических задач дополнительно сдвигает
        ``reminder_at`` на следующее наступление по сетке периода, замыкая цикл.

        Returns:
            int: Количество задач, признанных просроченными за текущую итерацию.
        """
        # reminder_at nullable, а у задачи без напоминания нечего сравнивать
        # с дедлайном. Без этой фильтрации получим TypeError на None + timedelta
        # и упадёт весь планировщик, а не одна задача.
        active_tasks = Task.objects.filter(
            status_flag=StatusChoices.IN_PROGRESS,
            reminder_at__isnull=False,
        )
        overdue_tasks_ids = []

        for task in active_tasks:
            timeout_delta = OVERDUE_TIMEOUTS.get(
                task.periodicity_unit, OVERDUE_TIMEOUTS["none"]
            )
            deadline_time = task.reminder_at + timeout_delta

            if self.now > deadline_time:
                update_fields = ["status_flag", "status_changed_at"]

                task.status_flag = StatusChoices.OVERDUE
                task.status_changed_at = self.now

                # Для периодической задачи сразу закрываем наступление и
                # возвращаем reminder_at в будущее, иначе цикл застрянет.
                # Из статуса OVERDUE повторно время не сдвигается: close_occurrence
                # проверяет, что reminder_at <= now, а после сдвига это уже не так.
                if close_occurrence(task, self.now):
                    update_fields.append("reminder_at")

                task.save(update_fields=update_fields)

                logger.warning(
                    f"== [ПРОСРОЧКА] Задача ID {task.id} превысила лимит "
                    f"на реакцию ({timeout_delta}) =="
                )

                overdue_tasks_ids.append(task.id)

        return len(overdue_tasks_ids)
