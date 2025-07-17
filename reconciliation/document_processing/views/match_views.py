from django.http import JsonResponse
from datetime import datetime
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from document_processing.models import ItemWiseGrn,InvoiceData,InvoiceGrnReconciliation,InvoiceItemReconciliation
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
import logging
import json
from django.db import transaction
logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class ReconciliationDetailAPI(View):
    def get(self, request):
        try:
            invoices = InvoiceData.objects.filter(type='invoice')  
            if not invoices.exists():
                return JsonResponse({"success": False, "message": "No invoice data found."}, status=404)

            all_reconciliations = []

            for invoice in invoices:
                po_number = invoice.po_number
                invoice_items = InvoiceItemReconciliation.objects.filter(invoice_number=invoice.invoice_number)
                grn_summary = InvoiceGrnReconciliation.objects.filter(po_number=po_number).first()

                invoice_line_items = []
                for item in invoice_items:
                    invoice_line_items.append({
                        "item_sequence": item.invoice_item_sequence,
                        "item_name": item.invoice_item_description,
                        "unit": item.invoice_item_unit,
                        "hsn": item.invoice_item_hsn,
                        "rate": float(item.invoice_item_unit_price or 0),
                        "quantity": float(item.invoice_item_quantity or 0),
                        "subtotal": float(item.invoice_item_subtotal or 0),
                        "sgst": float(item.invoice_item_sgst_amount or 0),
                        "cgst": float(item.invoice_item_cgst_amount or 0),
                        "igst": float(item.invoice_item_igst_amount or 0),
                        "total": float(item.invoice_item_total_amount or 0),
                        "status": item.match_status
                    })

                grn_line_items = []
                for idx, item in enumerate(invoice_items, start=1):
                    grn_line_items.append({
                        "item_sequence": idx,
                        "item_name": item.grn_item_description,
                        "unit": item.grn_item_unit,
                        "hsn": item.grn_item_hsn,
                        "rate": float(item.grn_item_unit_price or 0),
                        "quantity": float(item.grn_item_quantity or 0),
                        "subtotal": float(item.grn_item_subtotal or 0),
                        "sgst": float(item.grn_item_sgst_amount or 0),
                        "cgst": float(item.grn_item_cgst_amount or 0),
                        "igst": float(item.grn_item_igst_amount or 0),
                        "total": float(item.grn_item_total_amount or 0)
                    })

                item_statuses = []
                for item in invoice_items:
                    item_statuses.append({
                        "item_sequence": item.invoice_item_sequence,
                        "match_status": item.match_status,
                        "match_score": float(item.match_score or 0),
                        "quantity_variance": float(item.quantity_variance or 0),
                        "subtotal_variance": float(item.subtotal_variance or 0),
                        "total_amount_variance": float(item.total_amount_variance or 0),
                        "requires_review": item.requires_review,
                        "is_exception": item.is_exception
                    })

                response = {
                    "invoice_data": {
                        "invoice_number": invoice.invoice_number,
                        "po_number": invoice.po_number,
                        "vendor": invoice.vendor_name,
                        "invoice_date": invoice.invoice_date,
                        "invoice_total": float(invoice.invoice_total_post_gst or 0),
                        "cgst": float(invoice.cgst_amount or 0),
                        "sgst": float(invoice.sgst_amount or 0),
                        "igst": float(invoice.igst_amount or 0),
                        "subtotal": float(invoice.invoice_value_without_gst or 0),
                        "line_items": invoice_line_items
                    },
                    "grn_data": {
                        "grn_number": invoice.grn_number,
                        "po_number": invoice.po_number,
                        "vendor": invoice.vendor_name,
                        "grn_date": grn_summary.grn_date if grn_summary else None,
                        "grn_total": float(grn_summary.grn_total or 0) if grn_summary else 0,
                        "cgst": float(grn_summary.grn_cgst or 0) if grn_summary else 0,
                        "sgst": float(grn_summary.grn_sgst or 0) if grn_summary else 0,
                        "igst": float(grn_summary.grn_igst or 0) if grn_summary else 0,
                        "subtotal": float(grn_summary.grn_subtotal or 0) if grn_summary else 0,
                        "line_items": grn_line_items
                    },
                    "status": {
                        "match_status": grn_summary.match_status if grn_summary else "pending",
                        "match_score": float(grn_summary.match_score or 0) if grn_summary else 0,
                        "vendor_match": grn_summary.vendor_match if grn_summary else False,
                        "gst_match": grn_summary.gst_match if grn_summary else False,
                        "date_valid": grn_summary.date_valid if grn_summary else False,
                        "total_variance": float(grn_summary.total_variance or 0) if grn_summary else 0,
                        "exception_reasons": grn_summary.exception_reasons or [],
                        "requires_review": grn_summary.requires_review if grn_summary else False,
                        "is_exception": grn_summary.is_exception if grn_summary else False,
                        "approval_status": grn_summary.approval_status if grn_summary else "pending",
                        "reconciled_by": grn_summary.reconciled_by if grn_summary else None,
                        "reconciled_at": grn_summary.reconciled_at if grn_summary else None,
                        "item_level_status": item_statuses
                    }
                }

                all_reconciliations.append(response)

            return JsonResponse({"success": True, "data": all_reconciliations}, status=200)

        except Exception as e:
            logger.exception("Error in reconciliation detail API")
            return JsonResponse({
                "success": False,
                "message": "Internal Server Error",
                "error": str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ReconciliationApprovalAPI(View):
    """
    POST endpoint to update reconciliation approval status
    
    POST /api/reconciliation-approval/
    
    Request Body:
    {
        "invoice_data_id": integer (REQUIRED),
        "status": true/false (REQUIRED),
        "approved_by": "string (REQUIRED)"
    }
    
    When status = true:
    - Sets status = True
    - Sets approval_status = "approved" 
    - Sets approved_by = provided name
    - Sets approved_at = current timestamp
    """
    
    def post(self, request):
        """POST: Update reconciliation approval status"""
        try:
            # Parse JSON request body
            try:
                body = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON in request body'
                }, status=400)
            
            # Extract required fields
            invoice_data_id = body.get('invoice_data_id')
            status = body.get('status')
            approved_by = body.get('approved_by')
            
            # Validate all required fields in one condition
            if invoice_data_id is None or status is None or not approved_by:
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id, status, and approved_by are required'
                }, status=400)
            
            # Validate types
            if not isinstance(status, bool) or not isinstance(invoice_data_id, int):
                return JsonResponse({
                    'success': False,
                    'error': 'status must be true or false and invoice_data_id must be an integer'
                }, status=400)
            
            # Find reconciliation record
            try:
                reconciliation = InvoiceGrnReconciliation.objects.get(
                    invoice_data_id=invoice_data_id
                )
            except InvoiceGrnReconciliation.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'No reconciliation record found for invoice_data_id: {invoice_data_id}'
                }, status=404)
            
            # Update reconciliation record
            with transaction.atomic():
                reconciliation.status = status
                reconciliation.approved_by = approved_by
                
                if status == True:
                    # User approved
                    reconciliation.approval_status = 'approved'
                    reconciliation.approved_at = datetime.now()
                    action_message = "approved"
                else:
                    # User rejected
                    reconciliation.approval_status = 'pending'
                    reconciliation.approved_at = None
                    action_message = "rejected"
                
                reconciliation.save()
                
                # Log the action
                logger.info(f"[ReconciliationApprovalAPI] User {action_message} reconciliation: invoice_data_id-{invoice_data_id}, PO-{reconciliation.po_number}")
                
                # Prepare response with timestamps
                response_data = {
                    'success': True,
                    'message': f'Reconciliation successfully {action_message}',
                    'data': {
                        'id': reconciliation.id,
                        'invoice_data_id': reconciliation.invoice_data_id,
                        'po_number': reconciliation.po_number,
                        'grn_number': reconciliation.grn_number,
                        'invoice_number': reconciliation.invoice_number,
                        'status': reconciliation.status,
                        'approval_status': reconciliation.approval_status,
                        'approved_by': reconciliation.approved_by,
                        'approved_at': reconciliation.approved_at.timestamp() if reconciliation.approved_at else None,
                        'updated_at': reconciliation.updated_at.timestamp()
                    }
                }
                
                return JsonResponse(response_data, status=200)
                
        except InvoiceGrnReconciliation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'No reconciliation record found for invoice_data_id: {invoice_data_id}'
            }, status=404)
        except ValueError as e:
            logger.warning(f"[ReconciliationApprovalAPI] ValueError: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid data provided: {str(e)}'
            }, status=400)
        except Exception as e:
            logger.error(f"[ReconciliationApprovalAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Internal server error occurred'
            }, status=500)