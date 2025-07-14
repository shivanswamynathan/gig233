from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from document_processing.models import InvoiceGrnReconciliation, InvoiceData
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
import logging

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
    
    
