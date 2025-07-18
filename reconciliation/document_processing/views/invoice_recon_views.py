import asyncio
import json
import logging
from typing import List, Dict, Any
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from document_processing.utils.invoice_recon import run_rule_based_reconciliation
from document_processing.utils.item_recon import run_item_wise_reconciliation
from document_processing.models import InvoiceData, GrnSummary, InvoiceGrnReconciliation, InvoiceItemReconciliation, InvoiceItemData, ItemWiseGrn
from asgiref.sync import sync_to_async
from django.db.models import Q

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class RuleBasedReconciliationAPI(View):
    """
    Unified Rule-Based Reconciliation Endpoint
    
    SINGLE URL that performs BOTH:
    1. Invoice-level reconciliation (InvoiceData vs GrnSummary)
    2. Item-level reconciliation (InvoiceItemData vs ItemWiseGrn)
    3. Updates GRN Summary status after completion
    
    Same API endpoint as before: /api/reconciliation/
    """
    
    def post(self, request):
        """
        POST: Start unified reconciliation (Invoice + Item level automatically)
        
        Request Body (JSON):
        {
            "invoice_ids": [1, 2, 3] (optional - if not provided, processes all),
            "tolerance_percentage": 2.0 (optional - default: 2.0%),
            "date_tolerance_days": 30 (optional - default: 30 days),
            "batch_size": 100 (optional - default: 100),
            "skip_item_reconciliation": false (optional - set true to skip item-level)
        }
        """
        return asyncio.run(self._async_post(request))
    
    async def _async_post(self, request):
        try:
            # Parse parameters
            if request.content_type == 'application/json':
                body = json.loads(request.body.decode('utf-8'))
                invoice_ids = body.get('invoice_ids', None)
                tolerance_percentage = float(body.get('tolerance_percentage', 2.0))
                date_tolerance_days = int(body.get('date_tolerance_days', 30))
                batch_size = int(body.get('batch_size', 100))
                skip_item_reconciliation = body.get('skip_item_reconciliation', False)
            else:
                # Form data support
                invoice_ids_str = request.POST.get('invoice_ids', None)
                if invoice_ids_str:
                    invoice_ids = json.loads(invoice_ids_str)
                else:
                    invoice_ids = None
                tolerance_percentage = float(request.POST.get('tolerance_percentage', 2.0))
                date_tolerance_days = int(request.POST.get('date_tolerance_days', 30))
                batch_size = int(request.POST.get('batch_size', 100))
                skip_item_reconciliation = request.POST.get('skip_item_reconciliation', 'false').lower() == 'true'
            
            # Validate parameters
            if tolerance_percentage < 0 or tolerance_percentage > 50:
                return JsonResponse({
                    'success': False,
                    'error': 'tolerance_percentage must be between 0 and 50'
                }, status=400)
            
            if date_tolerance_days < 0 or date_tolerance_days > 365:
                return JsonResponse({
                    'success': False,
                    'error': 'date_tolerance_days must be between 0 and 365'
                }, status=400)
            
            if batch_size < 5 or batch_size > 500:
                return JsonResponse({
                    'success': False,
                    'error': 'batch_size must be between 5 and 500'
                }, status=400)
            
            # Get data counts for logging
            total_invoices = await sync_to_async(InvoiceData.objects.filter(processing_status='completed').count)()
            total_grn_summaries = await sync_to_async(GrnSummary.objects.count)()
            
            if invoice_ids:
                invoices_to_process = len(invoice_ids)
                total_invoice_items = await sync_to_async(
                    lambda: InvoiceItemData.objects.filter(invoice_data_id__in=invoice_ids).count()
                )()
            else:
                invoices_to_process = total_invoices
                total_invoice_items = await sync_to_async(InvoiceItemData.objects.count)()
            
            total_grn_items = await sync_to_async(ItemWiseGrn.objects.count)()
            
            logger.info(f"=== UNIFIED RECONCILIATION STARTED ===")
            logger.info(f"Invoice-level: {total_invoices} invoices, {total_grn_summaries} GRN summaries")
            logger.info(f"Item-level: {total_invoice_items} invoice items, {total_grn_items} GRN items")
            logger.info(f"Processing: {invoices_to_process} invoices")
            logger.info(f"Settings: tolerance={tolerance_percentage}%, date_tolerance={date_tolerance_days} days")
            logger.info(f"Skip item reconciliation: {skip_item_reconciliation}")
            
            # Check if GRN summaries exist
            if total_grn_summaries == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'No GRN summaries found. Please ensure GRN data has been processed and aggregated into GrnSummary table.',
                    'suggestion': 'Upload ItemWiseGrn data first, which will automatically create GRN summaries.'
                }, status=400)
            
            # =================================================================
            # STEP 1: INVOICE-LEVEL RECONCILIATION
            # =================================================================
            logger.info("STEP 1: Running invoice-level reconciliation...")
            invoice_result = await run_rule_based_reconciliation(
                invoice_ids=invoice_ids,
                tolerance_percentage=tolerance_percentage,
                date_tolerance_days=date_tolerance_days,
                batch_size=batch_size
            )
            
            if not invoice_result['success']:
                return JsonResponse({
                    'success': False,
                    'error': f"Invoice-level reconciliation failed: {invoice_result['error']}",
                    'stats': invoice_result['stats']
                }, status=500)
            
            logger.info(f"Invoice-level completed: {invoice_result['total_processed']} invoices processed")
            
            # =================================================================
            # STEP 2: ITEM-LEVEL RECONCILIATION (unless skipped)
            # =================================================================
            item_result = None
            if not skip_item_reconciliation:
                logger.info("🔄 STEP 2: Running item-level reconciliation...")
                item_result = await run_item_wise_reconciliation(
                    invoice_ids=invoice_ids,
                    tolerance_percentage=tolerance_percentage
                )
                
                if item_result['success']:
                    logger.info(f"Item-level completed: {item_result['total_items_processed']} items processed")
                else:
                    logger.warning(f"Item-level failed: {item_result['error']}")
            else:
                logger.info("STEP 2: Item-level reconciliation skipped by request")
            
            # =================================================================
            # STEP 3: UPDATE GRN SUMMARY STATUS
            # =================================================================
            logger.info("🔄 STEP 3: Updating GRN Summary reconciliation status...")
            grn_status_update_result = await self._update_grn_summary_status(invoice_ids)
            
            if grn_status_update_result['success']:
                logger.info(f"GRN status updated: {grn_status_update_result['total_grn_summaries_updated']} summaries")
            else:
                logger.warning(f"GRN status update failed: {grn_status_update_result['error']}")
            
            # =================================================================
            # PREPARE UNIFIED RESPONSE
            # =================================================================
            logger.info("📊 Preparing unified response...")
            
            response_data = {
                'success': True,
                'message': f"Unified reconciliation completed: {invoice_result['total_processed']} invoices processed",
                'status': 'completed',
                'reconciliation_levels': {
                    'invoice_level': True,
                    'item_level': not skip_item_reconciliation,
                    'grn_status_update': True
                },
                'data': {
                    # INVOICE-LEVEL RESULTS
                    'invoice_reconciliation': {
                        'batch_id': invoice_result['batch_id'],
                        'total_processed': invoice_result['total_processed'],
                        'invoices_available': total_invoices,
                        'grn_summaries_available': total_grn_summaries,
                        'success_rate': f"{invoice_result['total_processed']}/{invoices_to_process}",
                        'processing_method': 'Rule-Based Matching (No LLM)',
                        'statistics': {
                            'perfect_matches': invoice_result['stats'].get('perfect_matches', 0),
                            'partial_matches': invoice_result['stats'].get('partial_matches', 0),
                            'amount_mismatches': invoice_result['stats'].get('amount_mismatches', 0),
                            'vendor_mismatches': invoice_result['stats'].get('vendor_mismatches', 0),
                            'date_mismatches': invoice_result['stats'].get('date_mismatches', 0),
                            'no_matches': invoice_result['stats'].get('no_matches', 0),
                            'errors': invoice_result['stats'].get('errors', 0)
                        }
                    },
                    
                    # GRN STATUS UPDATE RESULTS
                    'grn_status_update': grn_status_update_result,
                    
                    # CONFIGURATION
                    'reconciliation_config': {
                        'tolerance_percentage': tolerance_percentage,
                        'date_tolerance_days': date_tolerance_days,
                        'batch_size': batch_size,
                        'skip_item_reconciliation': skip_item_reconciliation,
                        'uses_llm': False,
                        'data_sources': {
                            'invoice_level': 'InvoiceData + GrnSummary',
                            'item_level': 'InvoiceItemData + ItemWiseGrn'
                        }
                    },
                    
                    # FIELD MAPPINGS
                    'field_mappings': {
                        'invoice_level': {
                            'po_number': 'po_number (exact match)',
                            'grn_number': 'grn_number (exact match)',
                            'invoice_number': 'seller_invoice_number (exact match)',
                            'vendor_name': 'supplier_name (fuzzy match)',
                            'vendor_gst': 'pickup_gstin (exact match)',
                            'invoice_date': 'supplier_invoice_date (tolerance check)',
                            'amounts': 'aggregated_amounts (tolerance check)'
                        },
                        'item_level': {
                            'po_number': 'po_no (exact match)',
                            'invoice_number': 'seller_invoice_no (exact match)',
                            'hsn_code': 'hsn_no (exact match)',
                            'item_description': 'item_name (similarity matching)',
                            'quantity': 'received_qty (tolerance check)',
                            'unit_price': 'price (tolerance check)',
                            'item_total': 'total (tolerance check)'
                        }
                    }
                }
            }
            
            # Add item-level results if processed
            if item_result and item_result['success']:
                response_data['data']['item_reconciliation'] = {
                    'total_items_processed': item_result['total_items_processed'],
                    'items_available': total_invoice_items,
                    'grn_items_available': total_grn_items,
                    'processing_method': 'Rule-Based Item Matching',
                    'statistics': {
                        'perfect_matches': item_result['stats'].get('perfect_matches', 0),
                        'partial_matches': item_result['stats'].get('partial_matches', 0),
                        'quantity_mismatches': item_result['stats'].get('quantity_mismatches', 0),
                        'price_mismatches': item_result['stats'].get('price_mismatches', 0),
                        'hsn_mismatches': item_result['stats'].get('hsn_mismatches', 0),
                        'description_mismatches': item_result['stats'].get('description_mismatches', 0),
                        'no_matches': item_result['stats'].get('no_matches', 0),
                        'errors': item_result['stats'].get('errors', 0)
                    }
                }
            elif not skip_item_reconciliation:
                response_data['data']['item_reconciliation'] = {
                    'status': 'failed',
                    'error': item_result['error'] if item_result else 'Unknown error'
                }
            else:
                response_data['data']['item_reconciliation'] = {
                    'status': 'skipped',
                    'reason': 'skip_item_reconciliation = true'
                }
            
            logger.info("=== UNIFIED RECONCILIATION COMPLETED ===")
            return JsonResponse(response_data, status=200)
                
        except Exception as e:
            logger.error(f"Error in unified reconciliation API: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Unified reconciliation failed: {str(e)}'
            }, status=500)
    
    async def _update_grn_summary_status(self, invoice_ids: List[int] = None) -> Dict[str, Any]:
        """
        Update GRN Summary reconciliation status based on reconciliation results
        """
        try:
            logger.info("Updating GRN Summary reconciliation status...")
            
            # Get reconciled invoice data
            if invoice_ids:
                reconciled_invoices = await sync_to_async(list)(
                    InvoiceGrnReconciliation.objects.filter(
                        invoice_data_id__in=invoice_ids,
                        match_status__in=['perfect_match', 'partial_match']
                    ).values('grn_number', 'po_number', 'match_status')
                )
            else:
                reconciled_invoices = await sync_to_async(list)(
                    InvoiceGrnReconciliation.objects.filter(
                        match_status__in=['perfect_match', 'partial_match']
                    ).values('grn_number', 'po_number', 'match_status')
                )
            
            # Group by GRN number to determine status
            grn_status_map = {}
            for recon in reconciled_invoices:
                grn_key = f"{recon['grn_number']}_{recon['po_number']}"
                if grn_key not in grn_status_map:
                    grn_status_map[grn_key] = []
                grn_status_map[grn_key].append(recon['match_status'])
            
            # Update GRN summaries
            updated_count = 0
            perfect_match_count = 0
            partial_match_count = 0
            
            for grn_key, match_statuses in grn_status_map.items():
                grn_number, po_number = grn_key.rsplit('_', 1)
                
                # Determine overall status for this GRN
                if all(status == 'perfect_match' for status in match_statuses):
                    reconciliation_status = 'matched'  # Changed to 'matched' for perfect
                    perfect_match_count += 1
                elif any(status in ['perfect_match', 'partial_match'] for status in match_statuses):
                    reconciliation_status = 'variance'  # Changed to 'variance' for partial
                    partial_match_count += 1
                else:
                    continue  # Skip if no good matches
                
                # Update GRN summary
                try:
                    grn_summary = await sync_to_async(GrnSummary.objects.get)(
                        grn_number=grn_number,
                        po_number=po_number
                    )
                    
                    grn_summary.is_reconciled = True
                    grn_summary.reconciliation_status = reconciliation_status
                    await sync_to_async(grn_summary.save)(update_fields=['is_reconciled', 'reconciliation_status'])
                    updated_count += 1
                    
                    logger.info(f"Updated GRN Summary {grn_number} (PO: {po_number}) - Status: {reconciliation_status}")
                    
                except GrnSummary.DoesNotExist:
                    logger.warning(f"GRN Summary not found: {grn_number} (PO: {po_number})")
                    continue
                except Exception as e:
                    logger.error(f"Error updating GRN Summary {grn_number}: {str(e)}")
                    continue
            
            logger.info(f"GRN Summary status update completed: {updated_count} summaries updated")
            
            return {
                'success': True,
                'total_grn_summaries_updated': updated_count,
                'perfect_match_grns': perfect_match_count,
                'partial_match_grns': partial_match_count,
                'status_breakdown': {
                    'reconciled_grns': updated_count,
                    'matched_status': perfect_match_count,  # is_reconciled=True, reconciliation_status='matched'
                    'variance_status': partial_match_count  # is_reconciled=True, reconciliation_status='variance'
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating GRN Summary status: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'total_grn_summaries_updated': 0
            }