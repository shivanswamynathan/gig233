from django.contrib import admin
from django.urls import path, include
from document_processing.views.health_check import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path('health-check/', HealthCheckView.as_view(), name='health-check'),
    path("api/v1/document-processing/", include("document_processing.urls.main")),
    path("api/v1/chatbot/", include("chatbot.urls")),

]
