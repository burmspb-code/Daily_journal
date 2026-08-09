"""Представления для регистрации, проверки подлинности и управления профилем пользователя."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, TemplateView, View
from rest_framework import exceptions, status
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .forms import CustomUserCreateForm
from .models import CustomUser
from .serializers import UserSerializer, EmailVerificationSerializer, UserRegisterSerializer
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

    def post(self, request, *args, **kwargs):
        """
        Выполняет вход пользователя в систему и генерирует JWT-токены.

        При успешной аутентификации принудительно обновляет поле `last_login`.
        """
        # Запускаем стандартный конвейер валидации логина и пароля
        response = super().post(request, *args, **kwargs)

        # Если статус ответа 200 OK (токены успешно сгенерированы)
        if response.status_code == 200:
            # Находим пользователя в базе по его email/username из запроса
            # Simple JWT сохраняет проверенного пользователя прямо в request.user
            if request.user and request.user.is_authenticated:
                update_last_login(None, request.user)

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
    """Эндпоинт для подтверждения email через API."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Проверяет токен активации email и аутентифицирует пользователя.

        Возвращает access и refresh JWT-токены при успешной верификации.
        Генерирует ошибку 400 Bad Request, если токен невалиден.
        """
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Тот же самый сервис, но для API контроллера
            user = activate_user_by_token(
                uidb64=serializer.validated_data["uidb64"],
                token=serializer.validated_data["token"],
            )

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "detail": "Email успешно подтвержден. Вы вошли в систему.",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )

        except InvalidActivationToken as e:
            raise exceptions.ValidationError({"detail": str(e)})


class UserMeAPIView(RetrieveUpdateAPIView):
    """
    API-представление для просмотра и безопасного редактирования профиля текущего пользователя.
    """

    serializer_class = UserSerializer

    def get_object(self):
        """Получаем текущего пользователя."""
        return self.request.user


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
