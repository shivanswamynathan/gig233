import asyncio
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from document_processing.utils.invoice_recon import run_rule_based_reconciliation
from document_processing.models import InvoiceData, GrnSummary
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class RuleBasedReconciliationAPI(View):
    """
    Rule-Based Reconciliation Endpoint (No LLM Required)
    
    Uses direct field mapping and threshold-based matching with GrnSummary table
    """
    
    def post(self, request):
        """
        POST: Start rule-based reconciliation
        
        Request Body (JSON):
        {
            "invoice_ids": [1, 2, 3] (optional - if not provided, processes all),
            "tolerance_percentage": 2.0 (optional - default: 2.0%),
            "date_tolerance_days": 30 (optional - default: 30 days),
            "batch_size": 100 (optional - default: 100)
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
            
            # Get data counts
            total_invoices = await sync_to_async(InvoiceData.objects.filter(processing_status='completed').count)()
            total_grn_summaries = await sync_to_async(GrnSummary.objects.count)()
            
            if invoice_ids:
                invoices_to_process = len(invoice_ids)
            else:
                invoices_to_process = total_invoices
            
            logger.info(f"Starting Rule-Based reconciliation")
            logger.info(f"Data: {total_invoices} invoices, {total_grn_summaries} GRN summaries")
            logger.info(f"Settings: {invoices_to_process} to process, tolerance={tolerance_percentage}%, date_tolerance={date_tolerance_days} days")
            
            # Check if GRN summaries exist
            if total_grn_summaries == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'No GRN summaries found. Please ensure GRN data has been processed and aggregated into GrnSummary table.',
                    'suggestion': 'Upload ItemWiseGrn data first, which will automatically create GRN summaries.'
                }, status=400)
            
            # Run rule-based reconciliation
            result = await run_rule_based_reconciliation(
                invoice_ids=invoice_ids,
                tolerance_percentage=tolerance_percentage,
                date_tolerance_days=date_tolerance_days,
                batch_size=batch_size
            )
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': f"Rule-based reconciliation completed: {result['total_processed']} invoices processed",
                    'data': {
                        'processing_summary': {
                            'batch_id': result['batch_id'],
                            'total_processed': result['total_processed'],
                            'invoices_available': total_invoices,
                            'grn_summaries_available': total_grn_summaries,
                            'success_rate': f"{result['total_processed']}/{invoices_to_process}",
                            'processing_method': 'Rule-Based Matching (No LLM)'
                        },
                        'match_statistics': {
                            'perfect_matches': result['stats'].get('perfect_matches', 0),
                            'partial_matches': result['stats'].get('partial_matches', 0),
                            'amount_mismatches': result['stats'].get('amount_mismatches', 0),
                            'vendor_mismatches': result['stats'].get('vendor_mismatches', 0),
                            'date_mismatches': result['stats'].get('date_mismatches', 0),
                            'no_matches': result['stats'].get('no_matches', 0),
                            'errors': result['stats'].get('errors', 0)
                        },
                        'reconciliation_config': {
                            'tolerance_percentage': tolerance_percentage,
                            'date_tolerance_days': date_tolerance_days,
                            'batch_size': batch_size,
                            'uses_llm': False,
                            'data_source': 'GrnSummary table'
                        },
                        'field_mappings_used': {
                            'po_number': 'po_number (exact match)',
                            'grn_number': 'grn_number (exact match)',
                            'invoice_number': 'seller_invoice_number (exact match)',
                            'vendor_name': 'supplier_name (fuzzy match)',
                            'vendor_gst': 'pickup_gstin (exact match)',
                            'invoice_date': 'supplier_invoice_date (tolerance check)',
                            'invoice_value_without_gst': 'total_subtotal (tolerance check)',
                            'cgst_amount': 'total_cgst_amount (tolerance check)',
                            'sgst_amount': 'total_sgst_amount (tolerance check)',
                            'igst_amount': 'total_igst_amount (tolerance check)',
                            'invoice_total_post_gst': 'total_amount (tolerance check)'
                        }
                    }
                }, status=200)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f"Rule-based reconciliation failed: {result['error']}",
                    'stats': result['stats']
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error in rule-based reconciliation API: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Rule-based reconciliation failed: {str(e)}'
            }, status=500)
