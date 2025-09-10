from django.urls import path, include

app_name = "document_processing"

urlpatterns = [
    path("", include("document_processing.urls.invoice_urls")),
    path("", include("document_processing.urls.grn_urls")),
    path("", include("document_processing.urls.attachment_urls")),
    path("", include("document_processing.urls.reconciliation_urls")),
    path("", include("document_processing.urls.check_urls")),
    path("", include("document_processing.urls.email_urls")),
]
