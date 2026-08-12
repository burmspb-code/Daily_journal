"""
Сериализаторы основного приложения (daily) для Django REST Framework.
"""

from rest_framework import serializers
from .models import Task, Bookmark


class TaskSerializer(serializers.ModelSerializer):
    # Выводим человекочитаемое имя закладки (read_only=True означает, что поле только для чтения)
    bookmark_title = serializers.CharField(
        source="bookmark.title", read_only=True
    )
    owner_username = serializers.CharField(
        source="owner.username", read_only=True
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
            "bookmark_title",
            "owner_username",
        ]


class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = '__all__'