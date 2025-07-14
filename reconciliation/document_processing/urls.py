from django.urls import path
from .views import views,po_grn_views,itemwise_grn_views,attachment_api_views,invoice_recon_views,manually_enter_views, upload_key_views, invoice_views,check_views

app_name = 'document_processing'

urlpatterns = [
    path('api/process-invoice/', views.ProcessInvoiceAPI.as_view(), name='process_invoice'),

    # PO-GRN data processing
    path('api/process-po-grn/', po_grn_views.ProcessPoGrnAPI.as_view(), name='process_po_grn'),

    # Item-wise GRN data processing
    path('api/process-itemwise-grn/', itemwise_grn_views.ProcessItemWiseGrnAPI.as_view(), name='process_itemwise_grn'),

    # Process ItemWiseGRN file and automatically extract attachments
    path('api/process-grn-file-and-attachments/', attachment_api_views.ProcessItemWiseGRNAndAttachmentsAPI.as_view(), name='process_grn_file_and_attachments'),

    # Process attachments from GRN table
    path('api/process-attachments-from-grn-table/', attachment_api_views.ProcessAttachmentsFromGrnTableAPI.as_view(), name='process_attachments_from_grn_table'),

    path('api/reconciliation/', invoice_recon_views.RuleBasedReconciliationAPI.as_view(), name='reconciliation'),
    

    # Manually enter invoice data as JSON
    path('api/invoice/manual-entry/', manually_enter_views.ManuallyEnterInvoiceAPI.as_view(), name='manual_invoice_entry'),
    
    # Upload history API
    path('api/upload-history/', upload_key_views.UploadHistoryListAPI.as_view(), name='upload_history_list'),

    # Processed invoice list API
    path('api/processed-invoices/', invoice_views.ProcessedInvoiceListAPI.as_view(), name='processed_invoices'),

    # Missing invoice list API
    path('api/missing-invoices/', invoice_views.MissingInvoiceListAPI.as_view(), name='missing_invoices'),

    # OCR issues list API
    path('api/ocr-issues/', invoice_views.OCRIssuesListAPI.as_view(), name='ocr_issues'),

    path('api/check-pending/', check_views.ApprovedReconciliationAPI.as_view(), name='check-pending'),
]
