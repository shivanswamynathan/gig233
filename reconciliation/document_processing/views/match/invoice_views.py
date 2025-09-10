from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from document_processing.models import InvoiceData, ItemWiseGrn, GrnSummary, InvoiceItemData
from document_processing.utils.services.pagination import PaginationHelper, create_server_error_response
from django.db.models import Q, Count
import pandas as pd
import numpy as np
import os
import json
import logging

logger = logging.getLogger(__name__)


def format_success_response(data, message="Success"):
    return JsonResponse({
        "success": True,
        "message": message,
        "data": data
    }, status=200)


def format_error_response(message="Internal Server Error", status=500):
    return JsonResponse({
        "success": False,
        "message": message,
        "data": []
    }, status=status)


@method_decorator(csrf_exempt, name='dispatch')
class ProcessedInvoiceListAPI(View):
    """Returns all successfully processed invoices."""

    def get(self, request):
        try:
            invoices = InvoiceData.objects.filter(
                processing_status='completed',
                duplicates=False
            ).values(
                'id',
                'vendor_name',
                'updated_at',
                'po_number',
                'grn_number',
                'invoice_number',
                'invoice_date',
                'attachment_url'
            )

            formatted = [
                {
                    **inv,
                    'updated_at': inv['updated_at'].strftime("%d/%m/%y") if inv['updated_at'] else ""
                }
                for inv in invoices
            ]

            logger.info(f"[ProcessedInvoiceListAPI] Returned {len(formatted)} records.")
            return format_success_response(formatted, "Processed invoices fetched successfully.")

        except Exception as e:
            logger.error(f"[ProcessedInvoiceListAPI] Error: {str(e)}", exc_info=True)
            return format_error_response()


class MissingInvoiceListAPI(APIView):
    """
    Django REST Framework API to return ItemWiseGrn records with missing invoices
    
    GET /api/missing-invoices/?batch_id=optional
    
    Query Parameters:
    - batch_id: Optional batch ID to filter specific upload batch
    
    Returns all ItemWiseGrn records where missing_invoice = True
    """
    
    def get(self, request):
        """GET: Retrieve ItemWiseGrn records with missing invoices"""
        try:
            # Get query parameters
            batch_id = request.query_params.get('batch_id', None)
            
            # Build queryset - filter records where missing_invoice = True
            queryset = ItemWiseGrn.objects.filter(missing_invoice=True)
            
            # Apply batch filter if provided
            if batch_id:
                queryset = queryset.filter(upload_batch_id=batch_id)
                logger.info(f"[MissingInvoiceListAPI] Filtering by batch_id: {batch_id}")
            
            # Check if any records found
            total_count = queryset.count()
            if total_count == 0:
                return Response({
                    'success': True,
                    'message': 'No records found with missing invoices',
                    'batch_id': batch_id,
                    'data': [],
                    'total_count': 0
                }, status=status.HTTP_200_OK)
            
            # Format the data
            formatted_data = []
            for grn_record in queryset:
                formatted_data.append({
                    'id': grn_record.id,
                    'grn_number': grn_record.grn_no,
                    'po_number': grn_record.po_no,
                    'vendor_name': grn_record.supplier,
                    'quantity': float(grn_record.received_qty) if grn_record.received_qty else 0,
                    'total_amount': float(grn_record.total) if grn_record.total else 0,
                    'missing_invoice': grn_record.missing_invoice,
                    'created_at': grn_record.created_at.strftime("%d/%m/%Y %H:%M") if grn_record.created_at else "",
                    'updated_at': grn_record.updated_at.strftime("%d/%m/%Y %H:%M") if grn_record.updated_at else ""
                })
            
            # Log success
            logger.info(f"[MissingInvoiceListAPI] Returned {len(formatted_data)} missing invoice records "
                       f"(Total: {total_count})")
            
            # Return response
            return JsonResponse({
                'success': True,
                'message': f'Retrieved {len(formatted_data)} records with missing invoices',
                'batch_id': batch_id,
                'data': formatted_data,
                'total_missing_invoices': total_count
                
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"[MissingInvoiceListAPI] Error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': str(e),
                'data': []
            }, status=status.HTTP_400_BAD_REQUEST)
        
