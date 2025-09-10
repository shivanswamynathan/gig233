from django.urls import path

from ..views.match import invoice_views, manually_enter_views

from ..views.sync import upload_key_views
from ..views.match import views

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

    path("boe-extractions/",
         invoice_views.BoeExtractionAPI.as_view(), name="boe_extractions"),

    path("fetch-data/",
          invoice_views.FetchDataAPI.as_view(), name="fetch_data"),
    path("duplicate-invoices/",
         invoice_views.DuplicateInvoiceAPI.as_view(), name="duplicate_invoices"),
    path("duplicate-invoice-flag/",invoice_views.DuplicateInvoiceFlagAPI.as_view(), name="duplicate_invoice_flag"),

    path("duplicate-issue/",
          invoice_views.DuplicateIssuesAPI.as_view(), name="duplicate_issue"),
]
