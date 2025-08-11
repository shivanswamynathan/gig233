from django.http import JsonResponse
from datetime import datetime
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from document_processing.models import InvoiceGrnReconciliation,InvoiceItemReconciliation, InvoiceData, GrnSummary
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
import logging
import json
from django.db import transaction
logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class ReconciliationDetailAPI(View):
    def get(self, request):
        try:
            invoice_item_groups = InvoiceGrnReconciliation.objects.all()
            all_reconciliations = []
            
            for grn_summary in invoice_item_groups:
                invoice_number =grn_summary.invoice_number
                po_number = grn_summary.po_number
                invoice_items = InvoiceItemReconciliation.objects.filter(invoice_number=invoice_number)
                invoice_data = InvoiceData.objects.filter(invoice_number=invoice_number).first()
                grn_aggregated_data = GrnSummary.objects.filter(grn_number=grn_summary.grn_number).first()


                invoice_line_items = []
                grn_line_items = []
                item_statuses = []

                for idx, item in enumerate(invoice_items, start=1):
                    invoice_line_items.append({
                        "item_sequence": item.invoice_item_sequence or idx,
                        "item_name": item.invoice_item_description,
                        "unit": item.invoice_item_unit,
                        "hsn": item.invoice_item_hsn,
                        "rate": float(item.invoice_item_unit_price) if item.invoice_item_unit_price is not None else "-",
                        "quantity": float(item.invoice_item_quantity) if item.invoice_item_quantity is not None else "-",
                        "subtotal": float(item.invoice_item_subtotal) if item.invoice_item_subtotal is not None else "-",
                        "sgst": float(item.invoice_item_sgst_amount) if item.invoice_item_sgst_amount is not None else "-",
                        "cgst": float(item.invoice_item_cgst_amount) if item.invoice_item_cgst_amount is not None else "-",
                        "igst": float(item.invoice_item_igst_amount) if item.invoice_item_igst_amount is not None else "-",
                        "total": float(item.invoice_item_total_amount) if item.invoice_item_total_amount is not None else "-",
                        "status": item.match_status
                    })

                    grn_line_items.append({
                        "item_sequence": idx,
                        "item_name": item.grn_item_description,
                        "unit": item.grn_item_unit,
                        "hsn": item.grn_item_hsn,
                        "rate": float(item.grn_item_unit_price) if item.grn_item_unit_price is not None else "-",
                        "quantity": float(item.grn_item_quantity) if item.grn_item_quantity is not None else "-",
                        "subtotal": float(item.grn_item_subtotal) if item.grn_item_subtotal is not None else "-",
                        "sgst": float(item.grn_item_sgst_amount) if item.grn_item_sgst_amount is not None else "-",
                        "cgst": float(item.grn_item_cgst_amount) if item.grn_item_cgst_amount is not None else "-",
                        "igst": float(item.grn_item_igst_amount) if item.grn_item_igst_amount is not None else "-",
                        "total": float(item.grn_item_total_amount) if item.grn_item_total_amount is not None else "-"
                    })

                    item_statuses.append({
                        "id": item.id,
                        "item_overall_status": item.overall_match_status,
                        "match_status": item.match_status,
                        "match_score": float(item.match_score) if item.match_score is not None else "-",
                        "quantity_variance": float(item.quantity_variance) if item.quantity_variance is not None else "-",
                        "subtotal_variance": float(item.subtotal_variance) if item.subtotal_variance is not None else "-",
                        "total_amount_variance": float(item.total_amount_variance) if item.total_amount_variance is not None else "-",
                        "updated_by": item.updated_by if item.updated_by else None,
                        "updtated_at": item.updated_at.timestamp() if item.updated_at else None,
                        "requires_review": item.requires_review,
                        "is_exception": item.is_exception
                    })

                response = {
                    "invoice_data": {
                        "invoice_number": invoice_number,
                        "invoice_data_id": grn_summary.invoice_data_id,
                        "attachment_url": invoice_data.attachment_url if invoice_data.attachment_url else None,
                        "po_number": grn_summary.po_number if grn_summary.po_number else None,
                        "vendor": grn_summary.invoice_vendor if grn_summary.invoice_vendor else None,
                        "invoice_date": grn_summary.invoice_date if grn_summary.invoice_date else None,
                        "invoice_discount": float(invoice_data.invoice_discount) if invoice_data.invoice_discount is not None else "-",
                        "invoice_total": float(grn_summary.invoice_total) if grn_summary.invoice_total is not None else "-",
                        "cgst": float(grn_summary.invoice_cgst) if grn_summary.invoice_cgst is not None else "-",
                        "sgst": float(grn_summary.invoice_sgst) if grn_summary.invoice_sgst is not None else "-",
                        "igst": float(grn_summary.invoice_igst) if grn_summary.invoice_igst is not None else "-",
                        "subtotal": float(grn_summary.invoice_subtotal) if grn_summary.invoice_subtotal is not None else "-",
                        "line_items": invoice_line_items
                    },
                    "grn_data": {
                        "grn_number": grn_summary.grn_number,
                        "po_number": po_number,
                        "vendor": grn_summary.grn_vendor if grn_summary.grn_vendor else None,
                        "grn_date": grn_summary.grn_date if grn_summary.grn_date else None,
                        "grn_total_discount": float(grn_aggregated_data.total_discount) if grn_aggregated_data and grn_aggregated_data.total_discount is not None else "-",
                        "grn_total": float(grn_summary.grn_total) if grn_summary.grn_total is not None else "-",
                        "cgst": float(grn_summary.grn_cgst) if grn_summary.grn_cgst is not None else "-",
                        "sgst": float(grn_summary.grn_sgst) if grn_summary.grn_sgst is not None else "-",
                        "igst": float(grn_summary.grn_igst) if grn_summary.grn_igst is not None else "-",
                        "subtotal": float(grn_summary.grn_subtotal) if grn_summary.grn_subtotal is not None else "-",
                        "line_items": grn_line_items
                    },
                    "status": {
                        "match_status": grn_summary.match_status if grn_summary.match_status else "pending",
                        "match_score": float(grn_summary.match_score) if grn_summary.match_score else 0,
                        "vendor_match": grn_summary.vendor_match,
                        "gst_match": grn_summary.gst_match,
                        "date_valid": grn_summary.date_valid,
                        "total_variance": float(grn_summary.total_variance) if grn_summary.total_variance is not None else "-",
                        "requires_review": grn_summary.requires_review if grn_summary.requires_review else False,
                        "is_exception": grn_summary.is_exception if grn_summary.is_exception else False,
                        "approval_status": grn_summary.approval_status,
                        "approved_by": grn_summary.approved_by if grn_summary.approved_by else None,
                        "approved_at": grn_summary.approved_at if grn_summary.approved_at else None,
                        "reconciled_by": grn_summary.reconciled_by if grn_summary.reconciled_by else None,
                        "reconciled_at": grn_summary.reconciled_at if grn_summary.reconciled_at else None,
                        "status": grn_summary.status,
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