class OCRIssuesListAPI(APIView):
    """
    API to return OCR issue invoices (no vendor fetch here).
    """
    def get(self, request):
        try:
            invoices = InvoiceData.objects.filter(
                duplicates=False
            ).exclude(
                failure_reason__isnull=True
            ).values(
                'id',
                'vendor_name',
                'updated_at',
                'po_number',
                'grn_number',
                'invoice_number',
                'invoice_date',
                'attachment_url',
                'invoice_value_without_gst',
                'cgst_amount',
                'sgst_amount',
                'igst_amount',
                'total_gst_amount',
                'invoice_total_post_gst',
                'failure_reason',
            )

            formatted = []
            for inv in invoices:
                formatted.append({
                    "invoice_id": inv['id'],
                    "vendor_name": inv['vendor_name'],
                    "updated_at": inv['updated_at'].strftime("%d/%m/%y") if inv['updated_at'] else "",
                    "po_number": inv['po_number'],
                    "grn_number": inv['grn_number'],
                    "invoice_number": inv['invoice_number'],
                    "invoice_date": inv['invoice_date'].strftime("%d/%m/%y") if inv['invoice_date'] else "",
                    "attachment_name": inv['attachment_url'] or "",
                    "confidence": "",
                    "invoice_value_without_gst": float(inv['invoice_value_without_gst']) if inv['invoice_value_without_gst'] is not None else "-",
                    "cgst_amount": float(inv['cgst_amount']) if inv['cgst_amount'] is not None else "-",
                    "sgst_amount": float(inv['sgst_amount']) if inv['sgst_amount'] is not None else "-",
                    "igst_amount": float(inv['igst_amount']) if inv['igst_amount'] is not None else "-",
                    "total_gst_amount": float(inv['total_gst_amount']) if inv['total_gst_amount'] is not None else "-",
                    "invoice_total_post_gst": float(inv['invoice_total_post_gst']) if inv['invoice_total_post_gst'] is not None else "-",
                    "failure_reason": inv['failure_reason'] or "Unknown"
                })

            logger.info(f"[OCRIssuesListAPI] Returned {len(formatted)} records.")
            return JsonResponse(
                {
                    "success": True,
                    "data": formatted
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"[OCRIssuesListAPI] Error: {str(e)}", exc_info=True)
            return Response(
                {
                  "success": False,
                  "message": "Internal Server Error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class FetchDataAPI(APIView):
    """
    API to fetch GRN summary (invoice-level details) + all matching Itemwise GRN items for a given invoice (OCR issue).
    Example: /api/v1/document-processing/fetch-data/?invoice_id=1030
    """

    def get(self, request):
        invoice_id = request.GET.get("invoice_id")
        if not invoice_id:
            return Response(
                {
                    "success": False,
                    "message": "Missing 'invoice_id' parameter",
                    "data": []
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # -------------------
            # Fetch invoice (OCR issue entry)
            # -------------------
            invoice = InvoiceData.objects.filter(id=invoice_id).first()
            if not invoice:
                logger.warning(f"Invoice {invoice_id} not found")
                return Response(
                    {
                        "success": False,
                        "message": f"Invoice {invoice_id} not found",
                        "data": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            logger.info(f"OCR Invoice {invoice.id} fetched successfully")

            # -------------------
            # Fetch GRN summary (real invoice-level details)
            # -------------------
            grn_summary = GrnSummary.objects.filter(
                po_number=invoice.po_number,
                grn_number=invoice.grn_number
            ).first()

            if not grn_summary:
                logger.warning(f"No GRN Summary found (po={invoice.po_number}, grn={invoice.grn_number})")
                return Response(
                    {
                        "success": False,
                        "message": "No matching GRN summary found",
                        "data": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            logger.info(f"GRN Summary {grn_summary.id} found for Invoice {invoice.id}")

            # -------------------
            # Fetch ALL itemwise GRN (items list)
            # -------------------
            attachment_url = invoice.attachment_url
            itemwise_grn_qs = ItemWiseGrn.objects.filter(
                po_no=grn_summary.po_number,
                grn_no=grn_summary.grn_number
            ).filter(
                Q(attachment_1=attachment_url) | Q(attachment_2=attachment_url) | Q(attachment_3=attachment_url)
            )

            items_list = []
            for item in itemwise_grn_qs:
                items_list.append({
                    "id": item.id,
                    "item_name": item.item_name or None,
                    "hsn_code": item.hsn_no or None,
                    "po_no": item.po_no or None,
                    "grn_no": item.grn_no or None,
                    "invoice_number": item.seller_invoice_no or None,
                    "invoice_date": item.supplier_invoice_date if item.supplier_invoice_date else None,
                    "unit_price": str(item.price) if item.price else None,
                    "quantity": str(item.received_qty) if item.received_qty else None,
                    "discount": str(item.discount) if item.discount else None,
                    "vendor_name": item.supplier or None,
                    "unit_of_measurement": item.unit or None,
                    "subtotal": str(item.subtotal) if item.subtotal else None,
                    "sgst_amount": str(item.sgst_tax_amount) if item.sgst_tax_amount else None,
                    "cgst_amount": str(item.cgst_tax_amount) if item.cgst_tax_amount else None,
                    "igst_amount": str(item.igst_tax_amount) if item.igst_tax_amount else None,
                    "total": str(item.total) if item.total else None,
                })

            # -------------------
            # Prepare response
            # -------------------
            response_data = {
                "invoice":{
                    "invoice_id": invoice.id,   # OCR invoice reference only
                    "vendor": grn_summary.supplier_name or None,
                    "invoice_number": grn_summary.seller_invoice_number,
                    "po_no": grn_summary.po_number,
                    "grn_no": grn_summary.grn_number,
                    "invoice_date": grn_summary.supplier_invoice_date if grn_summary.supplier_invoice_date else None,
                    "total_amount": str(grn_summary.total_amount) if grn_summary.total_amount else None,
                    "subtotal": str(grn_summary.total_subtotal) if grn_summary.total_subtotal else None,
                    "cgst_amount": str(grn_summary.total_cgst_amount) if grn_summary.total_cgst_amount else None,
                    "sgst_amount": str(grn_summary.total_sgst_amount) if grn_summary.total_sgst_amount else None,
                    "igst_amount": str(grn_summary.total_igst_amount) if grn_summary.total_igst_amount else None,
                },    
                "items": items_list
            }

            logger.info(f"Response ready for Invoice {invoice.id} with {len(items_list)} items")
            return Response(
                {
                    "success": True,
                    "message": "Data fetched successfully",
                    "data": response_data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"Error while fetching data for invoice_id={invoice_id}: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": str(e),
                    "data": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @transaction.atomic
    def post(self, request):
        try:
            # -----------------
            # Parse body (must be JSON with invoice + items)
            # -----------------
            if request.content_type != "application/json":
                return Response(
                    {
                        "success": False,
                        "message": "Content-Type must be application/json",
                        "data": []
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                data = json.loads(request.body.decode("utf-8"))
            except Exception:
                return Response(
                    {
                        "success": False,
                        "message": "Invalid JSON body",
                        "data": []
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            invoice_data = data.get("invoice")
            items_data = data.get("items")

            if not invoice_data or not items_data:
                return Response(
                    {
                        "success": False,
                        "message": "Both 'invoice' and 'items' are required",
                        "data": []
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            invoice_id = invoice_data.get("invoice_id")
            if not invoice_id:
                return Response(
                    {
                        "success": False,
                        "message": "invoice_id is required inside 'invoice'",
                        "data": []
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # -----------------
            # Fetch Invoice
            # -----------------
            try:
                invoice = InvoiceData.objects.get(id=invoice_id)
            except InvoiceData.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "message": "Invoice not found",
                        "data": []
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            logger.info(f"[FetchDataAPI][POST] Updating InvoiceData for id={invoice_id}")


            # -----------------
            # Update InvoiceData fields
            # -----------------
            invoice.vendor_name = invoice_data.get("vendor") or invoice.vendor_name
            invoice.po_number = invoice_data.get("po_no") or invoice.po_number
            invoice.grn_number = invoice_data.get("grn_no") or invoice.grn_number
            invoice.invoice_number = invoice_data.get("invoice_number") or invoice.invoice_number
            invoice.invoice_date = invoice_data.get("invoice_date") or invoice.invoice_date
            invoice.invoice_total_post_gst = invoice_data.get("total_amount") or None
            invoice.sgst_amount = invoice_data.get("sgst_amount") or None
            invoice.cgst_amount = invoice_data.get("cgst_amount") or None
            invoice.igst_amount = invoice_data.get("igst_amount") or None
            invoice.invoice_value_without_gst = invoice_data.get("subtotal") or None
            invoice.total_gst_amount = invoice_data.get("total_gst_amount") or None
            invoice.failure_reason = None
            invoice.processing_status = "completed"
            invoice.save()

            # -----------------
            InvoiceItemData.objects.filter(invoice_data_id=invoice.id).delete()
            logger.info(f"[FetchDataAPI][POST] Deleted old items for invoice {invoice.id}")

        # -----------------
            for item in items_data:
                item.pop("id", None)  # avoid conflicts

                obj = InvoiceItemData.objects.create(
                    invoice_data_id=invoice.id,
                    item_description=item.get("item_name"),
                    po_number=item.get("po_no"),
                    hsn_code=item.get("hsn_code"),
                    invoice_number=item.get("invoice_number"),
                    vendor_name=item.get("vendor_name"),
                    unit_of_measurement=item.get("unit_of_measurement"),
                    quantity=item.get("quantity") or None,
                    unit_price=item.get("unit_price") or None,
                    invoice_value_item_wise=item.get("subtotal") or None,
                    sgst_amount=item.get("sgst_amount") or None,
                    cgst_amount=item.get("cgst_amount") or None,
                    igst_amount=item.get("igst_amount") or None,
                    item_total_amount=item.get("total") or None,
                )
                logger.info(f"[FetchDataAPI][POST] Inserted item {obj.item_description} for invoice {invoice.id}")

            return Response(
                {"success": True, "message": "Invoice and items updated successfully"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"[FetchDataAPI][POST] Error: {e}", exc_info=True)
            return Response(
                {"success": False, "message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
@method_decorator(csrf_exempt, name='dispatch')        
class BoeExtractionAPI(APIView):
    def post(self, request):
        """
        Accepts BOE CSV/Excel file upload and returns its contents as JSON.
        """
        try:
            logger.info("Starting BOE file upload process...")

            uploaded_file = request.FILES.get("boe_file")
            if not uploaded_file:
                logger.error("No file provided in request.")
                return Response(
                    {
                        "success": False,
                        "message": "No file uploaded. Please upload a CSV or Excel file.",
                        "data": []
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            file_name = uploaded_file.name.lower()
            logger.info(f"Received file: {file_name}")

            # Detect file format
            if file_name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            elif file_name.endswith((".xls", ".xlsx")):
                df = pd.read_excel(uploaded_file)
            else:
                logger.error("Unsupported file format.")
                return Response(
                    {
                        "success": False,
                        "message": "Unsupported file format. Only CSV and Excel are supported.",
                        "data": []
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"File successfully read: {df.shape[0]} rows, {df.shape[1]} columns.")

            # Remove only columns with no name (NaN, empty string, or starting with "Unnamed")
            df = df.loc[:, df.columns.notna()]                
            df = df.loc[:, df.columns != ""]                  
            df = df.loc[:, ~df.columns.str.startswith("Unnamed")]  

            # Replace NaN/NaT/inf with None for valid JSON
            df = df.replace([np.nan, np.inf, -np.inf], None)

            # Convert DataFrame to JSON records
            data_json = df.to_dict(orient="records")
            logger.info("Converted BOE data to JSON successfully.")

            return Response(
                {
                    "success": True,
                    "message": "File processed successfully",
                    "data": data_json
                },
                status=status.HTTP_200_OK
            )

        except pd.errors.EmptyDataError:
            logger.warning("Uploaded BOE file is empty.")
            return Response(
                {
                    "success": False,
                    "message": "BOE file is empty",
                    "data": []
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception(f"Unexpected error while processing BOE file: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "Internal server error",
                    "data": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DuplicateInvoiceAPI(APIView):
    """
    API endpoint to mark invoice as duplicate.
    
    PUT /api/duplicate-invoice/
    
    Request Body:
    {
        "attachment_url": "string"
    }
    """    
    def put(self, request):
        try:
            attachment_url = request.data.get('attachment_url')
            
            # Find matching invoice
            invoice = InvoiceData.objects.filter(
                attachment_url=attachment_url
            ).first()
            
            if not invoice:
                return Response({
                    'success': False,
                    'message': 'Invoice not found',
                    'data': []
                }, status=status.HTTP_404_NOT_FOUND)
            
            invoice.duplicates = False
            invoice.save()
            
            return Response({
                'success': True,
                'message': 'accepted duplicate successfully',
                'data': {'invoice_id': invoice.id}
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"[DuplicateInvoiceAPI] Error: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'message': str(e),
                'data': []
            }, status=status.HTTP_400_BAD_REQUEST)

class DuplicateInvoiceFlagAPI(APIView):
    """
    API endpoint to automatically flag duplicate invoices in the entire database.
    
    POST /api/duplicate-invoice-flag/
    
    No request body required.
    
    Scans the entire InvoiceData table and marks invoices as duplicates (duplicates=True) 
    when they have matching:
    - invoice_number  
    - po_number
    - grn_number
    
    If 2 or more invoices have the same combination of these fields, 
    ALL of them will be marked as duplicates.
    """
    
    def post(self, request):
        try:
            logger.info("[DuplicateInvoiceFlagAPI] Starting duplicate invoice detection process...")
            
            # Get all invoices that are not already marked as duplicates
            all_invoices = InvoiceData.objects.filter(duplicates=False)
            
            if not all_invoices.exists():
                return Response({
                    'success': True,
                    'message': 'No invoices found to process',
                    'data': {
                        'total_processed': 0,
                        'duplicates_found': 0,
                        'invoices_marked': 0
                    }
                }, status=status.HTTP_200_OK)
            
            total_invoices = all_invoices.count()
            logger.info(f"[DuplicateInvoiceFlagAPI] Processing {total_invoices} invoices...")
            
            # Group invoices by the duplicate criteria fields
            duplicate_groups = {}
            
            for invoice in all_invoices:
                # Create a key based on invoice_number, po_number, grn_number
                # Use empty string for None values and convert to lowercase for case-insensitive comparison
                key = (
                    (invoice.invoice_number or '').lower().strip(), 
                    (invoice.po_number or '').lower().strip(),
                    (invoice.grn_number or '').lower().strip()
                )
                
                # Skip invoices with empty key fields (all None or empty)
                if not any(key):
                    continue
                    
                if key not in duplicate_groups:
                    duplicate_groups[key] = []
                duplicate_groups[key].append(invoice.id)
            
            # Find groups with more than 1 invoice (duplicates)
            duplicate_invoice_ids = []
            duplicate_group_count = 0
            
            for key, invoice_ids in duplicate_groups.items():
                if len(invoice_ids) > 1:
                    duplicate_group_count += 1
                    duplicate_invoice_ids.extend(invoice_ids)
                    logger.info(f"[DuplicateInvoiceFlagAPI] Found duplicate group: {key} with {len(invoice_ids)} invoices: {invoice_ids}")
            
            if not duplicate_invoice_ids:
                return Response({
                    'success': True,
                    'message': 'No duplicate invoices found',
                    'data': {
                        'total_processed': total_invoices,
                        'duplicates_found': 0,
                        'invoices_marked': 0,
                        'duplicate_groups': 0
                    }
                }, status=status.HTTP_200_OK)
            
            # Mark all duplicate invoices
            updated_count = InvoiceData.objects.filter(
                id__in=duplicate_invoice_ids
            ).update(duplicates=True)
            
            logger.info(f"[DuplicateInvoiceFlagAPI] Successfully marked {updated_count} invoices as duplicates in {duplicate_group_count} groups")
            
            return Response({
                'success': True,
                'message': f'Successfully processed {total_invoices} invoices and marked {updated_count} as duplicates',
                'data': {
                    'total_processed': total_invoices,
                    'duplicates_found': len(duplicate_invoice_ids),
                    'invoices_marked': updated_count,
                    'duplicate_groups': duplicate_group_count,
                    'duplicate_invoice_ids': duplicate_invoice_ids
                }
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"[DuplicateInvoiceFlagAPI] Error during duplicate detection: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'message': f'Internal server error: {str(e)}',
                'data': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class DuplicateIssuesAPI(APIView):
    """
    API to fetch invoices flagged as duplicates along with their items.
    Endpoint: /api/v1/document-processing/duplicate-issues/
    """

    def get(self, request):
        try:
             # Step 1: Find duplicate groups (vendor + PO + GRN with count > 1)
            duplicate_groups = (
                InvoiceData.objects
                .values("vendor_name", "po_number", "grn_number", "invoice_number")
                .annotate(duplicate_count=Count("id"))
                .filter(duplicate_count__gt=1)
            )

            # Step 2: Get all invoices that belong to those groups
            invoices = InvoiceData.objects.filter(
                duplicates=True,
                vendor_name__in=[g["vendor_name"] for g in duplicate_groups],
                po_number__in=[g["po_number"] for g in duplicate_groups],
                grn_number__in=[g["grn_number"] for g in duplicate_groups],
                invoice_number__in=[g["invoice_number"] for g in duplicate_groups],
            )

            result = []
            for inv in invoices:
                items = InvoiceItemData.objects.filter(
                    invoice_data_id=inv.id
                ).values(
                    'id',
                    'item_description',
                    'po_number',
                    'hsn_code',
                    'unit_of_measurement',
                    'quantity',
                    'unit_price',
                    'invoice_value_item_wise',
                    'sgst_amount',
                    'cgst_amount',
                    'igst_amount',
                    'item_total_amount',
                    
                )

                result.append({
                    "id": inv.id,
                    "vendor_name": inv.vendor_name,
                    "updated_at": inv.updated_at,
                    "po_number": inv.po_number,
                    "grn_number": inv.grn_number,
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date,
                    "attachment_url": inv.attachment_url,
                    "subtotal": inv.invoice_value_without_gst,
                    "cgst_amount": inv.cgst_amount,
                    "sgst_amount": inv.sgst_amount,
                    "igst_amount": inv.igst_amount,
                    "total_gst_amount": inv.total_gst_amount,
                    "total_amount": inv.invoice_total_post_gst,
                    "items": list(items)  
                })

            return Response(
                {
                    "success": True,
                    "count": len(result),
                    "data": result
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": f"Error fetching duplicate issues: {str(e)}",
                    "data": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
