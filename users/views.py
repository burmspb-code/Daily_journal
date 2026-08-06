# users/views.py
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, TemplateView, View

from rest_framework import exceptions, status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .forms import CustomUserCreateForm
from .models import CustomUser
from .serializers import EmailVerificationSerializer, UserRegisterSerializer
from .services import (
    EmailActivationError,
    InvalidActivationToken,
    activate_user_by_token,
    register_inactive_user,
)


class UserRegisterView(CreateView):
    """Представление для регистрации нового пользователя через веб-форму."""

    model = CustomUser
    form_class = CustomUserCreateForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:email_confirmation_sent")

    def form_valid(self, form):
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


class UserRegisterAPIView(CreateAPIView):
    """Представление для регистрации нового пользователя через API."""

    queryset = CustomUser.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
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
