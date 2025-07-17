from django.urls import path
from ..views import views, manually_enter_views, upload_key_views, invoice_views

urlpatterns = [
    path("process-invoice/", views.ProcessInvoiceAPI.as_view(),
         name="process_invoice"),
    path("invoice/manual-entry/",
         manually_enter_views.ManuallyEnterInvoiceAPI.as_view(), name="manual_invoice_entry"),
    path("upload-history/", upload_key_views.UploadHistoryListAPI.as_view(),
         name="upload_history_list"),
    path("processed-invoices/",
         invoice_views.ProcessedInvoiceListAPI.as_view(), name="processed_invoices"),
    path("missing-invoices/",
         invoice_views.MissingInvoiceListAPI.as_view(), name="missing_invoices"),
    path("ocr-issues/", invoice_views.OCRIssuesListAPI.as_view(), name="ocr_issues"),
]
