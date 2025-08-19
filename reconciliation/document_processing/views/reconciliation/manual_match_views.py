import json
import logging
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from document_processing.models import InvoiceItemReconciliation

logger = logging.getLogger(__name__)


class ManualMatchAPI(APIView):
    """
    POST endpoint to handle manual matching by COPYING values between Invoice and GRN
    in InvoiceItemReconciliation table
    
    POST /api/manual-match/
    
    Request Body:
    {
        "id": integer (REQUIRED) - ID of InvoiceItemReconciliation record,
        "swap_direction": "invoice_to_grn" | "grn_to_invoice" (REQUIRED),
        "fields_to_swap": ["description", "quantity", "unit_price", "total_amount", "hsn", "all"] (OPTIONAL - defaults to ["all"]),
        "updated_by": "string (REQUIRED)" - User who performed the manual match
    }
    
    Functionality:
    - invoice_to_grn: COPIES Invoice data TO GRN fields (Invoice data remains unchanged)
    - grn_to_invoice: COPIES GRN data TO Invoice fields (GRN data remains unchanged)  
    - Sets manual_match = True
    - Updates match_status to "perfect_match" after successful copy operation
    """
    
    def post(self, request, *args, **kwargs):
        """POST: Handle manual match by copying values"""
        try:
            # Get data from DRF request
            body = request.data
            
            # Extract required fields
            reconciliation_id = body.get('id')
            swap_direction = body.get('swap_direction')
            fields_to_swap = body.get('fields_to_swap', ['all'])
            updated_by = body.get('updated_by')
            
            # Validate required fields
            if reconciliation_id is None or swap_direction is None or updated_by is None:
                return Response({
                    'success': False,
                    'error': 'id, swap_direction, and updated_by are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate swap_direction
            if swap_direction not in ['invoice_to_grn', 'grn_to_invoice']:
                return Response({
                    'success': False,
                    'error': 'swap_direction must be "invoice_to_grn" or "grn_to_invoice"'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate fields_to_swap
            allowed_fields = ['description', 'quantity', 'unit_price', 'total_amount', 'hsn', 'unit', 'subtotal', 'cgst', 'sgst', 'igst', 'all']
            if not isinstance(fields_to_swap, list) or not all(field in allowed_fields for field in fields_to_swap):
                return Response({
                    'success': False,
                    'error': f'fields_to_swap must be a list containing values from: {allowed_fields}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Find reconciliation record by ID
            try:
                reconciliation = InvoiceItemReconciliation.objects.get(id=reconciliation_id)
                
                # Check if record already has perfect_match status
                if reconciliation.match_status == 'perfect_match':
                    return Response({
                        'success': False,
                        'error': f'Cannot perform manual matching on reconciliation ID {reconciliation_id}: record already has perfect_match status',
                        'current_status': reconciliation.match_status
                    }, status=status.HTTP_400_BAD_REQUEST)
                
            except InvoiceItemReconciliation.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f'No reconciliation record found with ID: {reconciliation_id}'
                }, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'Error finding reconciliation record: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Perform COPY operation
            with transaction.atomic():
                copied_values = {}
                
                logger.info(f"[ManualMatchAPI] Starting COPY operation for reconciliation ID {reconciliation_id}")
                logger.info(f"[ManualMatchAPI] Copy direction: {swap_direction}")
                logger.info(f"[ManualMatchAPI] Fields to copy: {fields_to_swap}")
                
                # Define field mappings for copying
                field_mappings = self._get_field_mappings(fields_to_swap)
                
                # SIMPLE COPY LOGIC - NO SWAPPING
                if swap_direction == 'invoice_to_grn':
                    # COPY Invoice data TO GRN fields (Invoice remains unchanged)
                    for invoice_field, grn_field in field_mappings.items():
                        invoice_value = getattr(reconciliation, invoice_field)
                        
                        # Copy invoice value to GRN field
                        setattr(reconciliation, grn_field, invoice_value)
                        copied_values[f"{invoice_field} → {grn_field}"] = f"Copied: {invoice_value}"
                
                elif swap_direction == 'grn_to_invoice':
                    # COPY GRN data TO Invoice fields (GRN remains unchanged)
                    for invoice_field, grn_field in field_mappings.items():
                        grn_value = getattr(reconciliation, grn_field)
                        
                        # Copy GRN value to Invoice field
                        setattr(reconciliation, invoice_field, grn_value)
                        copied_values[f"{grn_field} → {invoice_field}"] = f"Copied: {grn_value}"
                
                # Update reconciliation status and flags
                original_match_status = reconciliation.match_status
                reconciliation.match_status = 'perfect_match'
                reconciliation.overall_match_status = 'complete_match'
                reconciliation.manual_match = True
                reconciliation.is_auto_matched = False
                reconciliation.updated_by = updated_by
                
                # Update match_notes instead of reconciliation_notes
                reconciliation.match_notes = (
                    f"{reconciliation.match_notes or ''}\n"
                    f"Manual match performed by {updated_by} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. "
                    f"Copy direction: {swap_direction}. "
                    f"Original status: {original_match_status}. "
                    f"Fields copied: {', '.join(fields_to_swap)}. "
                    f"Status changed to perfect_match after manual copy."
                ).strip()
                
                # Recalculate variances after copying (should be zero since both sides are now identical)
                self._recalculate_variances(reconciliation)
                
                # Save the changes
                reconciliation.save()
                
                # Log the successful copy operation
                logger.info(f"[ManualMatchAPI] Manual copy completed for reconciliation ID {reconciliation_id}")
                logger.info(f"[ManualMatchAPI] Record status changed to perfect_match")
                
                # Determine operation description
                if swap_direction == 'invoice_to_grn':
                    operation_description = "Copied Invoice data to GRN fields"
                else:
                    operation_description = "Copied GRN data to Invoice fields"
                
                # Prepare detailed response
                response_data = {
                    'success': True,
                    'message': f'Manual copy completed successfully. {operation_description}. Record now has perfect_match status.',
                    'data': {
                        'reconciliation_id': reconciliation_id,
                        'fields_copied': len(field_mappings),
                        'overall_match_status': 'overall_match_status',
                        'match_status': 'perfect_match',
                        'copy_direction': swap_direction,
                        'operation_performed': operation_description,
                        'fields_copied_list': fields_to_swap,
                        'performed_by': updated_by,
                        'performed_at': datetime.now().isoformat(),
                        'processed_item': {
                            'reconciliation_id': reconciliation.id,
                            'item_sequence': reconciliation.invoice_item_sequence,
                            'original_status': original_match_status,
                            'new_status': reconciliation.match_status,
                            'copied_fields_count': len(field_mappings),
                            'invoice_item_description': reconciliation.invoice_item_description,
                            'grn_item_description': reconciliation.grn_item_description,
                            'copied_values': copied_values
                        },
                        'summary': {
                            'item_now_perfect_match': True,
                            'manual_match_flag_set': True,
                            'auto_matched_flag_cleared': True,
                            'operation_type': 'copy' 
                        }
                    }
                }
                
                return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"[ManualMatchAPI] Error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Internal server error occurred',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_field_mappings(self, fields_to_swap):
        """
        Get field mappings based on fields_to_swap list
        
        Returns:
            dict: Mapping of invoice_field -> grn_field
        """
        # Complete field mapping between invoice and GRN
        all_field_mappings = {
            'invoice_item_description': 'grn_item_description',
            'invoice_item_hsn': 'grn_item_hsn',
            'invoice_item_quantity': 'grn_item_quantity',
            'invoice_item_unit': 'grn_item_unit',
            'invoice_item_unit_price': 'grn_item_unit_price',
            'invoice_item_subtotal': 'grn_item_subtotal',
            'invoice_item_cgst_rate': 'grn_item_cgst_rate',
            'invoice_item_cgst_amount': 'grn_item_cgst_amount',
            'invoice_item_sgst_rate': 'grn_item_sgst_rate',
            'invoice_item_sgst_amount': 'grn_item_sgst_amount',
            'invoice_item_igst_rate': 'grn_item_igst_rate',
            'invoice_item_igst_amount': 'grn_item_igst_amount',
            'invoice_item_total_tax': 'grn_item_total_tax',
            'invoice_item_total_amount': 'grn_item_total_amount'
        }
        
        # If 'all' is specified, return all mappings
        if 'all' in fields_to_swap:
            return all_field_mappings
        
        # Create mapping based on specified fields
        selected_mappings = {}
        field_aliases = {
            'description': 'invoice_item_description',
            'hsn': 'invoice_item_hsn',
            'quantity': 'invoice_item_quantity',
            'unit': 'invoice_item_unit',
            'unit_price': 'invoice_item_unit_price',
            'subtotal': 'invoice_item_subtotal',
            'cgst': ['invoice_item_cgst_rate', 'invoice_item_cgst_amount'],
            'sgst': ['invoice_item_sgst_rate', 'invoice_item_sgst_amount'],
            'igst': ['invoice_item_igst_rate', 'invoice_item_igst_amount'],
            'total_amount': 'invoice_item_total_amount'
        }
        
        for field in fields_to_swap:
            if field in field_aliases:
                alias_fields = field_aliases[field]
                if isinstance(alias_fields, list):
                    # Handle multiple fields (like cgst has both rate and amount)
                    for alias_field in alias_fields:
                        if alias_field in all_field_mappings:
                            selected_mappings[alias_field] = all_field_mappings[alias_field]
                else:
                    # Handle single field
                    if alias_fields in all_field_mappings:
                        selected_mappings[alias_fields] = all_field_mappings[alias_fields]
            elif field in all_field_mappings:
                # Direct field name match
                selected_mappings[field] = all_field_mappings[field]
        
        return selected_mappings
    
    def _recalculate_variances(self, reconciliation):
        """
        Recalculate variances after copying values
        
        Args:
            reconciliation: InvoiceItemReconciliation instance
        """
        try:
            # Recalculate quantity variance
            if reconciliation.invoice_item_quantity and reconciliation.grn_item_quantity:
                reconciliation.quantity_variance = reconciliation.invoice_item_quantity - reconciliation.grn_item_quantity
                if reconciliation.grn_item_quantity != 0:
                    reconciliation.quantity_variance_percentage = (reconciliation.quantity_variance / reconciliation.grn_item_quantity) * 100
            
            # Recalculate subtotal variance
            if reconciliation.invoice_item_subtotal and reconciliation.grn_item_subtotal:
                reconciliation.subtotal_variance = reconciliation.invoice_item_subtotal - reconciliation.grn_item_subtotal
                if reconciliation.grn_item_subtotal != 0:
                    reconciliation.subtotal_variance_percentage = (reconciliation.subtotal_variance / reconciliation.grn_item_subtotal) * 100
            
            # Recalculate total amount variance
            if reconciliation.invoice_item_total_amount and reconciliation.grn_item_total_amount:
                reconciliation.total_amount_variance = reconciliation.invoice_item_total_amount - reconciliation.grn_item_total_amount
                if reconciliation.grn_item_total_amount != 0:
                    reconciliation.total_amount_variance_percentage = (reconciliation.total_amount_variance / reconciliation.grn_item_total_amount) * 100
            
            # Recalculate unit rate variance
            if reconciliation.invoice_item_unit_price and reconciliation.grn_item_unit_price:
                reconciliation.unit_rate_variance = reconciliation.invoice_item_unit_price - reconciliation.grn_item_unit_price
            
            # Recalculate tax variances
            if reconciliation.invoice_item_cgst_amount and reconciliation.grn_item_cgst_amount:
                reconciliation.cgst_variance = reconciliation.invoice_item_cgst_amount - reconciliation.grn_item_cgst_amount
            
            if reconciliation.invoice_item_sgst_amount and reconciliation.grn_item_sgst_amount:
                reconciliation.sgst_variance = reconciliation.invoice_item_sgst_amount - reconciliation.grn_item_sgst_amount
            
            if reconciliation.invoice_item_igst_amount and reconciliation.grn_item_igst_amount:
                reconciliation.igst_variance = reconciliation.invoice_item_igst_amount - reconciliation.grn_item_igst_amount
            
            if reconciliation.invoice_item_total_tax and reconciliation.grn_item_total_tax:
                reconciliation.total_tax_variance = reconciliation.invoice_item_total_tax - reconciliation.grn_item_total_tax
            
            # Update tolerance flags based on new variances
            tolerance_pct = reconciliation.tolerance_percentage_applied or 2.00
            
            if reconciliation.total_amount_variance_percentage:
                reconciliation.is_within_amount_tolerance = abs(reconciliation.total_amount_variance_percentage) <= tolerance_pct
            
            if reconciliation.quantity_variance_percentage:
                quantity_tolerance_pct = reconciliation.quantity_tolerance_percentage_applied or 5.00
                reconciliation.is_within_quantity_tolerance = abs(reconciliation.quantity_variance_percentage) <= quantity_tolerance_pct
            
            logger.info(f"[ManualMatchAPI] Recalculated variances for reconciliation ID {reconciliation.id}")
            logger.info(f"[ManualMatchAPI] After manual copy - variances should be zero for perfect_match status")
            
        except Exception as e:
            logger.error(f"[ManualMatchAPI] Error recalculating variances: {str(e)}")
