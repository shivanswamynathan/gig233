from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from document_processing.models import InvoiceGrnReconciliation, InvoiceData,Check
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
import logging
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
                    'invoice date': recon.invoice_date.strftime('%Y-%m-%d') if recon.invoice_date else None,
                    'grn date': recon.grn_date.strftime('%Y-%m-%d') if recon.grn_date else None,
                    
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
                    'approved at': recon.approved_at.strftime('%Y-%m-%d %H:%M:%S') if recon.approved_at else None,
                    'reconciled at': recon.reconciled_at.strftime('%Y-%m-%d %H:%M:%S') if recon.reconciled_at else None,
                    'reconciled by': recon.reconciled_by,
                    'updated at': recon.updated_at.strftime('%Y-%m-%d %H:%M:%S') if recon.updated_at else None,
                    
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


# Add this new view to reconciliation/document_processing/views/check_views.py

@method_decorator(csrf_exempt, name='dispatch')
class CheckApprovalAPI(View):
    """
    POST endpoint to handle user approval actions and store in Check table
    
    POST /api/check-approval/
    
    Request Body:
    {
        "po_number": "string",
        "grn_number": "string", 
        "invoice_number": "string",
        "vendor_name": "string",
        "invoice_data_id": integer,
        "action": true/false,
        "approved_by": "string (optional)"
    }
    
    When action = true, status changes to "approved"
    When action = false, status remains "pending" or becomes "rejected"
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
            po_number = body.get('po_number')
            grn_number = body.get('grn_number')
            invoice_number = body.get('invoice_number')
            vendor_name = body.get('vendor_name')
            invoice_data_id = body.get('invoice_data_id')
            action = body.get('action')
            approved_by = body.get('approved_by', 'system')
            
            # Validate required fields
            required_fields = {
                'po_number': po_number,
                'grn_number': grn_number,
                'invoice_number': invoice_number,
                'vendor_name': vendor_name,
                'invoice_data_id': invoice_data_id,
                'action': action
            }
            
            missing_fields = [field for field, value in required_fields.items() if value is None or value == '']
            if missing_fields:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)
            
            # Validate action is boolean
            if not isinstance(action, bool):
                return JsonResponse({
                    'success': False,
                    'error': 'Action must be true or false'
                }, status=400)
            
            # Validate invoice_data_id is integer
            if not isinstance(invoice_data_id, int):
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id must be an integer'
                }, status=400)
            
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
                        'approved_by': approved_by
                    }
                )
                
                # Update the record based on action
                if action == True:
                    # User approved - set status to approved
                    check_record.status = 'approved'
                    check_record.action = True
                    check_record.approved_by = approved_by
                    action_message = "approved"
                else:
                    # User did not approve - set status to rejected
                    check_record.status = 'rejected'
                    check_record.action = False
                    check_record.approved_by = approved_by
                    action_message = "rejected"
                
                # Update vendor name in case it changed
                check_record.vendor_name = vendor_name
                check_record.save()
                
                # Log the action
                logger.info(f"[CheckApprovalAPI] User {action_message} record: PO-{po_number}, GRN-{grn_number}, Invoice-{invoice_number}")
                
                # Prepare response
                response_data = {
                    'success': True,
                    'message': f'Record successfully {action_message}',
                    'data': {
                        'po_number': check_record.po_number,
                        'grn_number': check_record.grn_number,
                        'invoice_number': check_record.invoice_number,
                        'vendor_name': check_record.vendor_name,
                        'invoice_data_id': check_record.invoice_data_id,
                        'status': check_record.status,
                        'action': check_record.action,
                        'approved_by': check_record.approved_by,
                        'created': created,
                        'updated_at': check_record.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'created_at': check_record.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                }
                
                return JsonResponse(response_data, status=200)
                
        except Exception as e:
            logger.error(f"[CheckApprovalAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Failed to process approval: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class CheckApprovalAPI(View):
    """
    POST endpoint to handle user approval actions and store in Check table
    
    POST /api/check-approval/
    
    Request Body (Minimal - other fields auto-fetched):
    {
        "invoice_data_id": integer (REQUIRED),
        "action": true/false (REQUIRED),
        "approved_by": "string (optional)"
    }
    
    OR Full Request Body (if you want to provide all fields):
    {
        "po_number": "string",
        "grn_number": "string", 
        "invoice_number": "string",
        "vendor_name": "string",
        "invoice_data_id": integer,
        "action": true/false,
        "approved_by": "string (optional)"
    }
    
    When action = true, status changes to "approved"
    When action = false, status remains "pending" or becomes "rejected"
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
            
            # Extract essential fields
            invoice_data_id = body.get('invoice_data_id')
            action = body.get('action')
            approved_by = body.get('approved_by', 'system')
            
            # Validate essential fields
            if invoice_data_id is None:
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id is required'
                }, status=400)
            
            if action is None:
                return JsonResponse({
                    'success': False,
                    'error': 'action is required'
                }, status=400)
            
            # Validate action is boolean
            if not isinstance(action, bool):
                return JsonResponse({
                    'success': False,
                    'error': 'action must be true or false'
                }, status=400)
            
            # Validate invoice_data_id is integer
            if not isinstance(invoice_data_id, int):
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id must be an integer'
                }, status=400)
            
            # Get optional fields from request or fetch from database
            po_number = body.get('po_number')
            grn_number = body.get('grn_number')
            invoice_number = body.get('invoice_number')
            vendor_name = body.get('vendor_name')
            
            # If any required field is missing, fetch from InvoiceGrnReconciliation table
            if not all([po_number, grn_number, invoice_number, vendor_name]):
                try:
                    # Find reconciliation record by invoice_data_id
                    reconciliation = InvoiceGrnReconciliation.objects.filter(
                        invoice_data_id=invoice_data_id
                    ).first()
                    
                    if not reconciliation:
                        return JsonResponse({
                            'success': False,
                            'error': f'No reconciliation record found for invoice_data_id: {invoice_data_id}'
                        }, status=404)
                    
                    # Use provided values or fetch from reconciliation
                    po_number = po_number or reconciliation.po_number
                    grn_number = grn_number or reconciliation.grn_number
                    invoice_number = invoice_number or reconciliation.invoice_number
                    vendor_name = vendor_name or reconciliation.grn_vendor  # Only use GRN vendor
                    
                    logger.info(f"[CheckApprovalAPI] Auto-fetched fields from reconciliation: PO-{po_number}, GRN-{grn_number}, Invoice-{invoice_number}, Vendor-{vendor_name} (GRN vendor only)")
                    
                    # Add after finding the reconciliation record:
                    total_amount = reconciliation.invoice_total if reconciliation else None
                    
                    # Get invoice URL from InvoiceData
                    invoice_url = None
                    try:
                        invoice_data = InvoiceData.objects.get(id=invoice_data_id)
                        invoice_url = invoice_data.attachment_url
                    except InvoiceData.DoesNotExist:
                        logger.warning(f"InvoiceData not found for ID: {invoice_data_id}")
                    
                except Exception as e:
                    logger.error(f"Error fetching reconciliation data: {str(e)}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Failed to fetch reconciliation data for invoice_data_id {invoice_data_id}: {str(e)}'
                    }, status=500)
            else:
                # If all fields provided, still get total_amount and url
                try:
                    reconciliation = InvoiceGrnReconciliation.objects.filter(
                        invoice_data_id=invoice_data_id
                    ).first()
                    total_amount = reconciliation.invoice_total if reconciliation else None
                    
                    # Get invoice URL from InvoiceData
                    invoice_url = None
                    try:
                        invoice_data = InvoiceData.objects.get(id=invoice_data_id)
                        invoice_url = invoice_data.attachment_url
                    except InvoiceData.DoesNotExist:
                        logger.warning(f"InvoiceData not found for ID: {invoice_data_id}")
                except Exception as e:
                    logger.warning(f"Could not fetch additional data: {str(e)}")
                    total_amount = None
                    invoice_url = None
            
            # Final validation - ensure we have all required fields
            if not all([po_number, grn_number, invoice_number, vendor_name]):
                missing_fields = []
                if not po_number: missing_fields.append('po_number')
                if not grn_number: missing_fields.append('grn_number')
                if not invoice_number: missing_fields.append('invoice_number')
                if not vendor_name: missing_fields.append('vendor_name')
                
                return JsonResponse({
                    'success': False,
                    'error': f'Could not determine required fields from reconciliation data. Missing: {", ".join(missing_fields)}'
                }, status=400)
            
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
                    check_record.approved_by = approved_by
                    action_message = "approved"
                else:
                    # User did not approve - set status to rejected
                    check_record.status = 'rejected'
                    check_record.action = False
                    check_record.approved_by = approved_by
                    action_message = "rejected"
                
                # Update vendor name and additional fields in case they changed
                check_record.vendor_name = vendor_name
                if total_amount:
                    check_record.total_amount = total_amount
                if invoice_url:
                    check_record.url = invoice_url
                check_record.save()
                
                # Log the action
                logger.info(f"[CheckApprovalAPI] User {action_message} record: PO-{po_number}, GRN-{grn_number}, Invoice-{invoice_number}")
                
                # Prepare response
                response_data = {
                    'success': True,
                    'message': f'Record successfully {action_message}',
                    'data': {
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
                        'updated_at': check_record.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'created_at': check_record.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'auto_fetched_fields': not all([
                            body.get('po_number'), 
                            body.get('grn_number'), 
                            body.get('invoice_number'), 
                            body.get('vendor_name')
                        ])
                    }
                }
                
                return JsonResponse(response_data, status=200)
                
        except Exception as e:
            logger.error(f"[CheckApprovalAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Failed to process approval: {str(e)}'
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
                    'created_at': check.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': check.updated_at.strftime('%Y-%m-%d %H:%M:%S')
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
