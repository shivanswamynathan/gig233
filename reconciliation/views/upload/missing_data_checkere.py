from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from document_processing.models import ItemWiseGrn
import logging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class CheckMissingDataAPI(View):
    """
    API endpoint to check ItemWiseGrn records and update missing data flags
    
    POST /api/check-missing-data/
    
    Checks:
    1. If po_no is missing/empty -> sets missing_po = True
    2. If grn_no is missing/empty -> sets missing_grn = True  
    3. If all attachments (attachment_1 to attachment_5) are missing/empty -> sets missing_invoice = True
    
    Optional Parameters (JSON):
    {
        "batch_id": "specific_batch_id" (optional - check only specific batch),
        "reset_flags": false (optional - reset all flags to False before checking)
    }
    """
    
    def post(self, request):
        """POST: Check and update missing data flags for ItemWiseGrn records"""
        try:
            # Parse request body if JSON
            batch_id = None
            reset_flags = False
            
            if request.content_type == 'application/json':
                import json
                try:
                    body = json.loads(request.body.decode('utf-8'))
                    batch_id = body.get('batch_id')
                    reset_flags = body.get('reset_flags', False)
                except json.JSONDecodeError:
                    pass
            else:
                # Form data support
                batch_id = request.POST.get('batch_id')
                reset_flags = request.POST.get('reset_flags', 'false').lower() == 'true'
            
            logger.info(f"[CheckMissingDataAPI] Starting missing data check. Batch ID: {batch_id}, Reset flags: {reset_flags}")
            
            # Build queryset
            if batch_id:
                queryset = ItemWiseGrn.objects.filter(upload_batch_id=batch_id)
                logger.info(f"Checking specific batch: {batch_id}")
            else:
                queryset = ItemWiseGrn.objects.all()
                logger.info("Checking all ItemWiseGrn records")
            
            total_records = queryset.count()
            if total_records == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'No ItemWiseGrn records found to check',
                    'batch_id': batch_id
                }, status=404)
            
            # Initialize counters
            updated_counts = {
                'missing_po_updated': 0,
                'missing_grn_updated': 0,
                'missing_invoice_updated': 0,
                'reset_flags_count': 0,
                'total_processed': 0
            }
            
            # Process records in batches for better performance
            batch_size = 1000
            
            with transaction.atomic():
                # Optional: Reset all flags first
                if reset_flags:
                    reset_count = queryset.update(
                        missing_po=False,
                        missing_grn=False, 
                        missing_invoice=False
                    )
                    updated_counts['reset_flags_count'] = reset_count
                    logger.info(f"Reset flags for {reset_count} records")
                
                # Process records in batches
                for offset in range(0, total_records, batch_size):
                    batch_records = list(queryset[offset:offset + batch_size])
                    
                    records_to_update = []
                    
                    for record in batch_records:
                        updated_counts['total_processed'] += 1
                        update_needed = False
                        
                        # Check 1: Missing PO
                        if self._is_field_missing(record.po_no):
                            if not record.missing_po:  # Only update if not already True
                                record.missing_po = True
                                update_needed = True
                                updated_counts['missing_po_updated'] += 1
                        
                        # Check 2: Missing GRN
                        if self._is_field_missing(record.grn_no):
                            if not record.missing_grn:  # Only update if not already True
                                record.missing_grn = True
                                update_needed = True
                                updated_counts['missing_grn_updated'] += 1
                        
                        # Check 3: Missing Invoice (all attachments empty)
                        if self._are_all_attachments_missing(record):
                            if not record.missing_invoice:  # Only update if not already True
                                record.missing_invoice = True
                                update_needed = True
                                updated_counts['missing_invoice_updated'] += 1
                        
                        # Add to update list if changes needed
                        if update_needed:
                            records_to_update.append(record)
                    
                    # Bulk update records that need changes
                    if records_to_update:
                        ItemWiseGrn.objects.bulk_update(
                            records_to_update,
                            ['missing_po', 'missing_grn', 'missing_invoice'],
                            batch_size=500
                        )
                        logger.info(f"Updated batch of {len(records_to_update)} records (offset: {offset})")
            
            # Log summary
            logger.info(f"[CheckMissingDataAPI] Completed missing data check:")
            logger.info(f"  Total records processed: {updated_counts['total_processed']}")
            logger.info(f"  Missing PO flags set: {updated_counts['missing_po_updated']}")
            logger.info(f"  Missing GRN flags set: {updated_counts['missing_grn_updated']}")  
            logger.info(f"  Missing Invoice flags set: {updated_counts['missing_invoice_updated']}")
            
            # Get final statistics
            final_stats = self._get_missing_data_statistics(batch_id)
            
            # Return success response
            return JsonResponse({
                'success': True,
                'message': f'Missing data check completed for {updated_counts["total_processed"]} records',
                'batch_id': batch_id,
                'data': {
                    'processing_summary': {
                        'total_records_checked': updated_counts['total_processed'],
                        'missing_po_flags_set': updated_counts['missing_po_updated'],
                        'missing_grn_flags_set': updated_counts['missing_grn_updated'],
                        'missing_invoice_flags_set': updated_counts['missing_invoice_updated'],
                        'flags_reset_count': updated_counts['reset_flags_count'] if reset_flags else 0
                    },
                    'current_statistics': final_stats,
                    'check_criteria': {
                        'missing_po': 'po_no is null or empty string',
                        'missing_grn': 'grn_no is null or empty string',
                        'missing_invoice': 'all attachment_1 to attachment_5 are null or empty'
                    }
                }
            }, status=200)
            
        except Exception as e:
            logger.error(f"[CheckMissingDataAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Failed to check missing data: {str(e)}',
                'batch_id': batch_id
            }, status=500)
    
    def _is_field_missing(self, field_value):
        """
        Check if a field is considered missing
        
        Args:
            field_value: Field value to check
            
        Returns:
            bool: True if field is missing (None, empty string, or whitespace only)
        """
        if field_value is None:
            return True
        if isinstance(field_value, str) and field_value.strip() == '':
            return True
        return False
    
    def _are_all_attachments_missing(self, record):
        """
        Check if all attachment fields (attachment_1 to attachment_5) are missing
        
        Args:
            record: ItemWiseGrn record instance
            
        Returns:
            bool: True if all attachments are missing
        """
        attachment_fields = [
            record.attachment_1,
            record.attachment_2, 
            record.attachment_3,
            record.attachment_4,
            record.attachment_5
        ]
        
        # Check if all attachments are missing (None, empty, or invalid URLs)
        for attachment in attachment_fields:
            if attachment and isinstance(attachment, str):
                attachment_clean = attachment.strip()
                # If any attachment has a valid URL, return False
                if attachment_clean and (attachment_clean.startswith('http://') or attachment_clean.startswith('https://')):
                    return False
        
        return True  # All attachments are missing
    
    def _get_missing_data_statistics(self, batch_id=None):
        """
        Get current statistics of missing data flags
        
        Args:
            batch_id: Optional batch ID to filter by
            
        Returns:
            dict: Statistics of missing data
        """
        try:
            from django.db import models
            
            if batch_id:
                queryset = ItemWiseGrn.objects.filter(upload_batch_id=batch_id)
            else:
                queryset = ItemWiseGrn.objects.all()
            
            total_records = queryset.count()
            missing_po_count = queryset.filter(missing_po=True).count()
            missing_grn_count = queryset.filter(missing_grn=True).count()
            missing_invoice_count = queryset.filter(missing_invoice=True).count()
            
            # Records with any missing data
            any_missing_count = queryset.filter(
                models.Q(missing_po=True) | 
                models.Q(missing_grn=True) | 
                models.Q(missing_invoice=True)
            ).count()
            
            # Records with all data complete
            complete_records = total_records - any_missing_count
            
            return {
                'total_records': total_records,
                'complete_records': complete_records,
                'records_with_missing_data': any_missing_count,
                'missing_po_records': missing_po_count,
                'missing_grn_records': missing_grn_count,
                'missing_invoice_records': missing_invoice_count,
                'completion_rate': f"{(complete_records/total_records*100):.1f}%" if total_records > 0 else "0%"
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {
                'error': 'Could not calculate statistics',
                'details': str(e)
            }