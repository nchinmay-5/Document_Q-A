"""Every route in the application, in one place."""
from django.contrib import admin
from django.urls import path
from rest_framework.routers import DefaultRouter

from documents.views import DocumentViewSet
from qa.views import AskView
from users.views import LoginView, LogoutView, RegisterView

# Gives /api/documents/ (list, upload) and /api/documents/<id>/ (read, delete).
router = DefaultRouter()
router.register("api/documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/qa/ask/", AskView.as_view(), name="ask"),
    *router.urls,
]
