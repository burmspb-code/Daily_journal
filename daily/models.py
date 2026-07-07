from django.db import models

class Task(models.Model):
    # Столбец B: Наименование контрагента/задачи
    name = models.CharField(
        max_length=255, 
        verbose_name="Наименование"
    )
    
    # Столбец C: Время создания
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Время создания"
    )
    
    # Столбец D: Время напоминания (разрешаем null для строк со звездочкой)
    reminder_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Время напоминания"
    )
    
    # Столбец E: Комментарий к задаче
    comment = models.TextField(
        null=True, 
        blank=True, 
        verbose_name="Комментарий"
    )
    
    # Столбец F: Признак для логики управления данными (по умолчанию 0)
    status_flag = models.IntegerField(
        default=0, 
        verbose_name="Признак управления"
    )

    class Meta:
        db_table = 'tasks'  # Имя таблицы в PostgreSQL
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['id']  # Сортировка по порядку (Столбец A)

    def __str__(self):
        return f"№{self.id} | {self.name} | Флаг: {self.status_flag}"
