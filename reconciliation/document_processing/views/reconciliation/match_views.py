from django.http import JsonResponse
from datetime import datetime
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Count, Sum, Avg
from document_processing.models import InvoiceGrnReconciliation,InvoiceItemReconciliation, InvoiceData, GrnSummary,InvoiceItemData
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
import logging
import json
from django.db import transaction
from datetime import datetime
import calendar
logger = logging.getLogger(__name__)

class ReconciliationDetailAPI(APIView):
    """
    Reconciliation Detail API with summary and detailed views
    
    Query Parameters:
    - summary: true/false (default: false)
    - include_details: true/false (default: false)
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    - month: 1-12
    - year: YYYY
    - po_number: string (partial match)
    - vendor: string (partial match)
    
    Examples:
    - Details only: /api/reconciliation/?month=6&year=2025
    - Summary + Details: /api/reconciliation/?summary=true&include_details=true&month=6&year=2025
    """

    def get(self, request):
        try:
            summary_only = request.query_params.get('summary', 'false').lower() == 'true'
            include_details = request.query_params.get('include_details', 'false').lower() == 'true'

            if summary_only and include_details:
                # Summary + Details
                return Response({
                    "success": True,
                    "data": [
                        {"summary": [self.get_summary_data(request)]},
                        {"details": self.get_detailed_data(request)},
                        {"filters_applied": [self.get_applied_filters(request)]}
                    ]
                }, status=status.HTTP_200_OK)

            # Details only (default)
            return Response({
                "success": True,
                "data": [
                    {"details": self.get_detailed_data(request)},
                    {"filters_applied": [self.get_applied_filters(request)]}
                ]
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Error in reconciliation detail API")
            return Response({
                "success": False,
                "message": "Internal Server Error",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_applied_filters(self, request):
        """Get the filters that were applied"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        po_number = request.query_params.get('po_number')
        vendor = request.query_params.get('vendor')

        # Handle month/year conversion for display
        if month and year:
            start_date = f"{year}-{month.zfill(2)}-01"
            last_day = calendar.monthrange(int(year), int(month))[1]
            end_date = f"{year}-{month.zfill(2)}-{last_day:02d}"

        return {
            "start_date": start_date,
            "end_date": end_date,
            "month": month,
            "year": year,
            "po_number": po_number,
            "vendor": vendor
        }

    def get_summary_data(self, request):
        """Returns summary dictionary based on item-level analysis"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        po_number = request.query_params.get('po_number')
        vendor = request.query_params.get('vendor')

        # Handle month/year conversion
        if month and year:
            start_date = f"{year}-{month.zfill(2)}-01"
            last_day = calendar.monthrange(int(year), int(month))[1]
            end_date = f"{year}-{month.zfill(2)}-{last_day:02d}"

        # Build invoice-level filters
        invoice_filters = Q()
        if start_date:
            invoice_filters &= Q(invoice_date__gte=start_date)
        if end_date:
            invoice_filters &= Q(invoice_date__lte=end_date)
        if po_number:
            invoice_filters &= Q(po_number__icontains=po_number)
        if vendor:
            invoice_filters &= Q(invoice_vendor__icontains=vendor)

        # Get filtered invoice reconciliations
        invoices = InvoiceGrnReconciliation.objects.filter(invoice_filters)
        
        # Get all invoice data IDs from filtered invoices
        invoice_data_ids = invoices.values_list('invoice_data_id', flat=True)

        # Get item-level reconciliations for these invoices
        items = InvoiceItemReconciliation.objects.filter(invoice_data_id__in=invoice_data_ids)

        # Calculate invoice-level status based on item-level analysis
        invoice_status_analysis = {}
        for invoice_data_id in invoice_data_ids:
            invoice_items = items.filter(invoice_data_id=invoice_data_id)
            total_items = invoice_items.count()
            perfect_match_items = invoice_items.filter(match_status='perfect_match').count()
            
            # Invoice is considered matched only if ALL items are perfectly matched
            is_invoice_matched = (total_items > 0 and total_items == perfect_match_items)
            invoice_status_analysis[invoice_data_id] = is_invoice_matched

        # Get matched and unmatched invoice lists
        matched_invoice_ids = [inv_id for inv_id, is_matched in invoice_status_analysis.items() if is_matched]
        unmatched_invoice_ids = [inv_id for inv_id, is_matched in invoice_status_analysis.items() if not is_matched]

        # Calculate basic metrics
        total_invoices = invoices.count()
        total_grns = invoices.exclude(grn_number__isnull=True).exclude(grn_number='').count()
        matched_invoices = len(matched_invoice_ids)
        unmatched_invoices = len(unmatched_invoice_ids)

        # Amount calculations based on actual invoice matching status
        if matched_invoice_ids:
            matched_invoices_queryset = invoices.filter(invoice_data_id__in=matched_invoice_ids)
            matched_invoice_amount = matched_invoices_queryset.aggregate(total=Sum('invoice_total'))['total'] or 0
            matched_grn_amount = matched_invoices_queryset.aggregate(total=Sum('grn_total'))['total'] or 0
        else:
            matched_invoice_amount = 0
            matched_grn_amount = 0

        if unmatched_invoice_ids:
            unmatched_invoices_queryset = invoices.filter(invoice_data_id__in=unmatched_invoice_ids)
            unmatched_invoice_amount = unmatched_invoices_queryset.aggregate(total=Sum('invoice_total'))['total'] or 0
            unmatched_grn_amount = unmatched_invoices_queryset.aggregate(total=Sum('grn_total'))['total'] or 0
        else:
            unmatched_invoice_amount = 0
            unmatched_grn_amount = 0

        # Conditional Match & Mismatch, complete match calculations
        conditional_qs = invoices.filter(overall_match_status="conditional_match")
        mismatch_qs = invoices.filter(overall_match_status="mismatch")
        completed_qs = invoices.filter(overall_match_status="complete_match")

        conditional_invoice_total = conditional_qs.aggregate(total=Sum('invoice_total'))['total'] or 0
        conditional_grn_total = conditional_qs.aggregate(total=Sum('grn_total'))['total'] or 0

        mismatch_invoice_total = mismatch_qs.aggregate(total=Sum('invoice_total'))['total'] or 0
        mismatch_grn_total = mismatch_qs.aggregate(total=Sum('grn_total'))['total'] or 0
    
        complete_matched_invoice_total = completed_qs.aggregate(total=Sum('invoice_total'))['total'] or 0
        complete_matched_grn_total = completed_qs.aggregate(total=Sum('grn_total'))['total'] or 0
        
        # Counts
        conditional_count = conditional_qs.count()
        mismatch_count = mismatch_qs.count()
        complete_match_count = completed_qs.count()

        # Total amounts
        total_invoice_amount = invoices.aggregate(total=Sum('invoice_total'))['total'] or 0
        total_grn_amount = invoices.aggregate(total=Sum('grn_total'))['total'] or 0

        if total_invoices > 0:
            matched_invoice_percentage = round((matched_invoices / total_invoices) * 100, 2)
        else:
            matched_invoice_percentage = 0.0

        if total_grns > 0:
            matched_grn_percentage = round((matched_invoices / total_grns) * 100, 2)
        else:
            matched_grn_percentage = 0.0

        return {
            "total_items_reconciled": {
                "invoice": total_invoices,
                "grn": total_grns
            },
            "total_amount_reconciled": {
                "invoice": float(total_invoice_amount),
                "grn": float(total_grn_amount)
            },
            "matched_items": {
                "invoice": matched_invoices,
                "grn": matched_invoices
            },
            "matched_amount": {
                "invoice": float(matched_invoice_amount),
                "grn": float(matched_grn_amount)
            },
            "unmatched_items": {
                "invoice": unmatched_invoices,
                "grn": unmatched_invoices
            },
            "unmatched_amount": {
                "invoice": float(unmatched_invoice_amount),
                "grn": float(unmatched_grn_amount)
            },
            
            "conditional_match_amount": {
                "count": conditional_count,
                "invoice": float(conditional_invoice_total),
                "grn": float(conditional_grn_total)
            },
            "mismatch_amount": {
                "count": mismatch_count,
                "invoice": float(mismatch_invoice_total),
                "grn": float(mismatch_grn_total)
            },
            "complete_match_amount": {
                "count": complete_match_count,
                "invoice": float(complete_matched_invoice_total),
                "grn": float(complete_matched_grn_total)
            },
        }

    def get_detailed_data(self, request):
        """Returns detailed reconciliation list"""
        # Parse filter parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        po_number = request.query_params.get('po_number')
        vendor = request.query_params.get('vendor')

        # Handle month/year conversion
        if month and year:
            start_date = f"{year}-{month.zfill(2)}-01"
            last_day = calendar.monthrange(int(year), int(month))[1]
            end_date = f"{year}-{month.zfill(2)}-{last_day:02d}"

        # Build filters for InvoiceGrnReconciliation
        filters = Q()
        if start_date:
            filters &= Q(invoice_date__gte=start_date)
        if end_date:
            filters &= Q(invoice_date__lte=end_date)
        if po_number:
            filters &= Q(po_number__icontains=po_number)
        if vendor:
            filters &= Q(invoice_vendor__icontains=vendor)

        # Apply filters
        invoice_item_groups = InvoiceGrnReconciliation.objects.filter(filters)
        all_reconciliations = []

        for grn_summary in invoice_item_groups:
            invoice_number = grn_summary.invoice_number
            po_number = grn_summary.po_number
            invoice_items = InvoiceItemReconciliation.objects.filter(invoice_number=invoice_number)
            invoice_data = InvoiceData.objects.filter(invoice_number=invoice_number).first()
            grn_aggregated_data = GrnSummary.objects.filter(grn_number=grn_summary.grn_number).first()

            invoice_line_items = []
            grn_line_items = []
            item_statuses = []

            for idx, item in enumerate(invoice_items, start=1):
                invoice_item_data = InvoiceItemData.objects.filter(
                    invoice_data_id=grn_summary.invoice_data_id, 
                    item_sequence=item.invoice_item_sequence or idx
                ).first()
                invoice_line_items.append({
                    "item_sequence": item.invoice_item_sequence or idx,
                    "item_name": item.invoice_item_description,
                    "unit": item.invoice_item_unit,
                    "hsn": item.invoice_item_hsn,
                    "rate": float(item.invoice_item_unit_price) if item.invoice_item_unit_price is not None else "-",
                    "quantity": float(item.invoice_item_quantity) if item.invoice_item_quantity is not None else "-",
                    "subtotal": float(item.invoice_item_subtotal) if item.invoice_item_subtotal is not None else "-",
                    "sgst": float(item.invoice_item_sgst_amount) if item.invoice_item_sgst_amount is not None else "-",
                    "cgst": float(item.invoice_item_cgst_amount) if item.invoice_item_cgst_amount is not None else "-",
                    "igst": float(item.invoice_item_igst_amount) if item.invoice_item_igst_amount is not None else "-",
                    "cess": float(invoice_item_data.cess_amount) if invoice_item_data and invoice_item_data.cess_amount is not None else "-",
                    "discount": float(invoice_item_data.discount_amount) if invoice_item_data and invoice_item_data.discount_amount is not None else "-",
                    "total": float(item.invoice_item_total_amount) if item.invoice_item_total_amount is not None else "-",
                    "status": item.match_status
                })

                grn_line_items.append({
                    "item_sequence": idx,
                    "item_name": item.grn_item_description,
                    "unit": item.grn_item_unit,
                    "hsn": item.grn_item_hsn,
                    "rate": float(item.grn_item_unit_price) if item.grn_item_unit_price is not None else "-",
                    "quantity": float(item.grn_item_quantity) if item.grn_item_quantity is not None else "-",
                    "subtotal": float(item.grn_item_subtotal) if item.grn_item_subtotal is not None else "-",
                    "sgst": float(item.grn_item_sgst_amount) if item.grn_item_sgst_amount is not None else "-",
                    "cgst": float(item.grn_item_cgst_amount) if item.grn_item_cgst_amount is not None else "-",
                    "igst": float(item.grn_item_igst_amount) if item.grn_item_igst_amount is not None else "-",
                    "total": float(item.grn_item_total_amount) if item.grn_item_total_amount is not None else "-"
                })

                item_statuses.append({
                    "id": item.id,
                    "item_overall_status": item.overall_match_status,
                    "match_status": item.match_status,
                    "match_score": float(item.match_score) if item.match_score is not None else "-",
                    "quantity_variance": float(item.quantity_variance) if item.quantity_variance is not None else "-",
                    "subtotal_variance": float(item.subtotal_variance) if item.subtotal_variance is not None else "-",
                    "total_amount_variance": float(item.total_amount_variance) if item.total_amount_variance is not None else "-",
                    "updated_by": item.updated_by if item.updated_by else None,
                    "updated_at": item.updated_at.timestamp() if item.updated_at else None,
                    "requires_review": item.requires_review,
                    "is_exception": item.is_exception,
                    "comments": item.comments if item.comments else None
                })

            all_reconciliations.append({
                "invoice_data": {
                    "invoice_number": invoice_number,
                    "invoice_data_id": grn_summary.invoice_data_id,
                    "attachment_url": invoice_data.attachment_url if invoice_data and invoice_data.attachment_url else None,
                    "po_number": grn_summary.po_number if grn_summary.po_number else None,
                    "vendor": grn_summary.invoice_vendor if grn_summary.invoice_vendor else None,
                    "invoice_date": grn_summary.invoice_date if grn_summary.invoice_date else None,
                    "invoice_discount": float(invoice_data.invoice_discount) if invoice_data and invoice_data.invoice_discount is not None else "-",
                    "invoice_total": float(grn_summary.invoice_total) if grn_summary.invoice_total is not None else "-",
                    "cgst": float(grn_summary.invoice_cgst) if grn_summary.invoice_cgst is not None else "-",
                    "sgst": float(grn_summary.invoice_sgst) if grn_summary.invoice_sgst is not None else "-",
                    "igst": float(grn_summary.invoice_igst) if grn_summary.invoice_igst is not None else "-",
                    "cess": float(invoice_data.cess_amount) if invoice_data and invoice_data.cess_amount is not None else "-",
                    "transportation": float(invoice_data.transport_charges) if invoice_data and invoice_data.transport_charges is not None else "-",
                    "subtotal": float(grn_summary.invoice_subtotal) if grn_summary.invoice_subtotal is not None else "-",
                    "line_items": invoice_line_items
                },
                "grn_data": {
                    "grn_number": grn_summary.grn_number,
                    "po_number": po_number,
                    "vendor": grn_summary.grn_vendor if grn_summary.grn_vendor else None,
                    "grn_date": grn_summary.grn_date if grn_summary.grn_date else None,
                    "grn_total_discount": float(grn_aggregated_data.total_discount) if grn_aggregated_data and grn_aggregated_data.total_discount is not None else "-",
                    "grn_total": float(grn_summary.grn_total) if grn_summary.grn_total is not None else "-",
                    "cgst": float(grn_summary.grn_cgst) if grn_summary.grn_cgst is not None else "-",
                    "sgst": float(grn_summary.grn_sgst) if grn_summary.grn_sgst is not None else "-",
                    "igst": float(grn_summary.grn_igst) if grn_summary.grn_igst is not None else "-",
                    "subtotal": float(grn_summary.grn_subtotal) if grn_summary.grn_subtotal is not None else "-",
                    "line_items": grn_line_items
                },
                "status": {
                    "overall_match_status": grn_summary.overall_match_status if grn_summary.overall_match_status else "pending",
                    "match_score": float(grn_summary.match_score) if grn_summary.match_score else 0,
                    "vendor_match": grn_summary.vendor_match,
                    "gst_match": grn_summary.gst_match,
                    "date_valid": grn_summary.date_valid,
                    "total_variance": float(grn_summary.total_variance) if grn_summary.total_variance is not None else "-",
                    "requires_review": grn_summary.requires_review if grn_summary.requires_review else False,
                    "is_exception": grn_summary.is_exception if grn_summary.is_exception else False,
                    "approval_status": grn_summary.approval_status,
                    "approved_by": grn_summary.approved_by if grn_summary.approved_by else None,
                    "approved_at": grn_summary.approved_at if grn_summary.approved_at else None,
                    "reconciled_by": grn_summary.reconciled_by if grn_summary.reconciled_by else None,
                    "reconciled_at": grn_summary.reconciled_at if grn_summary.reconciled_at else None,
                    "status": grn_summary.status,
                    "item_level_status": item_statuses
                    
                }
            })

        return all_reconciliations
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
            
            # Validate all required fields in one condition
            if invoice_data_id is None or status is None or not approved_by:
                return JsonResponse({
                    'success': False,
                    'error': 'invoice_data_id, status, and approved_by are required'
                }, status=400)
            
            # Validate types
            if not isinstance(status, bool) or not isinstance(invoice_data_id, int):
                return JsonResponse({
                    'success': False,
                    'error': 'status must be true or false and invoice_data_id must be an integer'
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
                
                # Prepare response with timestamps
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
                        'approved_at': reconciliation.approved_at.timestamp() if reconciliation.approved_at else None,
                        'updated_at': reconciliation.updated_at.timestamp()
                    }
                }
                
                return JsonResponse(response_data, status=200)
                
        except InvoiceGrnReconciliation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'No reconciliation record found for invoice_data_id: {invoice_data_id}'
            }, status=404)
        except ValueError as e:
            logger.warning(f"[ReconciliationApprovalAPI] ValueError: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid data provided: {str(e)}'
            }, status=400)
        except Exception as e:
            logger.error(f"[ReconciliationApprovalAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Internal server error occurred'
            }, status=500)
