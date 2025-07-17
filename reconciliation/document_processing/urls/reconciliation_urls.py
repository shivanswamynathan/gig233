from django.urls import path
from ..views import invoice_recon_views, match_views

urlpatterns = [
    path("reconciliation/",
         invoice_recon_views.RuleBasedReconciliationAPI.as_view(), name="reconciliation"),
    path("status-approval/",
         match_views.ReconciliationApprovalAPI.as_view(), name="status_approval"),
    path("reconciliation-match/",
          match_views.ReconciliationDetailAPI.as_view(), name='reconciliation_match_detail'),     
]
