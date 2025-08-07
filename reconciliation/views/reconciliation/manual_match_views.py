import json
import logging
from datetime import datetime
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from document_processing.models import InvoiceItemReconciliation

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ManualMatchAPI(View):
    """
    POST endpoint to handle manual matching by COPYING values between Invoice and GRN
    in InvoiceItemReconciliation table
    
    POST /api/manual-match/
    
    Request Body:
    {
        "invoice_data_id": integer (REQUIRED) - ID of InvoiceData record,
        "swap_direction": "invoice_to_grn" | "grn_to_invoice" (REQUIRED),
        "fields_to_swap": ["description", "quantity", "unit_price", "total_amount", "hsn", "all"] (OPTIONAL - defaults to ["all"]),
        "user": "string (OPTIONAL)" - User who performed the manual match
    }
    
    Functionality:
    - invoice_to_grn: COPIES Invoice data TO GRN fields (Invoice data remains unchanged)
    - grn_to_invoice: COPIES GRN data TO Invoice fields (GRN data remains unchanged)  
    - Sets manual_match = True
    - Updates match_status to "perfect_match" after successful copy operation
    """
    
    def post(self, request):
        """POST: Handle manual match by copying values"""
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
            swap_direction = body.get('swap_direction')
            fields_to_swap = body.get('fields_to_swap', ['all'])
            user = body.get('user', 'system')
            
            # Validate required fields
            if invoice_data_id is None or swap_direction is None:
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id and swap_direction are required'
                }, status=400)
            
            # Validate swap_direction
            if swap_direction not in ['invoice_to_grn', 'grn_to_invoice']:
                return JsonResponse({
                    'success': False,
                    'error': 'swap_direction must be "invoice_to_grn" or "grn_to_invoice"'
                }, status=400)
            
            # Validate fields_to_swap
            allowed_fields = ['description', 'quantity', 'unit_price', 'total_amount', 'hsn', 'unit', 'subtotal', 'cgst', 'sgst', 'igst', 'all']
            if not isinstance(fields_to_swap, list) or not all(field in allowed_fields for field in fields_to_swap):
                return JsonResponse({
                    'success': False,
                    'error': f'fields_to_swap must be a list containing values from: {allowed_fields}'
                }, status=400)
            
            # Find reconciliation records by invoice_data_id
            try:
                reconciliation_records = InvoiceItemReconciliation.objects.filter(
                    invoice_data_id=invoice_data_id
                )
                
                if not reconciliation_records.exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'No reconciliation records found for invoice_data_id: {invoice_data_id}'
                    }, status=404)
                
                # Check if any record has perfect_match status
                perfect_match_records = reconciliation_records.filter(match_status='perfect_match')
                if perfect_match_records.exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'Cannot perform manual matching on invoice_data_id {invoice_data_id}: {perfect_match_records.count()} record(s) already have perfect_match status',
                        'perfect_match_items': list(perfect_match_records.values_list('invoice_item_sequence', flat=True))
                    }, status=400)
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error finding reconciliation records: {str(e)}'
                }, status=500)
            
            # Perform COPY operation for all reconciliation records
            with transaction.atomic():
                processed_records = []
                total_copied_fields = 0
                
                logger.info(f"[ManualMatchAPI] Starting COPY operation for invoice_data_id {invoice_data_id}")
                logger.info(f"[ManualMatchAPI] Found {reconciliation_records.count()} reconciliation records")
                logger.info(f"[ManualMatchAPI] Copy direction: {swap_direction}")
                logger.info(f"[ManualMatchAPI] Fields to copy: {fields_to_swap}")
                
                # Process each reconciliation record
                for reconciliation in reconciliation_records:
                    copied_values = {}
                    
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
                    reconciliation.manual_match = True
                    reconciliation.is_auto_matched = False
                    reconciliation.reconciliation_notes = (
                        f"{reconciliation.reconciliation_notes or ''}\n"
                        f"Manual match performed by {user} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. "
                        f"Copy direction: {swap_direction}. "
                        f"Original status: {original_match_status}. "
                        f"Fields copied: {', '.join(fields_to_swap)}. "
                        f"Status changed to perfect_match after manual copy."
                    ).strip()
                    
                    # Recalculate variances after copying (should be zero since both sides are now identical)
                    self._recalculate_variances(reconciliation)
                    
                    # Save the changes
                    reconciliation.save()
                    
                    # Store processed record info
                    processed_records.append({
                        'reconciliation_id': reconciliation.id,
                        'item_sequence': reconciliation.invoice_item_sequence,
                        'original_status': original_match_status,
                        'new_status': reconciliation.match_status,
                        'copied_fields_count': len(field_mappings),
                        'invoice_item_description': reconciliation.invoice_item_description,
                        'grn_item_description': reconciliation.grn_item_description,
                        'copied_values': copied_values
                    })
                    
                    total_copied_fields += len(field_mappings)
                
                # Log the successful copy operation
                logger.info(f"[ManualMatchAPI] Manual copy completed for invoice_data_id {invoice_data_id}")
                logger.info(f"[ManualMatchAPI] Processed {len(processed_records)} records")
                logger.info(f"[ManualMatchAPI] All records status changed to perfect_match")
                
                # Determine operation description
                if swap_direction == 'invoice_to_grn':
                    operation_description = "Copied Invoice data to GRN fields"
                else:
                    operation_description = "Copied GRN data to Invoice fields"
                
                # Prepare detailed response
                response_data = {
                    'success': True,
                    'message': f'Manual copy completed successfully for {len(processed_records)} item(s). {operation_description}. All records now have perfect_match status.',
                    'data': {
                        'invoice_data_id': invoice_data_id,
                        'records_processed': len(processed_records),
                        'total_fields_copied': total_copied_fields,
                        'new_match_status': 'perfect_match',
                        'copy_direction': swap_direction,
                        'operation_performed': operation_description,
                        'fields_copied': fields_to_swap,
                        'performed_by': user,
                        'performed_at': datetime.now().isoformat(),
                        'processed_items': processed_records,
                        'summary': {
                            'all_items_now_perfect_match': True,
                            'manual_match_flag_set': True,
                            'auto_matched_flag_cleared': True,
                            'operation_type': 'copy' 
                        }
                    }
                }
                
                return JsonResponse(response_data, status=200)
                
        except Exception as e:
            logger.error(f"[ManualMatchAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Internal server error occurred',
                'details': str(e)
            }, status=500)
    
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