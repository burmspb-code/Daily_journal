"""Представления для регистрации, проверки подлинности и управления профилем пользователя."""

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import update_last_login
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.generic import CreateView, FormView, TemplateView, UpdateView, View
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view, inline_serializer
from rest_framework import exceptions, serializers, status
from rest_framework.generics import CreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView as SimpleJWTTokenObtainPairView

from .forms import CustomPasswordResetForm, CustomUserCreateForm, ResendActivationForm, UserProfileForm
from .models import CustomUser
from .serializers import (
    EmailVerificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegisterSerializer,
    UserSerializer,
)
from .services import (
    EmailActivationError,
    InvalidActivationToken,
    activate_user_by_token,
    register_inactive_user,
    resend_activation_email,
    send_password_reset_mail,
)

User = get_user_model()

logger = logging.getLogger(__name__)


# ========================= Представления для веб-интерфейса ===============================================


class UserRegisterView(CreateView):
    """Представление для регистрации пользователя на основе класса CreateView."""

    model = CustomUser
    form_class = CustomUserCreateForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:email_confirmation_sent")

    def get_context_data(self, **kwargs):
        """Добавляет класс is-invalid к полям с ошибками после валидации."""
        context = super().get_context_data(**kwargs)
        if "form" in kwargs and kwargs["form"].errors:
            kwargs["form"].add_is_invalid_class()
        return context

    def form_valid(self, form):
        """
        Регистрирует пользователя в статусе 'inactive' и отправляет письмо активации.
        """
        try:
            register_inactive_user(self.request, save_callback=form.save)
            return redirect(self.success_url)
        except EmailActivationError as e:
            messages.error(
                self.request,
                f"{e} Если вы уже регистрировались, попробуйте запросить повторную отправку ссылки активации.",
            )
            return self.render_to_response(self.get_context_data(form=form))


class EmailConfirmationSentView(TemplateView):
    """Страница с сообщением об отправке письма для подтверждения email."""

    template_name = "users/email_confirmation_sent.html"


class EmailConfirmView(View):
    """Веб-представление для активации аккаунта по ссылке из письма."""

    def get(self, request, uidb64, token):
        try:
            user = activate_user_by_token(uidb64, token)
        except InvalidActivationToken as e:
            messages.error(request, str(e))
            return redirect("users:login")

        messages.success(request, "Ваш аккаунт успешно активирован! Теперь вы можете войти.")
        return redirect(f"{reverse('users:login')}?email={user.email}")


