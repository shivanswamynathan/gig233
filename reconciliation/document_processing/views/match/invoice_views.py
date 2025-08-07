from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from document_processing.models import InvoiceData, ItemWiseGrn
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
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


class MissingInvoiceListAPI(APIView):
    """
    Django REST Framework API to return ItemWiseGrn records with missing invoices
    
    GET /api/missing-invoices/?batch_id=optional
    
    Query Parameters:
    - batch_id: Optional batch ID to filter specific upload batch
    
    Returns all ItemWiseGrn records where missing_invoice = True
    """
    
    def get(self, request):
        """GET: Retrieve ItemWiseGrn records with missing invoices"""
        try:
            # Get query parameters
            batch_id = request.query_params.get('batch_id', None)
            
            # Build queryset - filter records where missing_invoice = True
            queryset = ItemWiseGrn.objects.filter(missing_invoice=True)
            
            # Apply batch filter if provided
            if batch_id:
                queryset = queryset.filter(upload_batch_id=batch_id)
                logger.info(f"[MissingInvoiceListAPI] Filtering by batch_id: {batch_id}")
            
            # Check if any records found
            total_count = queryset.count()
            if total_count == 0:
                return Response({
                    'success': True,
                    'message': 'No records found with missing invoices',
                    'batch_id': batch_id,
                    'data': [],
                    'total_count': 0
                }, status=status.HTTP_200_OK)
            
            # Format the data
            formatted_data = []
            for grn_record in queryset:
                formatted_data.append({
                    'id': grn_record.id,
                    'grn_number': grn_record.grn_no,
                    'po_number': grn_record.po_no,
                    'vendor_name': grn_record.supplier,
                    'quantity': float(grn_record.received_qty) if grn_record.received_qty else 0,
                    'total_amount': float(grn_record.total) if grn_record.total else 0,
                    'missing_invoice': grn_record.missing_invoice,
                    'created_at': grn_record.created_at.strftime("%d/%m/%Y %H:%M") if grn_record.created_at else "",
                    'updated_at': grn_record.updated_at.strftime("%d/%m/%Y %H:%M") if grn_record.updated_at else ""
                })
            
            # Log success
            logger.info(f"[MissingInvoiceListAPI] Returned {len(formatted_data)} missing invoice records "
                       f"(Total: {total_count})")
            
            # Return response
            return Response({
                'success': True,
                'message': f'Retrieved {len(formatted_data)} records with missing invoices',
                'batch_id': batch_id,
                'data': formatted_data,
                'total_missing_invoices': total_count
                
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"[MissingInvoiceListAPI] Error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'message': str(e),
                'data': []
            }, status=status.HTTP_400_BAD_REQUEST)
        
@method_decorator(csrf_exempt, name='dispatch')
class OCRIssuesListAPI(View):
    """
    API endpoint to return records with OCR confidence < 85% and specific failure reasons.

    Filters:
    - processing_status = 'failed' and "completed"
    - failure_reason != null

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
            # Filter records with processing_status='failed' and failure_reason not null
            invoices = InvoiceData.objects.filter(
                models.Q(processing_status='failed') | models.Q(processing_status='completed')
            ).exclude(
                failure_reason__isnull=True  # Only exclude records where failure_reason is null
            ).values(
                'vendor_name',
                'updated_at',
                'po_number',
                'grn_number',
                'invoice_number',
                'attachment_url',
                'invoice_value_without_gst',
                'cgst_amount',
                'sgst_amount',
                'igst_amount',
                'total_gst_amount',
                'invoice_total_post_gst',
                'failure_reason',
                #'confidence'  # Include confidence if available
            )

            # Format the data
            formatted = []
            for inv in invoices:
                formatted.append({
                    "vendor_name": inv['vendor_name'],
                    "updated_at": inv['updated_at'].strftime("%d/%m/%y") if inv['updated_at'] else "",
                    "po_number": inv['po_number'],
                    "grn_number": inv['grn_number'],
                    "invoice_number": inv['invoice_number'],
                    "attachment_name": inv['attachment_url'] or "",
                    "confidence": "",  # Add actual confidence field if needed
                    "invoice_value_without_gst": float(inv['invoice_value_without_gst']) if inv['invoice_value_without_gst'] is not None else "-",
                    "cgst_amount": float(inv['cgst_amount']) if inv['cgst_amount'] is not None else "-",
                    "sgst_amount": float(inv['sgst_amount']) if inv['sgst_amount'] is not None else "-",
                    "igst_amount": float(inv['igst_amount']) if inv['igst_amount'] is not None else "-",
                    "total_gst_amount": float(inv['total_gst_amount']) if inv['total_gst_amount'] is not None else "-",
                    "invoice_total_post_gst": float(inv['invoice_total_post_gst']) if inv['invoice_total_post_gst'] is not None else "-",
                    "failure_reason": inv['failure_reason'] or "Unknown"
                })

            logger.info(f"[OCRIssuesListAPI] Returned {len(formatted)} records.")
            return JsonResponse({
                "success": True,
                "message": "OCR issue records fetched successfully.",
                "data": formatted
            }, status=200)

        except Exception as e:
            logger.error(f"[OCRIssuesListAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                "success": False,
                "message": "Internal Server Error",
                "data": []
            }, status=500)