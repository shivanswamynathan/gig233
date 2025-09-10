from django.urls import path

from ..views.upload import po_grn_views
from ..views.upload import itemwise_grn_views
from ..views.upload import missing_data_checkere

urlpatterns = [
    path("process-po-grn/", po_grn_views.ProcessPoGrnAPI.as_view(),
         name="process_po_grn"),
    path("process-itemwise-grn/",
         itemwise_grn_views.ProcessItemWiseGrnAPI.as_view(), name="process_itemwise_grn"),
     path("check-missing-data/",missing_data_checkere.CheckMissingDataAPI.as_view(),
         name="check_missing_data"),
]
