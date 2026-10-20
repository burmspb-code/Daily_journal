"""Тесты критичных сценариев приложения daily.

Покрывают лимиты тарифов, фильтрацию задач, инлайн-обновление статуса,
изоляцию пользовательских данных, контракт API и конвейер уведомлений Celery.
"""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from daily.models import Bookmark, NotificationAttempt, Task
from daily.serializers import TaskUpdateSerializer
from daily.services import ReminderNotificationService, TaskService
from daily.tasks import check_daily_reminders
from tests.factories import BookmarkFactory, TaskFactory

# =============================================================================
# СОЗДАНИЕ ЗАДАЧ И ЛИМИТЫ ТАРИФА
# =============================================================================


@pytest.mark.django_db
def test_task_create_view_creates_task_for_current_user(auth_client, user):
    bookmark = BookmarkFactory(owner=user)

    response = auth_client.post(
        reverse("daily:task_create"),
        data=json.dumps({"title": "  Новая задача  ", "bookmark_id": bookmark.id}),
        content_type="application/json",
    )

    assert response.status_code == 200

    task = Task.objects.get(title="Новая задача")
    assert task.owner == user
    assert task.bookmark == bookmark


@pytest.mark.django_db
def test_task_create_view_enforces_tariff_limit(auth_client, user):
    bookmark = BookmarkFactory(owner=user)
    limit = user.tariff_plan.max_tasks
    TaskFactory.create_batch(limit, bookmark=bookmark, owner=user)

    response = auth_client.post(
        reverse("daily:task_create"),
        data=json.dumps({"title": "Сверх лимита", "bookmark_id": bookmark.id}),
        content_type="application/json",
    )

    assert response.json()["status"] == "limit_error"
    assert Task.objects.filter(bookmark=bookmark).count() == limit


@pytest.mark.django_db
def test_task_create_view_requires_existing_bookmark(auth_client, user):
    BookmarkFactory(owner=user)

    response = auth_client.post(
        reverse("daily:task_create"),
        data=json.dumps({"title": "Без закладки", "bookmark_id": 999_999}),
        content_type="application/json",
    )

    assert response.status_code == 404


# =============================================================================
# ЗАКЛАДКИ
# =============================================================================


@pytest.mark.django_db
def test_bookmark_create_view_enforces_tariff_limit(auth_client, user):
    limit = user.tariff_plan.max_bookmarks
    BookmarkFactory.create_batch(limit, owner=user)

    response = auth_client.post(
        reverse("daily:bookmark_create"),
        {"title": "Лишняя", "description": "Не должна создаться"},
    )

    assert response.status_code == 200
    assert Bookmark.objects.filter(owner=user).count() == limit


@pytest.mark.django_db
def test_bookmark_create_view_creates_bookmark(auth_client, user):
    response = auth_client.post(
        reverse("daily:bookmark_create"),
        {"title": "Новая закладка", "description": "Описание"},
    )

    assert response.status_code == 302
    assert Bookmark.objects.filter(owner=user, title="Новая закладка").exists()


# =============================================================================
# СЕРВИСНЫЙ СЛОЙ: ФИЛЬТРАЦИЯ, СОРТИРОВКА, ИЗОЛЯЦИЯ
# =============================================================================


@pytest.mark.django_db
def test_task_service_filters_sorts_and_isolates_users(user, other_user):
    bookmark = BookmarkFactory(owner=user)
    alpha = TaskFactory(bookmark=bookmark, owner=user, title="Альфа")
    beta = TaskFactory(bookmark=bookmark, owner=user, title="Бета")

    foreign_bookmark = BookmarkFactory(owner=other_user)
    TaskFactory(bookmark=foreign_bookmark, owner=other_user, title="Чужая задача")

    sorted_context = TaskService.get_task_list_context(user, {"sort": "name_asc"})
    assert [task.title for task in sorted_context["tasks"]] == ["Альфа", "Бета"]
    assert [item.id for item in sorted_context["bookmarks"]] == [bookmark.id]

    # Подстрока без различий в регистре: результат одинаков и на SQLite, и на PostgreSQL.
    filtered_context = TaskService.get_task_list_context(user, {"title": "льф"})
    assert list(filtered_context["tasks"]) == [alpha]

    # Чужой ID закладки игнорируется — показывается первая закладка пользователя.
    foreign_context = TaskService.get_task_list_context(
        user, {"bookmark": str(foreign_bookmark.id)}
    )
    assert foreign_context["current_bookmark"] == bookmark
    assert beta in list(foreign_context["tasks"])


