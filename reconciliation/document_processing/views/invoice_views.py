from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from document_processing.models import InvoiceData
import logging

logger = logging.getLogger(__name__)


def format_success_response(data, message="Success"):
    return JsonResponse({
        "success": True,
        "message": message,
        "data": data
    }, status=200)


def format_error_response(message="Internal Server Error", status=500):
    return JsonResponse({
        "success": False,
        "message": message,
        "data": []
    }, status=status)


@method_decorator(csrf_exempt, name='dispatch')
class ProcessedInvoiceListAPI(View):
    """Returns all successfully processed invoices."""

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

            formatted = [
                {
                    **inv,
                    'updated_at': inv['updated_at'].strftime("%d/%m/%y") if inv['updated_at'] else ""
                }
                for inv in invoices
            ]

            logger.info(f"[ProcessedInvoiceListAPI] Returned {len(formatted)} records.")
            return format_success_response(formatted, "Processed invoices fetched successfully.")

        except Exception as e:
            logger.error(f"[ProcessedInvoiceListAPI] Error: {str(e)}", exc_info=True)
            return format_error_response()


@method_decorator(csrf_exempt, name='dispatch')
class MissingInvoiceListAPI(View):
    """Returns records with missing invoice numbers."""

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

            formatted = [
                {
                    **inv,
                    'updated_at': inv['updated_at'].strftime("%d/%m/%Y") if inv['updated_at'] else "",
                    'invoice_number': inv['invoice_number'] or "Missing"
                }
                for inv in invoices
            ]

            logger.info(f"[MissingInvoiceListAPI] Returned {len(formatted)} records.")
            return format_success_response(formatted, "Missing invoice records fetched.")

        except Exception as e:
            logger.error(f"[MissingInvoiceListAPI] Error: {str(e)}", exc_info=True)
            return format_error_response()
        
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
            statuses = ['completed', 'partial_matching', 'processing']
            grouped_data = {}

            for status in statuses:
                invoices = InvoiceData.objects.filter(
                    processing_status=status
                ).values(
                    'vendor_name',
                    'updated_at',
                    'po_number',
                    'grn_number',
                    'invoice_number',
                    'attachment_url'
                )

                formatted = []
                for inv in invoices:
                    formatted.append({
                        "vendor_name": inv['vendor_name'],
                        "updated_at": inv['updated_at'].strftime("%d/%m/%y") if inv['updated_at'] else "",
                        "po_number": inv['po_number'],
                        "grn_number": inv['grn_number'],
                        "invoice_number": inv['invoice_number'],
                        "attachment_name": inv['attachment_url'].split("/")[-1] if inv['attachment_url'] else "",
                        "confidence": ""  # Blank confidence (since not in DB)
                    })

                grouped_data[status] = formatted

            logger.info(f"[OCRIssuesListAPI] Returned {sum(len(v) for v in grouped_data.values())} records.")
            return JsonResponse({
                "success": True,
                "message": "OCR issue records grouped by status.",
                "data": grouped_data
            }, status=200)

        except Exception as e:
            logger.error(f"[OCRIssuesListAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                "success": False,
                "message": "Internal Server Error",
                "data": {}
            }, status=500)