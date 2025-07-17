from django.urls import path
from ..views import po_grn_views, itemwise_grn_views

urlpatterns = [
    path("process-po-grn/", po_grn_views.ProcessPoGrnAPI.as_view(),
         name="process_po_grn"),
    path("process-itemwise-grn/",
         itemwise_grn_views.ProcessItemWiseGrnAPI.as_view(), name="process_itemwise_grn"),
]