@pytest.mark.django_db
def test_task_service_filters_by_status_flag(user):
    bookmark = BookmarkFactory(owner=user)
    TaskFactory(bookmark=bookmark, owner=user)
    completed = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.COMPLETED,
    )

    context = TaskService.get_task_list_context(
        user, {"flag": str(Task.StatusChoices.COMPLETED)}
    )

    assert list(context["tasks"]) == [completed]


# =============================================================================
# API: КОНТРАКТ ОТВЕТА
# =============================================================================


@pytest.mark.django_db
def test_task_list_api_returns_meta_and_tasks(auth_client, user):
    """Фронтенд (status-polling.js) ожидает results.meta и results.tasks."""
    bookmark = BookmarkFactory(owner=user)
    TaskFactory(bookmark=bookmark, owner=user, title="Проверка API")

    response = auth_client.get(reverse("daily:task_list_api"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]["meta"]["bookmarks"][0]["title"] == bookmark.title
    assert [task["title"] for task in payload["results"]["tasks"]] == ["Проверка API"]


@pytest.mark.django_db
def test_task_list_api_requires_authentication(client):
    response = client.get(reverse("daily:task_list_api"))

    assert response.status_code in (401, 403)


# =============================================================================
# ИНЛАЙН-ОБНОВЛЕНИЕ СТАТУСА
# =============================================================================


@pytest.mark.django_db
def test_status_update_allows_only_completed_transition(auth_client, user):
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(bookmark=bookmark, owner=user)

    forbidden = auth_client.post(
        reverse("daily:update_task_status"),
        {"task_id": task.id, "status_flag": Task.StatusChoices.IN_PROGRESS},
    )
    assert forbidden.status_code == 400

    allowed = auth_client.post(
        reverse("daily:update_task_status"),
        {"task_id": task.id, "status_flag": Task.StatusChoices.COMPLETED},
    )
    assert allowed.status_code == 200

    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.COMPLETED
    assert task.status_changed_at is not None

    repeated = auth_client.post(
        reverse("daily:update_task_status"),
        {"task_id": task.id, "status_flag": Task.StatusChoices.COMPLETED},
    )
    assert repeated.status_code == 400


@pytest.mark.django_db
def test_task_update_serializer_rejects_non_completed_status(user):
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(bookmark=bookmark, owner=user)

    serializer = TaskUpdateSerializer(
        task,
        data={"status_flag": Task.StatusChoices.IN_PROGRESS},
        partial=True,
    )

    assert serializer.is_valid() is False
    assert "status_flag" in serializer.errors


# =============================================================================
# СБРОС СТАТУСА ПРИ ИЗМЕНЕНИИ НАПОМИНАНИЯ
# =============================================================================


def modal_payload(task, reminder_at):
    """Данные формы модального окна (см. editing-in-modal-window.js)."""
    return {
        "id": task.id,
        "title": task.title,
        "comment": task.comment,
        "reminder_at": reminder_at,
        "periodicity_value": "",
        "periodicity_unit": "none",
    }


@pytest.mark.django_db
def test_changing_reminder_resets_status_to_created(auth_client, user):
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.COMPLETED,
    )
    new_reminder = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")

    response = auth_client.post(
        reverse("daily:task_update"), modal_payload(task, new_reminder)
    )

    assert response.status_code == 200
    assert response.json()["task"]["status"] == Task.StatusChoices.CREATED

    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.CREATED
    assert task.status_changed_at is not None
    assert task.reminder_at is not None


@pytest.mark.django_db
def test_removing_reminder_resets_status_to_created(auth_client, user):
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.IN_PROGRESS,
        reminder_at=timezone.now() + timedelta(hours=2),
    )

    response = auth_client.post(reverse("daily:task_update"), modal_payload(task, ""))

    assert response.status_code == 200

    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.CREATED
    assert task.reminder_at is None
    assert task.periodicity_unit == "none"


@pytest.mark.django_db
def test_saving_without_reminder_change_keeps_status(auth_client, user):
    """Сохранение модалки без правки времени не должно сбрасывать статус."""
    reminder = (timezone.now() + timedelta(hours=3)).replace(second=0, microsecond=0)
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.IN_PROGRESS,
        reminder_at=reminder,
    )

    response = auth_client.post(
        reverse("daily:task_update"),
        modal_payload(task, timezone.localtime(reminder).strftime("%Y-%m-%dT%H:%M")),
    )

    assert response.status_code == 200
    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.IN_PROGRESS


