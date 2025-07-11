import logging
from typing import Dict, List, Any
from django.db import transaction
from django.db.models import Sum, Count, Q
from decimal import Decimal
from datetime import datetime
from document_processing.models import ItemWiseGrn, GrnSummary

logger = logging.getLogger(__name__)

def aggregate_grn_data(batch_id: str = None) -> Dict[str, Any]:
    """
    Aggregate GRN data using GRN Number + PO Number + Seller Invoice Number
    
    Args:
        batch_id: Batch ID that triggered this aggregation (for logging)
        
    Returns:
        Processing results
    """
    try:
        logger.info(f"Starting multi-field GRN aggregation (triggered by batch: {batch_id})")
        
        # Get unique combinations of GRN + PO + Seller Invoice
        unique_combinations = ItemWiseGrn.objects.values(
            'grn_no', 'po_no', 'seller_invoice_no'
        ).distinct()
        
        # Filter out records with missing key fields
        valid_combinations = [
            combo for combo in unique_combinations 
            if combo['grn_no'] and combo['po_no']  # GRN and PO are required
        ]
        
        if not valid_combinations:
            return {
                'success': True,
                'message': 'No valid GRN combinations found',
                'total_processed': 0,
                'created_count': 0,
                'updated_count': 0
            }
        
        logger.info(f"Found {len(valid_combinations)} unique GRN combinations (GRN + PO + Invoice)")
        
        created_count = 0
        updated_count = 0
        
        with transaction.atomic():
            for combo in valid_combinations:
                grn_no = combo['grn_no']
                po_no = combo['po_no']
                seller_invoice_no = combo['seller_invoice_no'] or ''
                
                # Create a unique identifier for this combination
                summary_key = f"{grn_no}|{po_no}|{seller_invoice_no}"
                
                logger.info(f"Processing combination: GRN={grn_no}, PO={po_no}, Invoice={seller_invoice_no}")
                
                # Filter items by all three fields
                filter_criteria = {
                    'grn_no': grn_no,
                    'po_no': po_no,
                }
                
                # Handle seller_invoice_no (can be null/empty)
                if seller_invoice_no:
                    filter_criteria['seller_invoice_no'] = seller_invoice_no
                else:
                    filter_criteria['seller_invoice_no__isnull'] = True
                
                grn_items = ItemWiseGrn.objects.filter(**filter_criteria)
                
                if not grn_items.exists():
                    logger.warning(f"No items found for combination: {summary_key}")
                    continue
                
                logger.info(f"Found {grn_items.count()} items for combination: {summary_key}")
                
                # Check if summary exists using composite key
                summary, created = GrnSummary.objects.get_or_create(
                    grn_number=grn_no,
                    po_number=po_no,
                    seller_invoice_number=seller_invoice_no,
                    defaults={
                        'created_at': datetime.now(),
                        'upload_batch_id': batch_id or ''
                    }
                )
                
                # Get first item for header data
                first_item = grn_items.first()
                
                # Aggregate amounts from items matching all criteria
                aggregated_data = grn_items.aggregate(
                    total_items=Count('id'),
                    total_received_qty=Sum('received_qty'),
                    total_subtotal=Sum('subtotal'),
                    total_cgst=Sum('cgst_tax_amount'),
                    total_sgst=Sum('sgst_tax_amount'),
                    total_igst=Sum('igst_tax_amount'),
                    total_tax=Sum('tax_amount'),
                    total_amount=Sum('total')
                )
                
                # Update summary fields
                summary.supplier_name = first_item.supplier or ''
                summary.grn_created_date = first_item.grn_created_at
                summary.supplier_invoice_date = first_item.supplier_invoice_date
                
                # Location details
                summary.pickup_location = first_item.pickup_location or ''
                summary.pickup_gstin = first_item.pickup_gstin or ''
                summary.pickup_city = first_item.pickup_city or ''
                summary.pickup_state = first_item.pickup_state or ''
                summary.delivery_location = first_item.delivery_location or ''
                summary.delivery_gstin = first_item.delivery_gstin or ''
                summary.delivery_city = first_item.delivery_city or ''
                summary.delivery_state = first_item.delivery_state or ''
                
                # Aggregated amounts
                summary.total_items_count = aggregated_data['total_items'] or 0
                summary.total_received_quantity = aggregated_data['total_received_qty']
                summary.total_subtotal = aggregated_data['total_subtotal']
                summary.total_cgst_amount = aggregated_data['total_cgst']
                summary.total_sgst_amount = aggregated_data['total_sgst']
                summary.total_igst_amount = aggregated_data['total_igst']
                summary.total_tax_amount = aggregated_data['total_tax']
                summary.total_amount = aggregated_data['total_amount']
                
                # Metadata
                summary.created_by = first_item.created_by or ''
                summary.concerned_person = first_item.concerned_person or ''
                summary.last_aggregated_at = datetime.now()
                
                # Update batch info
                if created:
                    summary.upload_batch_id = batch_id or first_item.upload_batch_id or ''
                
                summary.save()
                
                if created:
                    created_count += 1
                    logger.info(f"Created GRN summary: GRN={grn_no}, PO={po_no}, Items={summary.total_items_count}, Total=₹{summary.total_amount}")
                else:
                    updated_count += 1
                    logger.info(f"Updated GRN summary: GRN={grn_no}, PO={po_no}, Items={summary.total_items_count}, Total=₹{summary.total_amount}")
        
        logger.info(f"Multi-field GRN aggregation completed: {created_count} created, {updated_count} updated")
        
        return {
            'success': True,
            'triggered_by_batch': batch_id,
            'total_processed': len(valid_combinations),
            'created_count': created_count,
            'updated_count': updated_count,
            'message': f'Processed {len(valid_combinations)} unique GRN combinations (GRN + PO + Invoice)',
            'grouping_method': 'grn_number + po_number + seller_invoice_number'
        }
        
    except Exception as e:
        logger.error(f"Multi-field GRN aggregation failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'triggered_by_batch': batch_id
        }