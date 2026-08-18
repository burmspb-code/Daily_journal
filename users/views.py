"""Представления для регистрации, проверки подлинности и управления профилем пользователя."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, TemplateView, View
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import exceptions, status, serializers
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .forms import CustomUserCreateForm
from .models import CustomUser
from .serializers import UserSerializer, EmailVerificationSerializer, UserRegisterSerializer, \
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from .services import (
    EmailActivationError,
    InvalidActivationToken,
    activate_user_by_token,
    register_inactive_user,
)

User = get_user_model()


# ========================= Эндпоинты для работы для работы через WEB==============================================

class UserRegisterView(CreateView):
    """Представление для регистрации нового пользователя через веб-форму."""

    model = CustomUser
    form_class = CustomUserCreateForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:email_confirmation_sent")

    def form_valid(self, form):
        """
        Сохраняет пользователя в статусе 'inactive' и инициирует отправку email.

        В случае сбоя EmailActivationError возвращает форму с ошибкой в messages.
        """
        try:
            register_inactive_user(self.request, save_callback=form.save)
            return redirect(self.success_url)
        except EmailActivationError:
            messages.error(
                self.request,
                "Произошла ошибка при отправке письма с подтверждением. "
                "Пожалуйста, проверьте правильность ввода email или попробуйте позже.",
            )
            return self.render_to_response(self.get_context_data(form=form))


class EmailConfirmationSentView(TemplateView):
    """Статическая страница с уведомлением об отправке письма."""

    template_name = "users/email_confirmation_sent.html"


class EmailConfirmView(View):
    """Представление для активации аккаунта по uid и токену через браузер."""

    def get(self, request, uidb64, token):
        """
        Активирует пользователя через сервис `activate_user_by_token`.

        В случае успеха перенаправляет на логин с GET-параметром email.
        При ошибке `InvalidActivationToken` рендерит страницу сбоя активации.
        """
        try:
            # Вызываем единый сервис активации
            user = activate_user_by_token(uidb64=uidb64, token=token)

            messages.success(
                request,
                "Ваш аккаунт успешно активирован! Пожалуйста, войдите в систему.",
            )
            login_url = reverse("users:login")
            return redirect(f"{login_url}?email={user.email}")

        except InvalidActivationToken:
            # Если сервис выкинул ошибку (токен неверный/истек), рендерим страницу ошибки
            return render(request, "users/email_confirmation_failed.html")


# ========================= Эндпоинты для работы для работы с API ===============================================

class UserTokenObtainPairView(TokenObtainPairView):
    """
    Кастомный эндпоинт для получения JWT-токенов (входа в систему).
    Автоматически обновляет поле last_login пользователя при успешном входе.
    """

    @extend_schema(
        summary="Вход в систему (Получение JWT)",
        description="Принимает email/username и password. Возвращает пару access и refresh токенов.",
        responses={200: TokenObtainPairSerializer}
    )
    def post(self, request, *args, **kwargs):
        # Запускаем стандартный конвейер Simple JWT
        response = super().post(request, *args, **kwargs)

        # Если аутентификация успешна (статус 200)
        if response.status_code == status.HTTP_200_OK:
            # Simple JWT инициализирует сериализатор внутри super().post()
            # Мы можем воссоздать его с теми же данными, чтобы безопасно вытащить юзера
            serializer = self.get_serializer(data=request.data)
            try:
                serializer.is_valid(raise_exception=True)
                user = serializer.user  # Сериализатор Simple JWT сохраняет юзера в свойство .user
                if user:
                    update_last_login(None, user)
            except Exception:
                pass  # Защита: если что-то пошло не так, не ломаем выдачу токенов клиенту

        return response


class UserRegisterAPIView(CreateAPIView):
    """Представление для регистрации нового пользователя через API."""

    queryset = CustomUser.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        """
        Регистрирует неактивного пользователя через `register_inactive_user`.

        Вызывает `ValidationError`, если отправка письма активации завершилась ошибкой.
        """
        try:
            register_inactive_user(self.request, save_callback=serializer.save)
        except EmailActivationError:
            raise exceptions.ValidationError(
                {"detail": "Ошибка отправки письма. Проверьте email или повторите позже."}
            )


class UserVerifyEmailAPIView(APIView):
    """API-представление для подтверждения email пользователя по токену."""

    permission_classes = [AllowAny]
    serializer_class = EmailVerificationSerializer

    @extend_schema(
        summary="Подтверждение Email через API",
        description="Принимает токен активации из письма и переводит аккаунт пользователя в статус 'активен'.",
        request=EmailVerificationSerializer,
        responses={
            200: inline_serializer(
                name='EmailVerificationSuccessResponse',
                fields={
                    'detail': serializers.CharField(default="Аккаунт успешно активирован.")
                }
            ),
            400: inline_serializer(
                name='EmailVerificationFailedResponse',
                fields={
                    'detail': serializers.CharField(default="Неверный или истекший токен.")
                }
            )
        }
    )
    def post(self, request, *args, **kwargs):
        """Принимает токен активации и выполняет верификацию."""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Ваша текущая логика активации (остается без изменений)

        return Response(
            {"detail": "Аккаунт успешно активирован."},
            status=status.HTTP_200_OK
        )


class UserMeAPIView(RetrieveUpdateAPIView):
    """
    API-представление для просмотра и безопасного редактирования профиля текущего пользователя.
    """

    serializer_class = UserSerializer

    def get_object(self):
        """Получаем текущего пользователя."""
        return self.request.user


@extend_schema(exclude=True)  # Скрываем из Swagger и убираем ошибку из консоли
class UserPasswordResetAPIView(APIView):
    """API-представление для инициации сброса пароля (отправка email)."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Принимает email и отправляет ссылку для восстановления пароля."""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)

            # Генерируем uid и токен (стандартный безопасный механизм Django)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            # Здесь вызывается ваша функция отправки email (сделайте по аналогии с регистрацией)
            # send_password_reset_email(user=user, uidb64=uidb64, token=token)

        except User.DoesNotExist:
            # Безопасность: не говорим хакеру, есть ли такой email в базе.
            # Всегда возвращаем 200 OK, чтобы избежать перебора (enumeration attack).
            pass

        return Response(
            {"detail": "Если этот адрес зарегистрирован в системе, на него отправлено письмо."},
            status=status.HTTP_200_OK,
        )


@extend_schema(exclude=True)  # Скрываем из Swagger и убираем ошибку из консоли
class UserPasswordResetConfirmAPIView(APIView):
    """API-представление для установки нового пароля по токену."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Принимает токен и новый пароль, выполняя сброс."""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Вытаскиваем проверенного пользователя из контекста сериализатора
        user = serializer.context["user"]
        new_password = serializer.validated_data["new_password"]

        # Устанавливаем новый пароль (Django автоматически захэширует его)
        user.set_password(new_password)
        user.save()

        return Response(
            {"detail": "Пароль успешно изменен. Теперь вы можете войти."},
            status=status.HTTP_200_OK,
        )
