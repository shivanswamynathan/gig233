from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from document_processing.models import InvoiceGrnReconciliation, InvoiceData,Check
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
import logging
from datetime import datetime, timezone
import json
from django.db import transaction
logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ApprovedReconciliationAPI(View):
    """
    API endpoint to return only reconciliation records where approval_status = 'approved'
    
    GET /api/approved-reconciliations/
    
    Query Parameters:
    - page: Page number (default: 1)
    - limit: Records per page (default: 10, max: 10)
    
    Returns the specified fields for approved reconciliations with pagination
    Plus 3 additional calculated fields:
    - status: Default "pending"
    - url: Invoice attachment URL from InvoiceData table
    - actions: True/False based on business logic
    """
    
    def get(self, request):
        try:
            # Initialize pagination helper
            pagination = PaginationHelper(request, default_limit=10, max_limit=10)
            
            # Validate pagination parameters
            validation_error = pagination.validate_params()
            if validation_error:
                return JsonResponse(validation_error, status=400)
            
            # Query approved reconciliations
            queryset = InvoiceGrnReconciliation.objects.filter(
                approval_status='approved'
            ).order_by('-reconciled_at')
            
            # Apply pagination
            reconciliations, total_count = pagination.paginate_queryset(queryset)
            
            # Format the data with requested fields + 3 calculated fields
            formatted_data = []
            for recon in reconciliations:
                
                # Calculate the 3 additional fields
                invoice_url = self._get_invoice_url(recon.invoice_data_id)
                
                
                formatted_data.append({
                    # Basic identifiers
                    'po number': recon.po_number,
                    'grn number': recon.grn_number,
                    'invoice number': recon.invoice_number,
                    'invoice_data_id': recon.invoice_data_id,
                    
                    # Vendor information
                    'invoice vendor': recon.invoice_vendor,
                    'grn vendor': recon.grn_vendor,
                    
                    # GST information
                    'invoice gst': recon.invoice_gst,
                    'grn gst': recon.grn_gst,
                    
                    # Dates
                    'invoice date': datetime.combine(recon.invoice_date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp() if recon.invoice_date else None,
                    'grn date': datetime.combine(recon.grn_date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp() if recon.grn_date else None,
                    
                    # Invoice financial amounts
                    'invoice subtotal': float(recon.invoice_subtotal) if recon.invoice_subtotal else 0,
                    'invoice cgst': float(recon.invoice_cgst) if recon.invoice_cgst else 0,
                    'invoice sgst': float(recon.invoice_sgst) if recon.invoice_sgst else 0,
                    'invoice igst': float(recon.invoice_igst) if recon.invoice_igst else 0,
                    'invoice total': float(recon.invoice_total) if recon.invoice_total else 0,
                    
                    # GRN financial amounts
                    'grn subtotal': float(recon.grn_subtotal) if recon.grn_subtotal else 0,
                    'grn cgst': float(recon.grn_cgst) if recon.grn_cgst else 0,
                    'grn sgst': float(recon.grn_sgst) if recon.grn_sgst else 0,
                    'grn igst': float(recon.grn_igst) if recon.grn_igst else 0,
                    'grn total': float(recon.grn_total) if recon.grn_total else 0,
                    
                    # Approval and processing information
                    'approval status': recon.approval_status,
                    'approved by': recon.approved_by,
                    'approved at': recon.approved_at.timestamp() if recon.approved_at else None,
                    'reconciled at': recon.reconciled_at.timestamp() if recon.reconciled_at else None,
                    'reconciled by': recon.reconciled_by,
                    'updated at': recon.updated_at.timestamp() if recon.updated_at else None,
                    
                    # Flags
                    'is_auto_matched': recon.is_auto_matched,
                    'requires review': recon.requires_review,
                    'is exception': recon.is_exception,
                    
                    # === 3 CALCULATED FIELDS (Not in database table) ===
                    'status': 'pending',  # Default status as requested
                    'url': invoice_url,    # Invoice attachment URL from InvoiceData table
                    'actions': 'False'     # True/False based on business logic
                })
            
            # Log success
            pagination_info = pagination.get_pagination_info(total_count)
            logger.info(f"[ApprovedReconciliationAPI] Returned {len(formatted_data)} approved reconciliation records (Page {pagination.page}/{pagination_info['total_pages']})")
            
            # Create paginated response using utility
            return pagination.create_paginated_response(
                data=formatted_data,
                total_count=total_count,
                message=f'Retrieved {len(formatted_data)} approved reconciliation records from page {pagination.page}'
            )
            
        except Exception as e:
            logger.error(f"[ApprovedReconciliationAPI] Error: {str(e)}", exc_info=True)
            return create_server_error_response('Failed to fetch approved reconciliation records')
    
    def _get_invoice_url(self, invoice_data_id):
        """
        Get invoice attachment URL from InvoiceData table
        
        Args:
            invoice_data_id: ID of the invoice data record
            
        Returns:
            str or None: Invoice attachment URL
        """
        try:
            if invoice_data_id:
                invoice_data = InvoiceData.objects.get(id=invoice_data_id)
                return invoice_data.attachment_url
        except InvoiceData.DoesNotExist:
            logger.warning(f"InvoiceData not found for ID: {invoice_data_id}")
        except Exception as e:
            logger.error(f"Error fetching invoice URL for ID {invoice_data_id}: {str(e)}")
        
        return None

@method_decorator(csrf_exempt, name='dispatch')
class CheckApprovalAPI(View):
    """
    POST endpoint to handle user approval actions and store in Check table
    
    POST /api/check-approval/
    
    Request Body:
    {
        "invoice_data_id": integer (REQUIRED),
        "action": true/false (REQUIRED),
        "approved_by": "string (REQUIRED)"
    }
    
    When action = true, status changes to "approved"
    When action = false, status changes to "rejected"
    
    All other fields (po_number, grn_number, invoice_number, vendor_name, etc.) 
    are automatically fetched from InvoiceGrnReconciliation table using invoice_data_id
    """
    
    def post(self, request):
        """POST: Handle user approval action and store in Check table"""
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
            action = body.get('action')
            approved_by = body.get('approved_by')
            
            # Validate all required fields in one condition
            if invoice_data_id is None or action is None or not approved_by:
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id, action, and approved_by are required'
                }, status=400)
            
            # Validate types
            if not isinstance(action, bool) or not isinstance(invoice_data_id, int):
                return JsonResponse({
                    'success': False,
                    'error': 'action must be true or false and invoice_data_id must be an integer'
                }, status=400)
            
            # Fetch all required data from InvoiceGrnReconciliation table
            try:
                reconciliation = InvoiceGrnReconciliation.objects.get(
                    invoice_data_id=invoice_data_id
                )
            except InvoiceGrnReconciliation.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'No reconciliation record found for invoice_data_id: {invoice_data_id}'
                }, status=404)
            
            # Get invoice URL from InvoiceData table
            invoice_url = None
            try:
                invoice_data = InvoiceData.objects.get(id=invoice_data_id)
                invoice_url = invoice_data.attachment_url
            except InvoiceData.DoesNotExist:
                logger.warning(f"InvoiceData not found for ID: {invoice_data_id}")
            
            # Extract all required fields from reconciliation record
            po_number = reconciliation.po_number
            grn_number = reconciliation.grn_number
            invoice_number = reconciliation.invoice_number
            vendor_name = reconciliation.grn_vendor  # Use GRN vendor
            total_amount = reconciliation.invoice_total
            
            # Process the approval action
            with transaction.atomic():
                # Check if record already exists in Check table
                check_record, created = Check.objects.get_or_create(
                    po_number=po_number,
                    grn_number=grn_number,
                    invoice_number=invoice_number,
                    invoice_data_id=invoice_data_id,
                    defaults={
                        'vendor_name': vendor_name,
                        'status': 'pending',
                        'action': False,
                        'approved_by': approved_by,
                        'total_amount': total_amount,
                        'url': invoice_url
                    }
                )
                
                # Update the record based on action
                if action == True:
                    # User approved - set status to approved
                    check_record.status = 'approved'
                    check_record.action = True
                    action_message = "approved"
                else:
                    # User rejected - set status to rejected
                    check_record.status = 'rejected'
                    check_record.action = False
                    action_message = "rejected"
                
                # Update all fields
                check_record.approved_by = approved_by
                check_record.vendor_name = vendor_name
                check_record.total_amount = total_amount
                check_record.url = invoice_url
                check_record.save()
                
                # Log the action
                logger.info(f"[CheckApprovalAPI] User {action_message} record: invoice_data_id-{invoice_data_id}, PO-{po_number}")
                
                # Prepare response with timestamps
                response_data = {
                    'success': True,
                    'message': f'Record successfully {action_message}',
                    'data': {
                        'id': check_record.id,
                        'po_number': check_record.po_number,
                        'grn_number': check_record.grn_number,
                        'invoice_number': check_record.invoice_number,
                        'vendor_name': check_record.vendor_name,
                        'invoice_data_id': check_record.invoice_data_id,
                        'status': check_record.status,
                        'action': check_record.action,
                        'approved_by': check_record.approved_by,
                        'total_amount': float(check_record.total_amount) if check_record.total_amount else None,
                        'url': check_record.url,
                        'created': created,
                        'updated_at': check_record.updated_at.timestamp(),
                        'created_at': check_record.created_at.timestamp()
                    }
                }
                
                return JsonResponse(response_data, status=200)
                
        except InvoiceGrnReconciliation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'No reconciliation record found for invoice_data_id: {invoice_data_id}'
            }, status=404)
        except ValueError as e:
            logger.warning(f"[CheckApprovalAPI] ValueError: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid data provided: {str(e)}'
            }, status=400)
        except Exception as e:
            logger.error(f"[CheckApprovalAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Internal server error occurred'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class CheckListAPI(View):
    """
    GET endpoint to retrieve all records from Check table with pagination
    
    GET /api/check-list/?page=1&limit=10
    """
    
    def get(self, request):
        """GET: Retrieve all Check table records with pagination"""
        try:
            # Initialize pagination helper
            pagination = PaginationHelper(request, default_limit=10, max_limit=50)
            
            # Get all records from Check table
            queryset = Check.objects.all().order_by('-created_at')
            
            # Apply pagination
            check_records, total_count = pagination.paginate_queryset(queryset)
            
            # Format the data
            formatted_data = []
            for check in check_records:
                formatted_data.append({
                    'id': check.id,
                    'po_number': check.po_number,
                    'grn_number': check.grn_number,
                    'invoice_number': check.invoice_number,
                    'vendor_name': check.vendor_name,
                    'invoice_data_id': check.invoice_data_id,
                    'status': check.status,
                    'action': check.action,
                    'approved_by': check.approved_by,
                    'total_amount': float(check.total_amount) if check.total_amount else None,
                    'url': check.url,
                    'created_at': check.created_at.timestamp(),
                    'updated_at': check.updated_at.timestamp()
                })
            
            # Create paginated response
            return pagination.create_paginated_response(
                data=formatted_data,
                total_count=total_count,
                message=f'Retrieved {len(formatted_data)} check records'
            )
            
        except Exception as e:
            logger.error(f"[CheckListAPI] Error: {str(e)}")
            return create_server_error_response('Failed to fetch check records')