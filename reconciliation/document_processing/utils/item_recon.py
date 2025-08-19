import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from django.db import transaction
from django.db.models import Q
from asgiref.sync import sync_to_async
from difflib import SequenceMatcher
import re
import uuid
from datetime import datetime

from document_processing.models import (
    InvoiceData, 
    InvoiceItemData, 
    ItemWiseGrn,
    InvoiceItemReconciliation,
    GrnSummary
)

logger = logging.getLogger(__name__)


class ItemWiseReconciliationProcessor:
    """
    Item-wise reconciliation processor that matches InvoiceItemData with ItemWiseGrn
    
    Field mappings for matching:
    InvoiceItemData -> ItemWiseGrn
    - po_number -> po_no
    - invoice_number -> seller_invoice_no
    - vendor_name -> supplier
    - hsn_code -> hsn_no
    - item_description -> item_name
    - quantity -> received_qty
    - unit_price -> price
    - item_total_amount -> total
    """
    
    def __init__(self, tolerance_percentage: Decimal = Decimal('2.00')):
        self.tolerance_percentage = tolerance_percentage
        
        self.stats = {
            'total_items_processed': 0,
            'perfect_matches': 0,
            'partial_matches': 0,
            'quantity_mismatches': 0,
            'price_mismatches': 0,
            'hsn_mismatches': 0,
            'description_mismatches': 0,
            'no_matches': 0,
            'errors': 0
        }

    async def process_items_for_invoices(self, invoice_ids: List[int] = None) -> Dict[str, Any]:
        """Process item-wise reconciliation for given invoices"""
        try:
            logger.info("Starting Item-wise Reconciliation")
            
            # Get invoice items to process
            if invoice_ids:
                invoice_items = await sync_to_async(list)(
                    InvoiceItemData.objects.filter(
                        invoice_data_id__in=invoice_ids
                    ).select_related().order_by('invoice_data_id', 'item_sequence')
                )
            else:
                invoice_items = await sync_to_async(list)(
                    InvoiceItemData.objects.all().select_related().order_by('invoice_data_id', 'item_sequence')
                )
            
            total_items = len(invoice_items)
            logger.info(f"Processing {total_items} invoice items for reconciliation")
            
            results = []
            
            for item in invoice_items:
                try:
                    result = await self._process_single_item(item)
                    results.append(result)
                    self.stats['total_items_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing item {item.id}: {str(e)}")
                    self.stats['errors'] += 1
            
            logger.info("Item-wise reconciliation completed!")
            logger.info(f"Item Stats: {self.stats}")
            
            return {
                'success': True,
                'total_items_processed': self.stats['total_items_processed'],
                'stats': self.stats,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Item-wise reconciliation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }

    async def _process_single_item(self, invoice_item: InvoiceItemData) -> Dict[str, Any]:
        """Process single invoice item reconciliation"""
        try:
            logger.info(f"Processing item {invoice_item.id} - {invoice_item.item_description[:50]}...")
            
            # Step 1: Find matching GRN items using hierarchical matching
            grn_matches = await self._find_grn_item_matches(invoice_item)
            
            if not grn_matches:
                self.stats['no_matches'] += 1
                return await self._create_no_match_item_record(invoice_item)
            
            logger.info(f"Found {len(grn_matches)} GRN item matches for invoice item {invoice_item.id}")
            
            # Step 2: Evaluate matches and pick the best one
            best_match = await self._evaluate_grn_item_matches(invoice_item, grn_matches)
            
            # Step 3: Create item reconciliation record
            reconciliation = await self._create_item_reconciliation_record(invoice_item, best_match)
            
            # Step 4: Update statistics
            self._update_item_statistics(reconciliation.match_status)
            
            return {
                'invoice_item_id': invoice_item.id,
                'reconciliation_id': reconciliation.id,
                'match_status': reconciliation.match_status,
                'grn_item_matched': best_match['grn_item'].id if best_match.get('grn_item') else None,
                'match_score': best_match['match_score'],
                'amount_variance': float(reconciliation.total_amount_variance or 0)  # FIXED: Use correct field name
            }
            
        except Exception as e:
            logger.error(f"Error processing invoice item {invoice_item.id}: {str(e)}")
            raise

    async def _find_grn_item_matches(self, invoice_item: InvoiceItemData) -> List[ItemWiseGrn]:
        """Find GRN item matches using hierarchical matching strategy"""
        
        # Base filters - must have PO number
        base_filters = Q(po_no=invoice_item.po_number) if invoice_item.po_number else Q()
        
        if not invoice_item.po_number:
            logger.warning(f"Invoice item {invoice_item.id} has no PO number")
            return []
        
        # Strategy 1: Exact match (PO + Invoice + HSN + Similar Description)
        if invoice_item.invoice_number and invoice_item.hsn_code:
            matches = await sync_to_async(list)(
                ItemWiseGrn.objects.filter(
                    base_filters &
                    Q(seller_invoice_no=invoice_item.invoice_number) &
                    Q(hsn_no=invoice_item.hsn_code)
                )
            )
            if matches:
                # Filter by description similarity
                similar_matches = []
                for grn_item in matches:
                    similarity = self._calculate_description_similarity(
                        invoice_item.item_description, 
                        grn_item.item_name
                    )
                    if similarity >= 0.6:  # 60% similarity threshold
                        similar_matches.append(grn_item)
                
                if similar_matches:
                    logger.info(f"Found {len(similar_matches)} exact matches (PO+Invoice+HSN+Description)")
                    return similar_matches
        
        # Strategy 2: PO + HSN Code match
        if invoice_item.hsn_code:
            matches = await sync_to_async(list)(
                ItemWiseGrn.objects.filter(
                    base_filters &
                    Q(hsn_no=invoice_item.hsn_code)
                )
            )
            if matches:
                logger.info(f"Found {len(matches)} matches (PO+HSN)")
                return matches
        
        # Strategy 3: PO + Invoice Number match
        if invoice_item.invoice_number:
            matches = await sync_to_async(list)(
                ItemWiseGrn.objects.filter(
                    base_filters &
                    Q(seller_invoice_no=invoice_item.invoice_number)
                )
            )
            if matches:
                logger.info(f"Found {len(matches)} matches (PO+Invoice)")
                return matches
        
        # Strategy 4: PO + Description similarity
        if invoice_item.item_description:
            all_grn_items = await sync_to_async(list)(
                ItemWiseGrn.objects.filter(base_filters)
            )
            
            similar_items = []
            for grn_item in all_grn_items:
                similarity = self._calculate_description_similarity(
                    invoice_item.item_description, 
                    grn_item.item_name
                )
                if similarity >= 0.7:  # 70% similarity for PO-only match
                    similar_items.append(grn_item)
            
            if similar_items:
                logger.info(f"Found {len(similar_items)} matches (PO+Description similarity)")
                return similar_items
        
        # Strategy 5: PO only (sequential matching by item sequence)
        matches = await sync_to_async(list)(
            ItemWiseGrn.objects.filter(base_filters).order_by('s_no')
        )
        
        if matches:
            logger.info(f"Found {len(matches)} matches (PO only)")
            return matches
        
        logger.warning(f"No GRN item matches found for invoice item {invoice_item.id}")
        return []

    def _calculate_description_similarity(self, desc1: str, desc2: str) -> float:
        """Calculate similarity between two item descriptions"""
        if not desc1 or not desc2:
            return 0.0
        
        # Clean and normalize descriptions
        def clean_description(desc):
            if not desc:
                return ""
            # Convert to lowercase, remove extra spaces, special characters
            cleaned = re.sub(r'[^\w\s]', ' ', desc.lower())
            cleaned = ' '.join(cleaned.split())
            return cleaned
        
        clean_desc1 = clean_description(desc1)
        clean_desc2 = clean_description(desc2)
        
        # Use SequenceMatcher for similarity
        similarity = SequenceMatcher(None, clean_desc1, clean_desc2).ratio()
        
        return similarity
    
    def _check_tax_rate_match(self, invoice_item: InvoiceItemData, grn_item: 'ItemWiseGrn') -> bool:
        """Check if tax rates match between invoice and GRN items"""
        tolerance = 0.1  # 0.1% tolerance for tax rates
        
        try:
            # Check CGST
            if invoice_item.cgst_rate and grn_item.cgst_tax:
                if abs(float(invoice_item.cgst_rate) - float(grn_item.cgst_tax)) > tolerance:
                    return False
            
            # Check SGST
            if invoice_item.sgst_rate and grn_item.sgst_tax:
                if abs(float(invoice_item.sgst_rate) - float(grn_item.sgst_tax)) > tolerance:
                    return False
            
            # Check IGST
            if invoice_item.igst_rate and grn_item.igst_tax:
                if abs(float(invoice_item.igst_rate) - float(grn_item.igst_tax)) > tolerance:
                    return False
            
            return True
            
        except (ValueError, TypeError):
            # If any tax rate conversion fails, assume no match
            return False

    async def _evaluate_grn_item_matches(self, invoice_item: InvoiceItemData, grn_matches: List[ItemWiseGrn]) -> Dict[str, Any]:
        """Evaluate GRN item matches and return the best match with scoring"""
        
        best_match = None
        best_score = -1
        
        for grn_item in grn_matches:
            match_evaluation = await self._evaluate_single_item_match(invoice_item, grn_item)
            
            if match_evaluation['match_score'] > best_score:
                best_score = match_evaluation['match_score']
                best_match = match_evaluation
        
        return best_match

    async def _evaluate_single_item_match(self, invoice_item: InvoiceItemData, grn_item: ItemWiseGrn) -> Dict[str, Any]:
        """Evaluate a single invoice item - GRN item match and return detailed scoring"""
        
        evaluation = {
            'grn_item': grn_item,
            'match_score': 0,
            'match_details': {},
            'variances': {},
            'match_status': 'no_match'
        }
        
        score = 0
        max_score = 100
        
        # 1. HSN Code Match (25 points)
        hsn_match = (invoice_item.hsn_code and grn_item.hsn_no and 
                    invoice_item.hsn_code.strip().upper() == grn_item.hsn_no.strip().upper())
        if hsn_match:
            score += 25
        evaluation['match_details']['hsn_match'] = hsn_match
        
        # 2. Tax Rate Match (15 points)
        tax_rate_match = self._check_tax_rate_match(invoice_item, grn_item)
        if tax_rate_match:
            score += 15
        evaluation['match_details']['tax_rate_match'] = tax_rate_match
        
        # 3. Description Similarity (20 points)
        description_similarity = self._calculate_description_similarity(
            invoice_item.item_description, grn_item.item_name
        )
        description_score = int(description_similarity * 20)
        score += description_score
        evaluation['match_details']['description_similarity'] = description_similarity
        evaluation['match_details']['description_match'] = description_similarity >= 0.7
        
        # 4. Quantity Match (15 points)
        quantity_evaluation = self._evaluate_quantity_match(invoice_item, grn_item)
        score += quantity_evaluation['score']
        evaluation['match_details']['quantity_match'] = quantity_evaluation
        evaluation['variances']['quantity_variance'] = quantity_evaluation['variance']
        
        # 5. Unit Price Match (15 points)
        price_evaluation = self._evaluate_price_match(invoice_item, grn_item)
        score += price_evaluation['score']
        evaluation['match_details']['price_match'] = price_evaluation
        evaluation['variances']['price_variance'] = price_evaluation['variance']
        
        # 6. Total Amount Match (15 points) - This is our subtotal match
        amount_evaluation = self._evaluate_amount_match(invoice_item, grn_item)
        score += amount_evaluation['score']
        evaluation['match_details']['amount_match'] = amount_evaluation  # This represents subtotal match
        evaluation['variances']['amount_variance'] = amount_evaluation['variance']
        
        # 7. Unit of Measurement Match (10 points)
        unit_match = (invoice_item.unit_of_measurement and grn_item.unit and
                    invoice_item.unit_of_measurement.strip().upper() == grn_item.unit.strip().upper())
        if unit_match:
            score += 10
        evaluation['match_details']['unit_match'] = unit_match
        
        evaluation['match_score'] = score
        
        # === NEW: BUILD SPECIFIC MISMATCH LIST ===
        mismatch_types = []
        
        # Core criteria mismatches (these cause overall_match_status = 'mismatch')
        if not hsn_match:
            mismatch_types.append('hsn_mismatch')
        if not tax_rate_match:
            mismatch_types.append('tax_rate_mismatch')
        if not amount_evaluation['within_tolerance']:  # This is subtotal mismatch
            mismatch_types.append('subtotal_mismatch')
        
        # Secondary criteria mismatches (these cause overall_match_status = 'conditional_match')
        if not quantity_evaluation['within_tolerance']:
            mismatch_types.append('quantity_mismatch')
        if not price_evaluation['within_tolerance']:
            mismatch_types.append('price_mismatch')
        #if description_similarity < 0.5:
         #   mismatch_types.append('description_mismatch')
        #if not unit_match:
         #   mismatch_types.append('unit_mismatch')
        
        # Set match_status based on specific issues
        if len(mismatch_types) == 0:
            evaluation['match_status'] = 'perfect_match'
        else:
            evaluation['match_status'] = ', '.join(mismatch_types)
        
        return evaluation

    def _evaluate_quantity_match(self, invoice_item: InvoiceItemData, grn_item: ItemWiseGrn) -> Dict[str, Any]:
        """Evaluate quantity matching between invoice item and GRN item"""
        
        def safe_decimal(value):
            if value is None:
                return Decimal('0.0000')
            return Decimal(str(value))
        
        invoice_qty = safe_decimal(invoice_item.quantity)
        grn_qty = safe_decimal(grn_item.received_qty)
        
        variance = invoice_qty - grn_qty
        
        if grn_qty != 0:
            variance_pct = abs(variance / grn_qty * 100)
        else:
            variance_pct = Decimal('0.00') if variance == 0 else Decimal('100.00')
        
        within_tolerance = variance_pct <= self.tolerance_percentage
        
        # Score based on tolerance (0-15 points)
        if within_tolerance:
            score = 15
        elif variance_pct <= self.tolerance_percentage * 2:
            score = 10
        elif variance_pct <= self.tolerance_percentage * 5:
            score = 5
        else:
            score = 0
        
        return {
            'score': score,
            'within_tolerance': within_tolerance,
            'variance': variance,
            'variance_pct': variance_pct
        }

    def _evaluate_price_match(self, invoice_item: InvoiceItemData, grn_item: ItemWiseGrn) -> Dict[str, Any]:
        """Evaluate unit price matching between invoice item and GRN item"""
        
        def safe_decimal(value):
            if value is None:
                return Decimal('0.0000')
            return Decimal(str(value))
        
        invoice_price = safe_decimal(invoice_item.unit_price)
        grn_price = safe_decimal(grn_item.price)
        
        variance = invoice_price - grn_price
        
        if grn_price != 0:
            variance_pct = abs(variance / grn_price * 100)
        else:
            variance_pct = Decimal('0.00') if variance == 0 else Decimal('100.00')
        
        within_tolerance = variance_pct <= self.tolerance_percentage
        
        # Score based on tolerance (0-15 points)
        if within_tolerance:
            score = 15
        elif variance_pct <= self.tolerance_percentage * 2:
            score = 10
        elif variance_pct <= self.tolerance_percentage * 5:
            score = 5
        else:
            score = 0
        
        return {
            'score': score,
            'within_tolerance': within_tolerance,
            'variance': variance,
            'variance_pct': variance_pct
        }

    def _evaluate_amount_match(self, invoice_item: InvoiceItemData, grn_item: ItemWiseGrn) -> Dict[str, Any]:
        """Evaluate total amount matching between invoice item and GRN item"""
        
        def safe_decimal(value):
            if value is None:
                return Decimal('0.00')
            return Decimal(str(value))
        
        invoice_total = safe_decimal(invoice_item.item_total_amount)
        grn_total = safe_decimal(grn_item.total)
        
        variance = invoice_total - grn_total
        
        if grn_total != 0:
            variance_pct = abs(variance / grn_total * 100)
        else:
            variance_pct = Decimal('0.00') if variance == 0 else Decimal('100.00')
        
        within_tolerance = variance_pct <= self.tolerance_percentage
        
        # Score based on tolerance (0-15 points)
        if within_tolerance:
            score = 15
        elif variance_pct <= self.tolerance_percentage * 2:
            score = 10
        elif variance_pct <= self.tolerance_percentage * 5:
            score = 5
        else:
            score = 0
        
        return {
            'score': score,
            'within_tolerance': within_tolerance,
            'variance': variance,
            'variance_pct': variance_pct
        }

    async def _create_item_reconciliation_record(self, invoice_item: InvoiceItemData, match_evaluation: Dict[str, Any]) -> 'InvoiceItemReconciliation':
        """Create item reconciliation record from match evaluation - UPDATED with overall match status"""
        
        grn_item = match_evaluation['grn_item']
        match_details = match_evaluation['match_details']
        variances = match_evaluation['variances']
        
        # Fixed: Handle variances properly
        def safe_variance_extract(variance_data, key='variance'):
            """Safely extract variance value"""
            if isinstance(variance_data, dict):
                return float(variance_data.get(key, 0))
            elif isinstance(variance_data, (int, float, Decimal)):
                return float(variance_data)
            else:
                return 0.0
        
        def safe_tolerance_extract(variance_data, key='within_tolerance'):
            """Safely extract tolerance value"""
            if isinstance(variance_data, dict):
                return variance_data.get(key, False)
            else:
                return False
        
        def safe_percentage_extract(variance_data, key='variance_pct'):
            """Safely extract variance percentage"""
            if isinstance(variance_data, dict):
                return float(variance_data.get(key, 0))
            else:
                return 0.0
        
        # Generate a batch ID for this reconciliation run
        batch_id = f"ITEM_RECON_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # Map your field names correctly
        reconciliation_data = {
            # === REFERENCE IDs ===
            'invoice_data_id': invoice_item.invoice_data_id,
            'invoice_item_data_id': invoice_item.id,
            'grn_item_id': grn_item.id,
            'reconciliation_batch_id': batch_id,
            
            # === MATCHING DETAILS ===
            'match_status': match_evaluation['match_status'],
            'match_score': Decimal(str(match_evaluation['match_score'] / 100)),  # Convert to 0-1 scale
            
            # === MATCHING ALGORITHM SCORES ===
            'hsn_match_score': Decimal('1.0000') if match_details.get('hsn_match', False) else Decimal('0.0000'),
            'description_match_score': Decimal(str(match_details.get('description_similarity', 0))),
            'amount_match_score': Decimal(str(match_details.get('amount_match', {}).get('score', 0) / 15)),
            'quantity_match_score': Decimal(str(match_details.get('quantity_match', {}).get('score', 0) / 15)),
            
            # === INVOICE ITEM DATA (CACHED) ===
            'invoice_item_sequence': invoice_item.item_sequence,
            'invoice_item_description': invoice_item.item_description or '',
            'invoice_item_hsn': invoice_item.hsn_code or '',
            'invoice_item_quantity': invoice_item.quantity,
            'invoice_item_unit': invoice_item.unit_of_measurement or '',
            'invoice_item_unit_price': invoice_item.unit_price,
            'invoice_item_subtotal': invoice_item.invoice_value_item_wise,
            'invoice_item_cgst_rate': invoice_item.cgst_rate,
            'invoice_item_cgst_amount': invoice_item.cgst_amount,
            'invoice_item_sgst_rate': invoice_item.sgst_rate,
            'invoice_item_sgst_amount': invoice_item.sgst_amount,
            'invoice_item_igst_rate': invoice_item.igst_rate,
            'invoice_item_igst_amount': invoice_item.igst_amount,
            'invoice_item_total_tax': invoice_item.total_tax_amount,
            'invoice_item_total_amount': invoice_item.item_total_amount,
            
            # === GRN ITEM DATA (CACHED) ===
            'grn_item_description': grn_item.item_name or '',
            'grn_item_hsn': grn_item.hsn_no or '',
            'grn_item_quantity': grn_item.received_qty,
            'grn_item_unit': grn_item.unit or '',
            'grn_item_unit_price': grn_item.price,
            'grn_item_subtotal': grn_item.subtotal,
            'grn_item_cgst_rate': grn_item.cgst_tax,
            'grn_item_cgst_amount': grn_item.cgst_tax_amount,
            'grn_item_sgst_rate': grn_item.sgst_tax,
            'grn_item_sgst_amount': grn_item.sgst_tax_amount,
            'grn_item_igst_rate': grn_item.igst_tax,
            'grn_item_igst_amount': grn_item.igst_tax_amount,
            'grn_item_total_tax': grn_item.tax_amount,
            'grn_item_total_amount': grn_item.total,
            
            # === VARIANCE ANALYSIS ===
            'quantity_variance': safe_variance_extract(variances.get('quantity_variance', 0)),
            'quantity_variance_percentage': safe_percentage_extract(variances.get('quantity_variance', {})),
            'subtotal_variance': safe_variance_extract(variances.get('amount_variance', 0)),  # Using amount variance for subtotal
            'subtotal_variance_percentage': safe_percentage_extract(variances.get('amount_variance', {})),
            'total_amount_variance': safe_variance_extract(variances.get('amount_variance', 0)),
            'total_amount_variance_percentage': safe_percentage_extract(variances.get('amount_variance', {})),
            'unit_rate_variance': safe_variance_extract(variances.get('price_variance', 0)),
            
            # Calculate tax variances if both items have tax data
            'cgst_variance': (invoice_item.cgst_amount or 0) - (grn_item.cgst_tax_amount or 0) if invoice_item.cgst_amount and grn_item.cgst_tax_amount else None,
            'sgst_variance': (invoice_item.sgst_amount or 0) - (grn_item.sgst_tax_amount or 0) if invoice_item.sgst_amount and grn_item.sgst_tax_amount else None,
            'igst_variance': (invoice_item.igst_amount or 0) - (grn_item.igst_tax_amount or 0) if invoice_item.igst_amount and grn_item.igst_tax_amount else None,
            'total_tax_variance': (invoice_item.total_tax_amount or 0) - (grn_item.tax_amount or 0) if invoice_item.total_tax_amount and grn_item.tax_amount else None,
            
            # === TOLERANCE FLAGS ===
            'is_within_amount_tolerance': safe_tolerance_extract(variances.get('amount_variance', {})),
            'is_within_quantity_tolerance': safe_tolerance_extract(variances.get('quantity_variance', {})),
            
            # === RECONCILIATION CONFIGURATION ===
            'tolerance_percentage_applied': self.tolerance_percentage,
            'quantity_tolerance_percentage_applied': Decimal('5.00'),  # Default quantity tolerance
            
            # === MATCHING WEIGHTS USED ===
            'hsn_match_weight_applied': Decimal('0.40'),
            'description_match_weight_applied': Decimal('0.30'),
            'amount_match_weight_applied': Decimal('0.30'),
            
            # === FLAGS ===
            'is_auto_matched': True,
            
            # === NOTES ===
            'reconciliation_notes': f"Item-wise rule-based matching. Score: {match_evaluation['match_score']}/100. HSN Match: {match_details.get('hsn_match', False)}, Description Similarity: {match_details.get('description_similarity', 0):.2f}",
            
            # === REFERENCE FIELDS ===
            'po_number': invoice_item.po_number or '',
            'invoice_number': invoice_item.invoice_number or '',
            'grn_number': grn_item.grn_no or '',
            'vendor_name': invoice_item.vendor_name or ''
        }
        
        # === NEW: OVERALL MATCH LOGIC ===
        match_flags = {
            'subtotal': match_details.get('amount_match', {}).get('within_tolerance', False),
            'quantity': match_details.get('quantity_match', {}).get('within_tolerance', False),
            'price': match_details.get('price_match', {}).get('within_tolerance', False),
            'hsn': match_details.get('hsn_match', False),
            'tax_rate': self._check_tax_rate_match(invoice_item, grn_item)
        }

        #description_mismatch = match_details.get('description_similarity', 1.0) < 0.5
        #unit_mismatch = (
        #    invoice_item.unit_of_measurement and grn_item.unit and
        #    invoice_item.unit_of_measurement.strip().upper() != grn_item.unit.strip().upper()
        #)

        # Determine overall status
        if all(match_flags.values()): #and not description_mismatch and not unit_mismatch:
            overall_status = "complete_match"
        elif match_flags['subtotal'] and match_flags['hsn'] and match_flags['tax_rate']:
            overall_status = "conditional_match"
        else:
            overall_status = "mismatch"

        # Add NEW fields to reconciliation_data
        reconciliation_data['overall_match_status'] = overall_status
        reconciliation_data['updated_by'] = 'system'
        
        reconciliation = await sync_to_async(InvoiceItemReconciliation.objects.create)(**reconciliation_data)
        
        logger.info(f"Created item reconciliation record {reconciliation.id} for invoice item {invoice_item.id} with score {match_evaluation['match_score']} and overall status: {overall_status}")
        return reconciliation

    async def _create_no_match_item_record(self, invoice_item: InvoiceItemData) -> Dict[str, Any]:
        """Create no-match record for invoice item - FIXED for your model"""
        
        # Generate a batch ID for this reconciliation run
        import uuid
        from datetime import datetime
        batch_id = f"ITEM_RECON_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        reconciliation_data = {
            # === REFERENCE IDs ===
            'invoice_data_id': invoice_item.invoice_data_id,
            'invoice_item_data_id': invoice_item.id,
            'grn_item_id': None,  # No match found
            'reconciliation_batch_id': batch_id,
            
            # === MATCHING DETAILS ===
            'match_status': 'no_match',
            'match_score': Decimal('0.0000'),
            
            # === MATCHING ALGORITHM SCORES ===
            'hsn_match_score': Decimal('0.0000'),
            'description_match_score': Decimal('0.0000'),
            'amount_match_score': Decimal('0.0000'),
            'quantity_match_score': Decimal('0.0000'),
            
            # === INVOICE ITEM DATA (CACHED) ===
            'invoice_item_sequence': invoice_item.item_sequence,
            'invoice_item_description': invoice_item.item_description or '',
            'invoice_item_hsn': invoice_item.hsn_code or '',
            'invoice_item_quantity': invoice_item.quantity,
            'invoice_item_unit': invoice_item.unit_of_measurement or '',
            'invoice_item_unit_price': invoice_item.unit_price,
            'invoice_item_subtotal': invoice_item.invoice_value_item_wise,
            'invoice_item_cgst_rate': invoice_item.cgst_rate,
            'invoice_item_cgst_amount': invoice_item.cgst_amount,
            'invoice_item_sgst_rate': invoice_item.sgst_rate,
            'invoice_item_sgst_amount': invoice_item.sgst_amount,
            'invoice_item_igst_rate': invoice_item.igst_rate,
            'invoice_item_igst_amount': invoice_item.igst_amount,
            'invoice_item_total_tax': invoice_item.total_tax_amount,
            'invoice_item_total_amount': invoice_item.item_total_amount,
            
            # === GRN ITEM DATA (NULL for no match) ===
            'grn_item_description': None,
            'grn_item_hsn': None,
            'grn_item_quantity': None,
            'grn_item_unit': None,
            'grn_item_unit_price': None,
            'grn_item_subtotal': None,
            'grn_item_cgst_rate': None,
            'grn_item_cgst_amount': None,
            'grn_item_sgst_rate': None,
            'grn_item_sgst_amount': None,
            'grn_item_igst_rate': None,
            'grn_item_igst_amount': None,
            'grn_item_total_tax': None,
            'grn_item_total_amount': None,
            
            # === VARIANCE ANALYSIS (NULL for no match) ===
            'quantity_variance': None,
            'quantity_variance_percentage': None,
            'subtotal_variance': None,
            'subtotal_variance_percentage': None,
            'cgst_variance': None,
            'sgst_variance': None,
            'igst_variance': None,
            'total_tax_variance': None,
            'total_amount_variance': None,
            'total_amount_variance_percentage': None,
            'unit_rate_variance': None,
            
            # === TOLERANCE FLAGS ===
            'is_within_amount_tolerance': False,
            'is_within_quantity_tolerance': False,
            
            # === RECONCILIATION CONFIGURATION ===
            'tolerance_percentage_applied': self.tolerance_percentage,
            'quantity_tolerance_percentage_applied': Decimal('5.00'),
            
            # === MATCHING WEIGHTS USED ===
            'hsn_match_weight_applied': Decimal('0.40'),
            'description_match_weight_applied': Decimal('0.30'),
            'amount_match_weight_applied': Decimal('0.30'),
            
            # === FLAGS ===
            'is_auto_matched': True,
            
            # === NOTES ===
            'reconciliation_notes': 'No matching GRN item records found using rule-based item matching',
            
            # === REFERENCE FIELDS ===
            'po_number': invoice_item.po_number or '',
            'invoice_number': invoice_item.invoice_number or '',
            'grn_number': None,
            'vendor_name': invoice_item.vendor_name or ''
        }
        
        reconciliation = await sync_to_async(InvoiceItemReconciliation.objects.create)(**reconciliation_data)
        
        return {
            'invoice_item_id': invoice_item.id,
            'reconciliation_id': reconciliation.id,
            'match_status': 'no_match',
            'grn_item_matched': None,
            'match_score': 0
        }

    def _update_item_statistics(self, match_status: str):
        """Update processing statistics for items"""
        if match_status == 'perfect_match':
            self.stats['perfect_matches'] += 1
        elif 'hsn_mismatch' in match_status:
            self.stats['hsn_mismatches'] += 1
        elif 'tax_rate_mismatch' in match_status:
            self.stats['tax_rate_mismatches'] += 1
        elif 'subtotal_mismatch' in match_status:
            self.stats['subtotal_mismatches'] += 1
        elif 'quantity_mismatch' in match_status:
            self.stats['quantity_mismatches'] += 1
        elif 'price_mismatch' in match_status:
            self.stats['price_mismatches'] += 1
        #elif 'description_mismatch' in match_status:
        #    self.stats['description_mismatches'] += 1
        #elif 'unit_mismatch' in match_status:
        #   self.stats['unit_mismatches'] += 1
        elif match_status in ['no_match', 'no_grn_item_found']:
            self.stats['no_matches'] += 1
        else:
            self.stats['partial_matches'] += 1 


# Main function to run item-wise reconciliation
async def run_item_wise_reconciliation(
    invoice_ids: List[int] = None, 
    tolerance_percentage: float = 2.0
) -> Dict[str, Any]:
    """
    Main function to run item-wise reconciliation
    
    Args:
        invoice_ids: Optional list of invoice IDs
        tolerance_percentage: Amount tolerance percentage (default 2.0)
    """
    processor = ItemWiseReconciliationProcessor(
        tolerance_percentage=Decimal(str(tolerance_percentage))
    )
    
    return await processor.process_items_for_invoices(invoice_ids=invoice_ids)
