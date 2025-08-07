from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse
import json
import logging

from document_processing.models import InvoiceData

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class ManuallyEnterInvoiceAPI(View):
    """
    API endpoint to accept JSON input and store in InvoiceData table.
    """

    def post(self, request):
        try:
            # Parse JSON input
            data = json.loads(request.body.decode('utf-8'))

            # Create InvoiceData object with all relevant fields
            invoice = InvoiceData.objects.create(
                manually_enter=data.get('manually_enter'),
                invoice_number=data.get('invoice_number'),
                vendor_name=data.get('vendor_name'),
                vendor_gst=data.get('vendor_gst'),
                vendor_pan=data.get('vendor_pan'),
                invoice_date=data.get('invoice_date'),
                po_number=data.get('po_number'),
                cgst_amount=data.get('cgst_amount'),
                sgst_amount=data.get('sgst_amount'),
                igst_amount=data.get('igst_amount'),
                processing_status=data.get('processing_status'),
                extracted_at=data.get('extracted_at'),
                created_at=data.get('created_at'),
                attachment_url=data.get('attachment_url'),
            )

            return JsonResponse({
                'success': True,
                'message': 'Invoice data stored successfully.',
                'invoice_id': invoice.id
            }, status=201)

        except Exception as e:
            logger.error(f"Error in manual entry API: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)