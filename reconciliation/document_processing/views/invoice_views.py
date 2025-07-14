from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from document_processing.models import InvoiceData
import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ProcessedInvoiceListAPI(View):
    """
    API endpoint to return invoice records that have been successfully processed.

    Returns:
        JSON response containing a list of processed invoices with selected fields:
        - vendor_name
        - updated_at (formatted as DD/MM/YY)
        - po_number
        - grn_number
        - invoice_number

    Status Codes:
        200: Success
        500: Internal Server Error
    """
    def get(self, request):
        try:
            invoices = InvoiceData.objects.filter(
                processing_status='completed'
            ).values(
                'vendor_name',
                'updated_at',
                'po_number',
                'grn_number',
                'invoice_number'
            )

            formatted = []
            for inv in invoices:
                inv['updated_at'] = inv['updated_at'].strftime("%d/%m/%y") if inv['updated_at'] else ""
                formatted.append(inv)

            logger.info(f"[ProcessedInvoiceListAPI] Returned {len(formatted)} records.")
            return JsonResponse({"data": formatted})

        except Exception as e:
            logger.error(f"[ProcessedInvoiceListAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MissingInvoiceListAPI(View):
    """
    API endpoint to return records where invoice number is missing.

    A record is considered a 'missing invoice' if:
    - processing_status is 'completed'
    - invoice_number is NULL or an empty string

    Returns:
        JSON response containing records where invoice_number is missing.
        - vendor_name
        - updated_at (formatted as DD/MM/YYYY)
        - po_number
        - grn_number
        - invoice_number: set as "Missing" if not present

    Status Codes:
        200: Success
        500: Internal Server Error
    """
    def get(self, request):
        try:
            invoices = InvoiceData.objects.filter(
                processing_status='completed'
            ).filter(
                models.Q(invoice_number__isnull=True) | models.Q(invoice_number__exact="")
            ).values(
                'vendor_name',
                'updated_at',
                'po_number',
                'grn_number',
                'invoice_number'
            )

            formatted = []
            for inv in invoices:
                inv['updated_at'] = inv['updated_at'].strftime("%d/%m/%Y") if inv['updated_at'] else ""
                inv['invoice_number'] = inv['invoice_number'] or "Missing"
                formatted.append(inv)

            logger.info(f"[MissingInvoiceListAPI] Returned {len(formatted)} records.")
            return JsonResponse({"data": formatted})

        except Exception as e:
            logger.error(f"[MissingInvoiceListAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class OCRIssuesListAPI(View):
    """
    API endpoint to return records with OCR confidence < 85%.

    Fields:
    - vendor_name
    - updated_at
    - po_number
    - grn_number
    - invoice_number
    - attachment_url (used to generate filename)
    - confidence (as percentage)

    Status Codes:
        200: Success
        500: Internal Server Error
    """
    def get(self, request):
        try:
            invoices = InvoiceData.objects.filter(
                processing_status='completed',
                confidence__lt=85
            ).values(
                'vendor_name',
                'updated_at',
                'po_number',
                'grn_number',
                'invoice_number',
                'attachment_url',
                'confidence'
            )

            formatted = []
            for inv in invoices:
                inv['updated_at'] = inv['updated_at'].strftime("%d/%m/%y") if inv['updated_at'] else ""
                inv['attachment_name'] = inv['attachment_url'].split('/')[-1] if inv['attachment_url'] else ""
                inv['confidence'] = f"{inv['confidence']}%" if inv['confidence'] is not None else "N/A"
                formatted.append(inv)

            logger.info(f"[OCRIssuesListAPI] Returned {len(formatted)} OCR issue records.")
            return JsonResponse({"data": formatted})

        except Exception as e:
            logger.error(f"[OCRIssuesListAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)