class ResendActivationView(FormView):
    """Представление для повторной отправки письма активации."""

    template_name = "users/resend_activation.html"
    form_class = ResendActivationForm
    success_url = reverse_lazy("users:email_confirmation_sent")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        resend_activation_email(self.request, email)
        return super().form_valid(form)


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Представление для редактирования профиля авторизованного пользователя."""

    model = CustomUser
    form_class = UserProfileForm
    template_name = "users/profile.html"
    success_url = reverse_lazy("users:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Профиль успешно обновлен.")
        return super().form_valid(form)


class WebPasswordResetView(auth_views.PasswordResetView):
    """Кастомный PasswordResetView, использующий Cloud Function вместо SMTP."""

    template_name = "users/password_reset.html"
    form_class = CustomPasswordResetForm
    success_url = reverse_lazy("users:password_reset_done")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        logger.info(f"[PWD_RESET_WEB] Запрос на сброс пароля для email={email}")
        users = list(form.get_users(email))
        logger.info(f"[PWD_RESET_WEB] Найдено пользователей: {len(users)}")
        for user in users:
            try:
                logger.info(
                    f"[PWD_RESET_WEB] Вызов send_password_reset_mail для user_id={user.pk}, email={user.email}, is_active={user.is_active}"
                )
                send_password_reset_mail(self.request, user)
                logger.info(f"[PWD_RESET_WEB] Успешно отправлено для user_id={user.pk}")
            except EmailActivationError:
                logger.exception(f"[PWD_RESET_WEB] EmailActivationError при отправке для user_id={user.pk}")
            except Exception:
                logger.exception(f"[PWD_RESET_WEB] Неожиданная ошибка при отправке для user_id={user.pk}")
        return HttpResponseRedirect(self.get_success_url())


# ========================= API-представления (DRF) ===============================================


@extend_schema_view(
    post=extend_schema(
        summary="Регистрация пользователя",
        description="Создает неактивного пользователя и отправляет письмо с ссылкой активации.",
        request=UserRegisterSerializer,
        responses={
            201: OpenApiResponse(description="Письмо с подтверждением отправлено."),
            400: OpenApiResponse(description="Ошибка валидации данных."),
        },
        tags=["Аутентификация"],
    )
)
class UserRegisterAPIView(CreateAPIView):
    """API-представление для регистрации нового пользователя."""

    permission_classes = [AllowAny]
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            register_inactive_user(request, save_callback=serializer.save)
        except EmailActivationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"detail": "Письмо с подтверждением отправлено на указанный email."},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary="Подтверждение Email через API",
    description="Принимает uidb64 и token из письма в JSON и переводит аккаунт пользователя в статус 'активен'.",
    request=EmailVerificationSerializer,
    responses={
        200: inline_serializer(
            name="EmailVerificationSuccessResponse",
            fields={"detail": serializers.CharField(default="Аккаунт успешно активирован.")},
        ),
        400: inline_serializer(
            name="EmailVerificationFailedResponse",
            fields={"detail": serializers.CharField(default="Неверный или истекший токен.")},
        ),
    },
    tags=["Аутентификация"],
)
class UserVerifyEmailAPIView(APIView):
    """API-представление для подтверждения email пользователя по токену."""

    permission_classes = [AllowAny]
    serializer_class = EmailVerificationSerializer

    def post(self, request, *_, **__):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            activate_user_by_token(
                uidb64=serializer.validated_data["uidb64"],
                token=serializer.validated_data["token"],
            )
        except InvalidActivationToken as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Аккаунт успешно активирован."}, status=status.HTTP_200_OK)


class UserTokenObtainPairView(SimpleJWTTokenObtainPairView):
    """Кастомное представление для получения JWT-токенов."""

    permission_classes = [AllowAny]
    serializer_class = TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_last_login(None, serializer.user)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    summary="Получение и обновление профиля текущего пользователя",
    description="Возвращает данные текущего аутентифицированного пользователя. Поддерживает частичное обновление через PATCH.",
    tags=["Профиль"],
)
class UserMeAPIView(RetrieveUpdateDestroyAPIView):
    """API для работы с профилем текущего пользователя."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UserSerializer
        return UserSerializer


@extend_schema(
    summary="Запрос на сброс пароля",
    description="Принимает email пользователя. Если аккаунт существует, отправляет письмо со ссылкой для сброса пароля.",
    request=PasswordResetRequestSerializer,
    responses={
        200: inline_serializer(
            name="PasswordResetRequestResponse",
            fields={"detail": serializers.CharField(default="Если этот адрес зарегистрирован в системе, на него отправлено письмо.")},
        ),
    },
    tags=["Аутентификация"],
)
class UserPasswordResetAPIView(APIView):
    """API-представление для запроса сброса пароля."""

    permission_classes = [AllowAny]

    def post(self, request, *_, **__):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
            send_password_reset_mail(request, user)
        except User.DoesNotExist:
            pass
        except EmailActivationError:
            logger.exception("Ошибка отправки письма сброса пароля")
            pass

        return Response(
            {"detail": "Если этот адрес зарегистрирован в системе, на него отправлено письмо."},
            status=status.HTTP_200_OK,
        )


@extend_schema(exclude=True)
class UserPasswordResetConfirmAPIView(APIView):
    """API-представление для подтверждения сброса пароля по токену."""

    permission_classes = [AllowAny]

    def post(self, request, *_, **__):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.context["user"]
        new_password = serializer.validated_data["new_password"]

        user.set_password(new_password)
        user.save()

        return Response(
            {"detail": "Пароль успешно изменён. Теперь вы можете войти."},
            status=status.HTTP_200_OK,
        )