@pytest.mark.django_db
def test_inline_reminder_change_resets_status_to_created(auth_client, user):
    """Инлайн-календарь шлёт только id и reminder_at (editing-reminder-time.js)."""
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.OVERDUE,
    )
    new_reminder = (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")

    response = auth_client.post(
        reverse("daily:task_update"), {"id": task.id, "reminder_at": new_reminder}
    )

    assert response.status_code == 200
    assert response.json()["task"]["status"] == Task.StatusChoices.CREATED

    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.CREATED
    assert task.status_changed_at is not None


@pytest.mark.django_db
def test_inline_reminder_removal_resets_status_to_created(auth_client, user):
    """Очистка инлайн-календаря снимает напоминание, периодичность и статус."""
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.IN_PROGRESS,
        reminder_at=timezone.now() + timedelta(hours=2),
        periodicity_value=1,
        periodicity_unit="days",
    )

    response = auth_client.post(
        reverse("daily:task_update"), {"id": task.id, "reminder_at": ""}
    )

    assert response.status_code == 200

    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.CREATED
    assert task.reminder_at is None
    assert task.periodicity_unit == "none"
    assert task.periodicity_value is None


@pytest.mark.django_db
def test_inline_title_and_comment_edit_keeps_status(auth_client, user):
    """Инлайн-правка названия и комментария статус не трогает."""
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.IN_PROGRESS,
        status_changed_at=timezone.now() - timedelta(days=1),
    )
    changed_at = task.status_changed_at

    auth_client.post(
        reverse("daily:task_update"), {"id": task.id, "title": "Инлайн-название"}
    )
    auth_client.post(
        reverse("daily:task_update"), {"id": task.id, "comment": "Инлайн-комментарий"}
    )

    task.refresh_from_db()
    assert task.title == "Инлайн-название"
    assert task.comment == "Инлайн-комментарий"
    assert task.status_flag == Task.StatusChoices.IN_PROGRESS
    assert task.status_changed_at == changed_at


@pytest.mark.django_db
def test_inline_periodicity_change_keeps_status(auth_client, user):
    """Инлайн-правка периодичности идёт в отдельный View и статус не сбрасывает."""
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.IN_PROGRESS,
    )

    response = auth_client.post(
        reverse("daily:update_task_periodicity"),
        {"task_id": task.id, "periodicity_value": 3, "periodicity_unit": "days"},
    )

    assert response.status_code == 200
    task.refresh_from_db()
    assert task.periodicity_unit == "days"
    assert task.periodicity_value == 3
    assert task.status_flag == Task.StatusChoices.IN_PROGRESS


# =============================================================================
# ИЗОЛЯЦИЯ ДАННЫХ ПРИ УДАЛЕНИИ
# =============================================================================


@pytest.mark.django_db
def test_task_delete_removes_only_own_tasks(auth_client, user, other_user):
    own_task = TaskFactory(bookmark=BookmarkFactory(owner=user), owner=user)
    foreign_task = TaskFactory(
        bookmark=BookmarkFactory(owner=other_user), owner=other_user
    )

    response = auth_client.post(
        reverse("daily:task_delete"),
        data=json.dumps({"task_ids": [own_task.id, foreign_task.id]}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert not Task.objects.filter(pk=own_task.pk).exists()
    assert Task.objects.filter(pk=foreign_task.pk).exists()


# =============================================================================
# КОНВЕЙЕР УВЕДОМЛЕНИЙ (CELERY)
# =============================================================================


@pytest.mark.django_db
def test_reminder_pipeline_enqueues_attempts_without_duplicates(
    django_capture_on_commit_callbacks, user
):
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        reminder_at=timezone.now() - timedelta(minutes=1),
    )
    service = ReminderNotificationService()

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        processed = service._process_new_reminders()

    assert processed == 1
    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.IN_PROGRESS
    assert len(callbacks) == 1

    attempt = NotificationAttempt.objects.get(
        task=task, channel=NotificationAttempt.CHANNEL_EMAIL
    )
    assert attempt.status == NotificationAttempt.STATUS_PENDING

    # Повторный запуск не должен создавать вторую попытку доставки.
    with django_capture_on_commit_callbacks(execute=False):
        assert service._process_new_reminders() == 0
    assert NotificationAttempt.objects.filter(task=task).count() == 1


@pytest.mark.django_db
def test_overdue_detection_marks_tasks_overdue(user):
    bookmark = BookmarkFactory(owner=user)
    task = TaskFactory(
        bookmark=bookmark,
        owner=user,
        status_flag=Task.StatusChoices.IN_PROGRESS,
        reminder_at=timezone.now() - timedelta(hours=2),
        periodicity_unit="none",
    )

    overdue_count = ReminderNotificationService()._check_and_set_dynamic_overdue()

    assert overdue_count == 1
    task.refresh_from_db()
    assert task.status_flag == Task.StatusChoices.OVERDUE
    assert task.status_changed_at is not None


@pytest.mark.django_db
def test_check_daily_reminders_task_returns_report(user):
    report = check_daily_reminders()

    assert "Обработка завершена успешно" in report
