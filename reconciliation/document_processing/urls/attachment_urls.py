from django.urls import path
from ..views.reconciliation import attachment_api_views

urlpatterns = [
    path(
        "process-grn-file-and-attachments/",
        attachment_api_views.ProcessItemWiseGRNAndAttachmentsAPI.as_view(),
        name="process_grn_file_and_attachments",
    ),
    path(
        "process-attachments-from-grn-table/",
        attachment_api_views.ProcessAttachmentsFromGrnTableAPI.as_view(),
        name="process_attachments_from_grn_table",
    ),
]
