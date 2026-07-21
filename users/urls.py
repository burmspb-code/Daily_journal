from views import


# Пространство имен для URL-адресов приложения
app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
]