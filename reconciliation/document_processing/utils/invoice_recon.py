import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.db.models import Q
from asgiref.sync import sync_to_async

from document_processing.models import (
    InvoiceData, 
    InvoiceItemData, 
    GrnSummary, 
    InvoiceGrnReconciliation,
    ReconciliationBatch
)

logger = logging.getLogger(__name__)


class RuleBasedReconciliationProcessor:
    """
    Rule-based reconciliation processor that matches invoices with GRN summaries
    without using LLM. Uses direct field mapping and threshold-based matching.
    
    Field mappings:
    - po_number -> po_number
    - grn_number -> grn_number  
    - invoice_number -> seller_invoice_number
    - vendor_name -> supplier_name
    - vendor_gst -> pickup_gstin
    - invoice_date -> supplier_invoice_date
    - invoice_value_without_gst -> total_subtotal
    - cgst_amount -> total_cgst_amount
    - sgst_amount -> total_sgst_amount
    - igst_amount -> total_igst_amount
    - invoice_total_post_gst -> total_amount
    """
    
    def __init__(self, tolerance_percentage: Decimal = Decimal('2.00'), date_tolerance_days: int = 30):
        self.tolerance_percentage = tolerance_percentage
        self.date_tolerance_days = date_tolerance_days
        
        self.stats = {
            'total_processed': 0,
            'perfect_matches': 0,
            'partial_matches': 0,
            'amount_mismatches': 0,
            'vendor_mismatches': 0,
            'date_mismatches': 0,
            'no_matches': 0,
            'errors': 0
        }

    async def process_batch_async(self, invoice_ids: List[int] = None, batch_size: int = 100) -> Dict[str, Any]:
        """Process invoices using rule-based reconciliation"""
        try:
            logger.info(f"Starting Rule-Based reconciliation")
            logger.info(f"Settings: tolerance={self.tolerance_percentage}%, date_tolerance={self.date_tolerance_days} days")
            
            # Create reconciliation batch
            batch = await self._create_reconciliation_batch()
            
            # Get invoices to process
            if invoice_ids:
                invoices = await sync_to_async(list)(
                    InvoiceData.objects.filter(id__in=invoice_ids, processing_status='completed')
                )
            else:
                invoices = await sync_to_async(list)(
                    InvoiceData.objects.filter(processing_status='completed')
                )
            
            total_invoices = len(invoices)
            logger.info(f"Processing {total_invoices} invoices with rule-based matching...")
            
            # Update batch total
            batch.total_invoices = total_invoices
            await sync_to_async(batch.save)()
            
            # Process in batches
            results = []
            
            for i in range(0, total_invoices, batch_size):
                batch_invoices = invoices[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}: {len(batch_invoices)} invoices")
                
                # Process batch
                for invoice in batch_invoices:
                    try:
                        result = await self._process_single_invoice(invoice, batch)
                        results.append(result)
                        self.stats['total_processed'] += 1
                        
                        # Update batch progress
                        batch.processed_invoices = self.stats['total_processed']
                        await sync_to_async(batch.save)()
                        
                    except Exception as e:
                        logger.error(f"Error processing invoice {invoice.id}: {str(e)}")
                        self.stats['errors'] += 1
                
                # Log progress
                progress_pct = (self.stats['total_processed'] / total_invoices) * 100
                logger.info(f"Progress: {self.stats['total_processed']}/{total_invoices} ({progress_pct:.1f}%)")
            
            # Complete batch
            await self._complete_reconciliation_batch(batch)
            
            logger.info("Rule-based reconciliation completed!")
            logger.info(f"Final Stats: {self.stats}")
            
            return {
                'success': True,
                'batch_id': batch.batch_id,
                'total_processed': self.stats['total_processed'],
                'stats': self.stats,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Rule-based batch processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }

    async def _process_single_invoice(self, invoice: InvoiceData, batch: ReconciliationBatch) -> Dict[str, Any]:
        """Process single invoice using rule-based matching"""
        try:
            logger.info(f"Processing invoice {invoice.id} - PO: {invoice.po_number}")
            
            # Step 1: Find GRN matches using hierarchy
            grn_matches = await self._find_grn_matches_hierarchical(invoice)
            
            if not grn_matches:
                self.stats['no_matches'] += 1
                return await self._create_no_match_record(invoice)
            
            logger.info(f"Found {len(grn_matches)} GRN matches for invoice {invoice.id}")
            
            # Step 2: Evaluate each match and pick the best one
            best_match = await self._evaluate_grn_matches(invoice, grn_matches)
            
            # Step 3: Create reconciliation record
            reconciliation = await self._create_reconciliation_record(invoice, best_match)
            
            # Step 4: Update statistics
            self._update_statistics(reconciliation.match_status)
            
            return {
                'invoice_id': invoice.id,
                'reconciliation_id': reconciliation.id,
                'match_status': reconciliation.match_status,
                'grn_matched': best_match['grn_summary'].grn_number,
                'match_score': best_match['match_score'],
                'total_variance': float(reconciliation.total_variance or 0)
            }
            
        except Exception as e:
            logger.error(f"Error processing invoice {invoice.id}: {str(e)}")
            raise

    async def _find_grn_matches_hierarchical(self, invoice: InvoiceData) -> List[GrnSummary]:
        """Find GRN matches using hierarchical matching strategy"""
        
        # Strategy 1: Exact PO + GRN + Invoice Number match
        if invoice.po_number and invoice.grn_number and invoice.invoice_number:
            matches = await sync_to_async(list)(
                GrnSummary.objects.filter(
                    po_number=invoice.po_number,
                    grn_number=invoice.grn_number,
                    seller_invoice_number=invoice.invoice_number
                )
            )
            if matches:
                logger.info(f"Found {len(matches)} exact matches (PO+GRN+Invoice)")
                return matches
        
        # Strategy 2: PO + Invoice Number match
        if invoice.po_number and invoice.invoice_number:
            matches = await sync_to_async(list)(
                GrnSummary.objects.filter(
                    po_number=invoice.po_number,
                    seller_invoice_number=invoice.invoice_number
                )
            )
            if matches:
                logger.info(f"Found {len(matches)} matches (PO+Invoice)")
                return matches
        
        # Strategy 3: PO + GRN match
        if invoice.po_number and invoice.grn_number:
            matches = await sync_to_async(list)(
                GrnSummary.objects.filter(
                    po_number=invoice.po_number,
                    grn_number=invoice.grn_number
                )
            )
            if matches:
                logger.info(f"Found {len(matches)} matches (PO+GRN)")
                return matches
        
        # Strategy 4: PO only match
        if invoice.po_number:
            matches = await sync_to_async(list)(
                GrnSummary.objects.filter(po_number=invoice.po_number)
            )
            if matches:
                logger.info(f"Found {len(matches)} matches (PO only)")
                return matches
        
        # Strategy 5: Invoice Number only match
        if invoice.invoice_number:
            matches = await sync_to_async(list)(
                GrnSummary.objects.filter(seller_invoice_number=invoice.invoice_number)
            )
            if matches:
                logger.info(f"Found {len(matches)} matches (Invoice only)")
                return matches
        
        # Strategy 6: Vendor GST match (fallback)
        if invoice.vendor_gst:
            matches = await sync_to_async(list)(
                GrnSummary.objects.filter(pickup_gstin=invoice.vendor_gst)
            )
            if matches:
                logger.info(f"Found {len(matches)} matches (GST only)")
                return matches
        
        logger.warning(f"No GRN matches found for invoice {invoice.id}")
        return []

    async def _evaluate_grn_matches(self, invoice: InvoiceData, grn_matches: List[GrnSummary]) -> Dict[str, Any]:
        """Evaluate GRN matches and return the best match with scoring"""
        
        best_match = None
        best_score = -1
        
        for grn in grn_matches:
            match_evaluation = await self._evaluate_single_match(invoice, grn)
            
            if match_evaluation['match_score'] > best_score:
                best_score = match_evaluation['match_score']
                best_match = match_evaluation
        
        return best_match

    async def _evaluate_single_match(self, invoice: InvoiceData, grn: GrnSummary) -> Dict[str, Any]:
        """Evaluate a single invoice-GRN match and return detailed scoring"""
        
        evaluation = {
            'grn_summary': grn,
            'match_score': 0,
            'match_details': {},
            'variances': {},
            'match_status': 'no_match'
        }
        
        score = 0
        max_score = 100
        
        # 1. PO Number Match (25 points)
        po_match = (invoice.po_number and grn.po_number and 
                   invoice.po_number.strip().upper() == grn.po_number.strip().upper())
        if po_match:
            score += 25
        evaluation['match_details']['po_match'] = po_match
        
        # 2. Invoice Number Match (20 points)
        invoice_match = (invoice.invoice_number and grn.seller_invoice_number and
                        invoice.invoice_number.strip().upper() == grn.seller_invoice_number.strip().upper())
        if invoice_match:
            score += 20
        evaluation['match_details']['invoice_match'] = invoice_match
        
        # 3. GRN Number Match (15 points)
        grn_match = (invoice.grn_number and grn.grn_number and
                    invoice.grn_number.strip().upper() == grn.grn_number.strip().upper())
        if grn_match:
            score += 15
        evaluation['match_details']['grn_match'] = grn_match
        
        # 4. Vendor Match (15 points)
        vendor_match = self._evaluate_vendor_match(invoice, grn)
        if vendor_match:
            score += 15
        evaluation['match_details']['vendor_match'] = vendor_match
        
        # 5. Date Validation (10 points)
        date_valid = self._evaluate_date_validation(invoice, grn)
        if date_valid:
            score += 10
        evaluation['match_details']['date_valid'] = date_valid
        
        # 6. Amount Tolerance (15 points)
        amount_evaluation = self._evaluate_amount_tolerance(invoice, grn)
        score += amount_evaluation['score']
        evaluation['match_details']['amount_tolerance'] = amount_evaluation['within_tolerance']
        evaluation['variances'] = amount_evaluation['variances']
        
        evaluation['match_score'] = score
        
        # Determine match status
        if score >= 85:
            evaluation['match_status'] = 'perfect_match'
        elif score >= 60:
            evaluation['match_status'] = 'partial_match'
        elif not amount_evaluation['within_tolerance']:
            evaluation['match_status'] = 'amount_mismatch'
        elif not vendor_match:
            evaluation['match_status'] = 'vendor_mismatch'
        elif not date_valid:
            evaluation['match_status'] = 'date_mismatch'
        else:
            evaluation['match_status'] = 'partial_match'
        
        return evaluation

    def _evaluate_vendor_match(self, invoice: InvoiceData, grn: GrnSummary) -> bool:
        """Evaluate vendor matching between invoice and GRN"""
        
        # Check vendor name match (invoice.vendor_name vs grn.supplier_name)
        if invoice.vendor_name and grn.supplier_name:
            invoice_vendor = invoice.vendor_name.strip().upper()
            grn_vendor = grn.supplier_name.strip().upper()
            if invoice_vendor == grn_vendor:
                return True
            # Partial match (contains)
            if invoice_vendor in grn_vendor or grn_vendor in invoice_vendor:
                return True
        
        # Check GST match (invoice.vendor_gst vs grn.pickup_gstin)
        if invoice.vendor_gst and grn.pickup_gstin:
            if invoice.vendor_gst.strip().upper() == grn.pickup_gstin.strip().upper():
                return True
        
        return False

    def _evaluate_date_validation(self, invoice: InvoiceData, grn: GrnSummary) -> bool:
        """Evaluate date validation - invoice date should be <= GRN created date + tolerance"""
        
        if not invoice.invoice_date or not grn.grn_created_date:
            return True  # No date validation possible
        
        # Invoice date should be before or close to GRN created date
        date_diff = (grn.grn_created_date - invoice.invoice_date).days
        
        # Allow invoice date to be up to date_tolerance_days after GRN date
        return -self.date_tolerance_days <= date_diff <= self.date_tolerance_days

    def _evaluate_amount_tolerance(self, invoice: InvoiceData, grn: GrnSummary) -> Dict[str, Any]:
        """Evaluate amount tolerance between invoice and GRN totals"""
        
        def safe_decimal(value):
            if value is None:
                return Decimal('0.00')
            return Decimal(str(value))
        
        def calculate_variance(invoice_val, grn_val):
            invoice_amount = safe_decimal(invoice_val)
            grn_amount = safe_decimal(grn_val)
            variance = invoice_amount - grn_amount
            
            if grn_amount != 0:
                variance_pct = abs(variance / grn_amount * 100)
            else:
                variance_pct = Decimal('0.00') if variance == 0 else Decimal('100.00')
            
            return {
                'variance_amount': variance,
                'variance_pct': variance_pct,
                'within_tolerance': variance_pct <= self.tolerance_percentage
            }
        
        # Calculate variances
        subtotal_var = calculate_variance(invoice.invoice_value_without_gst, grn.total_subtotal)
        cgst_var = calculate_variance(invoice.cgst_amount, grn.total_cgst_amount)
        sgst_var = calculate_variance(invoice.sgst_amount, grn.total_sgst_amount)
        igst_var = calculate_variance(invoice.igst_amount, grn.total_igst_amount)
        total_var = calculate_variance(invoice.invoice_total_post_gst, grn.total_amount)
        
        variances = {
            'subtotal_variance': subtotal_var,
            'cgst_variance': cgst_var,
            'sgst_variance': sgst_var,
            'igst_variance': igst_var,
            'total_variance': total_var
        }
        
        # Overall tolerance check (based on total amount)
        within_tolerance = total_var['within_tolerance']
        
        # Score based on tolerance (0-15 points)
        if within_tolerance:
            score = 15
        elif total_var['variance_pct'] <= self.tolerance_percentage * 2:
            score = 10  # Within 2x tolerance
        elif total_var['variance_pct'] <= self.tolerance_percentage * 5:
            score = 5   # Within 5x tolerance
        else:
            score = 0   # Outside tolerance
        
        return {
            'score': score,
            'within_tolerance': within_tolerance,
            'variances': variances
        }

    async def _create_reconciliation_record(self, invoice: InvoiceData, match_evaluation: Dict[str, Any]) -> InvoiceGrnReconciliation:
        """Create reconciliation record from match evaluation"""
        
        grn = match_evaluation['grn_summary']
        match_details = match_evaluation['match_details']
        variances = match_evaluation['variances']
        
        # Determine matching method
        if match_details.get('po_match') and match_details.get('grn_match') and match_details.get('invoice_match'):
            matching_method = 'exact_match'
        elif match_details.get('po_match') and match_details.get('grn_match'):
            matching_method = 'po_grn_match'
        elif match_details.get('po_match'):
            matching_method = 'po_only_match'
        else:
            matching_method = 'fallback_match'
        
        reconciliation_data = {
            'invoice_data_id': invoice.id,
            'po_number': invoice.po_number or '',
            'grn_number': grn.grn_number or '',
            'invoice_number': invoice.invoice_number or '',
            'match_status': match_evaluation['match_status'],
            
            # Vendor validation
            'vendor_match': match_details.get('vendor_match', False),
            'invoice_vendor': invoice.vendor_name or '',
            'grn_vendor': grn.supplier_name or '',
            
            # GST validation
            'gst_match': (invoice.vendor_gst == grn.pickup_gstin) if invoice.vendor_gst and grn.pickup_gstin else False,
            'invoice_gst': invoice.vendor_gst or '',
            'grn_gst': grn.pickup_gstin or '',
            
            # Date validation
            'date_valid': match_details.get('date_valid', False),
            'invoice_date': invoice.invoice_date,
            'grn_date': grn.grn_created_date,
            
            # Financial amounts
            'invoice_subtotal': float(invoice.invoice_value_without_gst or 0),
            'invoice_cgst': float(invoice.cgst_amount or 0),
            'invoice_sgst': float(invoice.sgst_amount or 0),
            'invoice_igst': float(invoice.igst_amount or 0),
            'invoice_total': float(invoice.invoice_total_post_gst or 0),
            
            # GRN amounts
            'grn_subtotal': float(grn.total_subtotal or 0),
            'grn_cgst': float(grn.total_cgst_amount or 0),
            'grn_sgst': float(grn.total_sgst_amount or 0),
            'grn_igst': float(grn.total_igst_amount or 0),
            'grn_total': float(grn.total_amount or 0),
            
            # Variances
            'subtotal_variance': float(variances['subtotal_variance']['variance_amount']),
            'cgst_variance': float(variances['cgst_variance']['variance_amount']),
            'sgst_variance': float(variances['sgst_variance']['variance_amount']),
            'igst_variance': float(variances['igst_variance']['variance_amount']),
            'total_variance': float(variances['total_variance']['variance_amount']),
            
            # Summary info
            'total_grn_line_items': grn.total_items_count,
            'matching_method': matching_method,
            'is_auto_matched': True,
            'tolerance_applied': self.tolerance_percentage,
            'reconciliation_notes': f"Rule-based matching. Score: {match_evaluation['match_score']}/100. Method: {matching_method}.",
            'overall_match_status': 'pending'
        }
        
        reconciliation = await sync_to_async(InvoiceGrnReconciliation.objects.create)(**reconciliation_data)
        
        logger.info(f"Created reconciliation record {reconciliation.id} for invoice {invoice.id} with score {match_evaluation['match_score']}")
        return reconciliation

    async def _create_no_match_record(self, invoice: InvoiceData) -> Dict[str, Any]:
        """Create no-match record"""
        reconciliation_data = {
            'invoice_data_id': invoice.id,
            'po_number': invoice.po_number or '',
            'invoice_number': invoice.invoice_number or '',
            'match_status': 'no_grn_found',
            'total_grn_line_items': 0,
            'is_auto_matched': True,
            'matching_method': 'rule_based_matching',
            'tolerance_applied': self.tolerance_percentage,
            'reconciliation_notes': 'No matching GRN summary records found using rule-based matching',
            'overall_match_status': 'pending'
        }
        
        reconciliation = await sync_to_async(InvoiceGrnReconciliation.objects.create)(**reconciliation_data)
        
        return {
            'invoice_id': invoice.id,
            'reconciliation_id': reconciliation.id,
            'match_status': 'no_grn_found',
            'grn_matched': None,
            'match_score': 0
        }

    def _update_statistics(self, match_status: str):
        """Update processing statistics"""
        if match_status == 'perfect_match':
            self.stats['perfect_matches'] += 1
        elif match_status == 'partial_match':
            self.stats['partial_matches'] += 1
        elif match_status == 'amount_mismatch':
            self.stats['amount_mismatches'] += 1
        elif match_status == 'vendor_mismatch':
            self.stats['vendor_mismatches'] += 1
        elif match_status == 'date_mismatch':
            self.stats['date_mismatches'] += 1
        elif match_status == 'no_grn_found':
            self.stats['no_matches'] += 1

    async def _create_reconciliation_batch(self) -> ReconciliationBatch:
        """Create a new reconciliation batch"""
        import uuid
        
        batch_id = f"RULE_BASED_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        batch = await sync_to_async(ReconciliationBatch.objects.create)(
            batch_id=batch_id,
            batch_name=f"Rule-Based Reconciliation - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            tolerance_percentage=self.tolerance_percentage,
            date_tolerance_days=self.date_tolerance_days,
            started_by="system"
        )
        
        logger.info(f"Created reconciliation batch: {batch_id}")
        return batch

    async def _complete_reconciliation_batch(self, batch: ReconciliationBatch):
        """Complete reconciliation batch with final statistics"""
        batch.processed_invoices = self.stats['total_processed']
        batch.perfect_matches = self.stats['perfect_matches']
        batch.partial_matches = self.stats['partial_matches']
        batch.exceptions = self.stats['amount_mismatches'] + self.stats['vendor_mismatches'] + self.stats['date_mismatches']
        batch.no_matches = self.stats['no_matches']
        batch.status = 'completed'
        batch.completed_at = datetime.now()
        
        await sync_to_async(batch.save)()
        logger.info(f"Completed reconciliation batch: {batch.batch_id}")


# Main function to run rule-based reconciliation
async def run_rule_based_reconciliation(
    invoice_ids: List[int] = None, 
    tolerance_percentage: float = 2.0,
    date_tolerance_days: int = 30,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Main function to run rule-based reconciliation using GrnSummary table
    
    Args:
        invoice_ids: Optional list of invoice IDs
        tolerance_percentage: Amount tolerance percentage (default 2.0)
        date_tolerance_days: Date tolerance in days (default 30)
        batch_size: Batch size for processing (default 100)
    """
    processor = RuleBasedReconciliationProcessor(
        tolerance_percentage=Decimal(str(tolerance_percentage)),
        date_tolerance_days=date_tolerance_days
    )
    
    return await processor.process_batch_async(
        invoice_ids=invoice_ids,
        batch_size=batch_size
    )
