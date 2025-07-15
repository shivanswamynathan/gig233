from django.http import JsonResponse
from datetime import datetime
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from document_processing.models import InvoiceGrnReconciliation
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
import logging
import json
from django.db import transaction
logger = logging.getLogger(__name__)


# Add this new endpoint to check_views.py

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
            
            # Validate required fields
            if invoice_data_id is None:
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id is required'
                }, status=400)
            
            if status is None:
                return JsonResponse({
                    'success': False,
                    'error': 'status is required'
                }, status=400)
            
            if not approved_by:
                return JsonResponse({
                    'success': False,
                    'error': 'approved_by is required'
                }, status=400)
            
            # Validate types
            if not isinstance(status, bool):
                return JsonResponse({
                    'success': False,
                    'error': 'status must be true or false'
                }, status=400)
            
            if not isinstance(invoice_data_id, int):
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id must be an integer'
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
                
                # Prepare response
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
                        'approved_at': reconciliation.approved_at.strftime('%Y-%m-%d %H:%M:%S') if reconciliation.approved_at else None,
                        'updated_at': reconciliation.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                }
                
                return JsonResponse(response_data, status=200)
                
        except Exception as e:
            logger.error(f"[ReconciliationApprovalAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Failed to process reconciliation approval: {str(e)}'
            }, status=500)
