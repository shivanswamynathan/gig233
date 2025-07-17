from django.urls import path
from ..views import check_views

urlpatterns = [
    path("check-pending/",
         check_views.ApprovedReconciliationAPI.as_view(), name="check_pending"),
    path("check-approval/", check_views.CheckApprovalAPI.as_view(),
         name="check_approval"),
    path("check-approved/", check_views.CheckListAPI.as_view(),
         name="check_approved"),
]
