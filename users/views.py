"""
Модуль представлений (views) приложения управления пользователями (users).

Содержит контроллеры для аутентификации, авторизации и регистрации
пользователей на основе кастомной модели CustomUser. Реализует логику
валидации регистрационных данных, интеграцию с сервисами капчи
и перенаправление пользователей на этапы подтверждения учетных записей.
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.generic import CreateView, TemplateView, View

from .forms import CustomUserCreateForm
from .models import CustomUser


class UserRegisterView(CreateView):
    """Представление для регистрации нового пользователя."""
    model = CustomUser
    form_class = CustomUserCreateForm
    template_name = 'users/register.html'
    success_url = reverse_lazy("users:email_confirmation_sent")

    def form_valid(self, form):
        """
        Обрабатывает успешную валидацию формы регистрации.

        Внутри изолированной атомарной транзакции метод создает неактивного
        пользователя, генерирует уникальный токен подтверждения (UIDB64 и Token)
        и отправляет письмо со ссылкой для активации аккаунта.

        Если отправка письма завершается ошибкой (сбоем SMTP), транзакция полностью
        откатывается, пользователь удаляется из БД, а на форму выводится
        соответствующее уведомление.

        Args:
            form (CustomUserCreateForm): Валидированная форма регистрации.

        Returns:
            HttpResponse: Перенаправление на страницу успешной отправки при успехе,
            либо возврат страницы с формой и ошибками при сбое отправки.
        """
        with transaction.atomic():
            # Создаем неактивного пользователя
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # Генерируем uid и токен
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            # Собираем ссылку активации
            relative_url = reverse(
                "users:email_confirm", kwargs={"uidb64": uid, "token": token}
            )
            scheme = "https" if self.request.is_secure() else "http"
            host = self.request.get_host()
            activation_url = f"{scheme}://{host}{relative_url}"

            try:
                # Отправляем письмо с обязательной генерацией исключения при сбое
                send_mail(
                    subject="Подтверждение регистрации",
                    message=f"Спасибо за регистрацию! Ссылка для активации: {activation_url}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                # Если отправка прошла успешно, перенаправляем на success_url
                return redirect(self.success_url)

            except Exception:
                # Показываем понятную ошибку пользователю на фронтенде
                messages.error(
                    self.request,
                    "Произошла ошибка при отправке письма с подтверждением. "
                    "Пожалуйста, проверьте правильность ввода email или попробуйте позже.",
                )

                # Отменяем сохранение пользователя в базе данных
                transaction.set_rollback(True)

                # Возвращаем пользователя на форму с сохраненными данными полей
                return self.render_to_response(self.get_context_data(form=form))


class EmailConfirmView(View):
    """Представление для активации аккаунта по uid и токену."""

    def get(self, request, uidb64, token):
        """
        Обрабатывает GET-запрос для активации учетной записи пользователя.

        Декодирует идентификатор пользователя (uidb64) и проверяет валидность
        переданного токена с помощью `default_token_generator`. При успешной проверке
        активирует аккаунт, обновляет статус электронной почты и перенаправляет
        на страницу аутентификации с предустановленным email в GET-параметрах.

        В случае невалидного токена, истечения срока его действия или отсутствия
        пользователя отображает страницу с уведомлением об ошибке активации.

        Args:
            request (HttpRequest): Объект текущего HTTP-запроса.
            uidb64 (str): Закодированный в Base64 первичный ключ (ID) пользователя.
            token (str): Уникальный одноразовый токен подтверждения.

        Returns:
            HttpResponse: Перенаправление (302) на страницу логина при успехе,
            либо рендеринг страницы с ошибкой (200) при неудачной активации.
        """
        try:
            # Используем корректное имя модели CustomUser вместо User
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            user = None

        # Проверяем, существует ли пользователь и валиден ли токен (не истек ли срок)
        if user is not None and default_token_generator.check_token(user, token):
            user.is_active = True
            user.email_status = "verified"  # Меняем статус почты
            user.save()

            # Добавляем красивое уведомление, которое отобразится на странице входа
            messages.success(
                request,
                "Ваш аккаунт успешно активирован! Пожалуйста, войдите в систему.",
            )

            # Формируем URL для страницы входа с GET-параметром email
            login_url = reverse("users:login")
            return redirect(f"{login_url}?email={user.email}")
        else:
            # Если токен устарел или неверный, показываем страницу с ошибкой
            return render(request, "users/email_confirmation_failed.html")


class EmailConfirmationSentView(TemplateView):
    """Статическая страница с уведомлением об отправке письма."""

    template_name = 'users/email_confirmation_sent.html'
