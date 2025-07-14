from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from document_processing.models import UploadHistory, ItemWiseGrn
import logging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class UploadHistoryListAPI(View):
    def get(self, request):
        try:
            batch_id = request.GET.get('batch_id')
            histories = UploadHistory.objects.all().order_by('-created_at')
            if batch_id:
                histories = histories.filter(batch_id=batch_id)
            data = []
            for h in histories:
                data.append({
                    "batch_id": h.batch_id,
                    "filename": h.filename,
                    "file_size": h.file_size,
                    "total_records": h.total_records,
                    "successful_records": h.successful_records,
                    "failed_records": h.failed_records,
                    "processing_status": h.processing_status,
                    "invoice_extracted": h.invoice_extracted,
                    "data_uploaded": h.data_uploaded,
                    "uploaded_by": h.uploaded_by,
                    "extracted_invoice_count": h.extracted_invoice_count,
                    "created_at": h.created_at,
                    "completed_at": h.completed_at,
                })

            # Calculate invoice counts from ItemWiseGrn
            if batch_id:
                grn_records = ItemWiseGrn.objects.filter(batch_id=batch_id)
            else:
                grn_records = ItemWiseGrn.objects.all()

            total_invoices = grn_records.count()
            extracted_invoices = grn_records.filter(extracted_data=True).count()
            non_extracted_invoices = grn_records.filter(extracted_data=False).count()

            return JsonResponse({
                "upload_history": data,
                "invoice_summary": {
                    "total_invoices": total_invoices,
                    "extracted_invoices": extracted_invoices,
                    "non_extracted_invoices": non_extracted_invoices
                }
            }, status=200)
        except Exception as e:
            logger.error(f"Error fetching upload history: {str(e)}")
            return JsonResponse({
                "success": False,
                "error": "Failed to fetch upload history.",
                "details": str(e)
            }, status=500)