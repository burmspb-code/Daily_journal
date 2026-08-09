"""
Сериализаторы основного приложения (daily) для Django REST Framework.
"""

from rest_framework import serializers
from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    # Выводим человекочитаемое имя закладки (read_only=True означает, что поле только для чтения)
    bookmark_name = serializers.CharField(
        source="bookmark.name", read_only=True
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "created_at",
            "reminder_at",
            "comment",
            "status_flag",
            "bookmark_name",
            "owner",
        ]
