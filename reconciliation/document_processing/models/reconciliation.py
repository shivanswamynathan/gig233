from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class ReconciliationBatch(models.Model):
    """
    Model to track reconciliation batches/runs
    """

    batch_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Batch ID"
    )

    batch_name = models.CharField(
        max_length=255,
        verbose_name="Batch Name"
    )

    # === PROCESSING DETAILS ===
    total_invoices = models.IntegerField(
        default=0,
        verbose_name="Total Invoices"
    )

    processed_invoices = models.IntegerField(
        default=0,
        verbose_name="Processed Invoices"
    )

    perfect_matches = models.IntegerField(
        default=0,
        verbose_name="Perfect Matches"
    )

    partial_matches = models.IntegerField(
        default=0,
        verbose_name="Partial Matches"
    )

    exceptions = models.IntegerField(
        default=0,
        verbose_name="Exceptions"
    )

    no_matches = models.IntegerField(
        default=0,
        verbose_name="No Matches"
    )

    # === STATUS ===
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='running',
        verbose_name="Status"
    )

    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Error Message"
    )

    # === PARAMETERS ===
    tolerance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.00'),
        verbose_name="Tolerance Percentage"
    )

    date_tolerance_days = models.IntegerField(
        default=30,
        verbose_name="Date Tolerance (Days)"
    )

    # === METADATA ===
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Started At"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completed At"
    )

    started_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Started By"
    )

    class Meta:
        db_table = 'reconciliation_batch'
        verbose_name = "Reconciliation Batch"
        verbose_name_plural = "Reconciliation Batches"
        ordering = ['-started_at']

    def __str__(self):
        return f"Batch: {self.batch_name} - {self.status}"

    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.processed_invoices == 0:
            return 0
        return ((self.perfect_matches + self.partial_matches) / self.processed_invoices) * 100

    @property
    def duration(self):
        """Calculate processing duration"""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None


class InvoiceItemReconciliation(models.Model):
    """
    Model to store item-level reconciliation between InvoiceItemData and ItemWiseGrn
    This provides detailed line-by-line matching and variance analysis
    """

    # === REFERENCE IDs (NO FOREIGN KEYS) ===
    invoice_data_id = models.IntegerField(
        verbose_name="Invoice Data ID",
        db_index=True,
        help_text="ID reference to the parent invoice record"
    )

    invoice_item_data_id = models.IntegerField(
        verbose_name="Invoice Item Data ID",
        db_index=True,
        help_text="ID reference to the invoice line item"
    )

    grn_item_id = models.IntegerField(
        verbose_name="GRN Item ID",
        null=True,
        blank=True,
        db_index=True,
        help_text="ID reference to the matched GRN line item (null if no match)"
    )

    # === BATCH TRACKING ===
    reconciliation_batch_id = models.CharField(
        max_length=100,
        verbose_name="Reconciliation Batch ID",
        db_index=True,
        help_text="Batch ID for tracking this reconciliation run"
    )

    # === MATCHING DETAILS ===
    match_status = models.CharField(
        max_length=200,
        choices=[
            ('perfect_match', 'Perfect Match'),
            ('partial_match', 'Partial Match'),
            ('amount_mismatch', 'Amount Mismatch'),
            ('quantity_mismatch', 'Quantity Mismatch'),
            ('hsn_mismatch', 'HSN Code Mismatch'),
            ('description_mismatch', 'Description Mismatch'),
            ('no_match', 'No Match Found'),
        ],
        default='no_match',
        verbose_name="Item Match Status",
        db_index=True
    )

    match_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name="Match Score",
        help_text="Overall match score (0.0000 to 1.0000)"
    )

    # === MATCHING ALGORITHM SCORES ===
    hsn_match_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name="HSN Match Score"
    )

    description_match_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name="Description Match Score"
    )

    amount_match_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name="Amount Match Score"
    )

    quantity_match_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name="Quantity Match Score"
    )

    # === INVOICE ITEM DATA (CACHED FOR COMPARISON) ===
    invoice_item_sequence = models.PositiveIntegerField(
        verbose_name="Invoice Item Sequence"
    )

    invoice_item_description = models.CharField(
        max_length=1000,
        verbose_name="Invoice Item Description"
    )

    invoice_item_hsn = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Invoice HSN Code"
    )

    invoice_item_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Invoice Quantity"
    )

    invoice_item_unit = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Invoice Unit of Measurement"
    )

    invoice_item_unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Invoice Unit Price"
    )

    invoice_item_subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice Item Subtotal"
    )

    invoice_item_cgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice CGST Rate"
    )

    invoice_item_cgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice CGST Amount"
    )

    invoice_item_sgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice SGST Rate"
    )

    invoice_item_sgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice SGST Amount"
    )

    invoice_item_igst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice IGST Rate"
    )

    invoice_item_igst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice IGST Amount"
    )

    invoice_item_total_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice Total Tax Amount"
    )

    invoice_item_total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Invoice Item Total Amount"
    )

    # === GRN ITEM DATA (CACHED FOR COMPARISON) ===
    grn_item_description = models.CharField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name="GRN Item Description"
    )

    grn_item_hsn = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="GRN HSN Code"
    )

    grn_item_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="GRN Received Quantity"
    )

    grn_item_unit = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="GRN Unit of Measurement"
    )

    grn_item_unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="GRN Unit Price"
    )

    grn_item_subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN Item Subtotal"
    )

    grn_item_cgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN CGST Rate"
    )

    grn_item_cgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN CGST Amount"
    )

    grn_item_sgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN SGST Rate"
    )

    grn_item_sgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN SGST Amount"
    )

    grn_item_igst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN IGST Rate"
    )

    grn_item_igst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN IGST Amount"
    )

    grn_item_total_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN Total Tax Amount"
    )

    grn_item_total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="GRN Item Total Amount"
    )

    # === VARIANCE ANALYSIS ===
    quantity_variance = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Quantity Variance",
        help_text="Invoice Quantity - GRN Quantity"
    )

    quantity_variance_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Quantity Variance %"
    )

    subtotal_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Subtotal Variance",
        help_text="Invoice Subtotal - GRN Subtotal"
    )

    subtotal_variance_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Subtotal Variance %"
    )

    cgst_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="CGST Variance"
    )

    sgst_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="SGST Variance"
    )

    igst_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="IGST Variance"
    )

    total_tax_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Total Tax Variance"
    )

    total_amount_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Total Amount Variance",
        help_text="Invoice Total - GRN Total"
    )

    total_amount_variance_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Total Amount Variance %"
    )

    unit_rate_variance = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Unit Rate Variance",
        help_text="Invoice Unit Price - GRN Unit Price"
    )

    # === TOLERANCE FLAGS ===
    is_within_amount_tolerance = models.BooleanField(
        default=False,
        verbose_name="Within Amount Tolerance",
        help_text="Whether amount variance is within configured tolerance"
    )

    is_within_quantity_tolerance = models.BooleanField(
        default=False,
        verbose_name="Within Quantity Tolerance",
        help_text="Whether quantity variance is within configured tolerance"
    )

    # === RECONCILIATION CONFIGURATION ===
    tolerance_percentage_applied = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.00'),
        verbose_name="Amount Tolerance Applied (%)"
    )

    quantity_tolerance_percentage_applied = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        verbose_name="Quantity Tolerance Applied (%)"
    )

    # === MATCHING WEIGHTS USED ===
    hsn_match_weight_applied = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.40'),
        verbose_name="HSN Match Weight Applied"
    )

    description_match_weight_applied = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.30'),
        verbose_name="Description Match Weight Applied"
    )

    amount_match_weight_applied = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.30'),
        verbose_name="Amount Match Weight Applied"
    )

    # === FLAGS ===
    requires_review = models.BooleanField(
        default=False,
        verbose_name="Requires Review",
        help_text="Whether this item reconciliation needs manual review"
    )

    is_exception = models.BooleanField(
        default=False,
        verbose_name="Is Exception",
        help_text="Whether this item is flagged as an exception"
    )

    is_auto_matched = models.BooleanField(
        default=True,
        verbose_name="Auto Matched",
        help_text="Whether this was automatically matched"
    )

    # === NOTES ===
    reconciliation_notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Reconciliation Notes",
        help_text="Additional notes about this item reconciliation"
    )
    manual_match = models.BooleanField(
        default=False,
        verbose_name="Manual Match",
        help_text="Whether this reconciliation was manually matched/swapped by user"
    )

    # === REFERENCE FIELDS FOR EASY QUERYING ===
    po_number = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="PO Number"
    )

    invoice_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Invoice Number"
    )

    grn_number = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="GRN Number"
    )

    vendor_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Vendor Name"
    )

    # === TIMESTAMPS ===
    reconciled_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Reconciled At"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )
    # === NEW OVERALL MATCH STATUS FIELDS ===
    overall_match_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Overall Match Status",
        db_index=True
    )

    match_notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Match Notes"
    )

    updated_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Updated By"
    )

    class Meta:
        db_table = 'invoice_item_reconciliation'
        verbose_name = "Invoice Item Reconciliation"
        verbose_name_plural = "Invoice Item Reconciliations"
        ordering = ['-reconciled_at', 'invoice_item_sequence']

        indexes = [
            models.Index(fields=['invoice_data_id']),
            models.Index(fields=['invoice_item_data_id']),
            models.Index(fields=['grn_item_id']),
            models.Index(fields=['reconciliation_batch_id']),
            models.Index(fields=['match_status']),
            models.Index(fields=['po_number']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['grn_number']),
            models.Index(fields=['requires_review', 'is_exception']),
            models.Index(fields=['reconciled_at']),
            models.Index(fields=['invoice_item_hsn']),
            models.Index(fields=['grn_item_hsn']),
            models.Index(fields=['overall_match_status']),
        ]

        # Prevent duplicate reconciliations for same invoice item
        unique_together = [
            ['invoice_item_data_id', 'reconciliation_batch_id']
        ]

    def __str__(self):
        return f"Item Reconciliation: Invoice Item {self.invoice_item_data_id} -> GRN Item {self.grn_item_id or 'None'} ({self.match_status})"

    @property
    def is_perfect_match(self):
        """Check if this is a perfect match"""
        return self.match_status == 'perfect_match'

    @property
    def has_significant_variance(self):
        """Check if there are significant variances requiring attention"""
        if not self.is_within_amount_tolerance or not self.is_within_quantity_tolerance:
            return True

        # Check if any variance percentage exceeds 10%
        variances = [
            self.quantity_variance_percentage,
            self.subtotal_variance_percentage,
            self.total_amount_variance_percentage
        ]

        for variance in variances:
            if variance and abs(variance) > 10:
                return True

        return False

    @property
    def match_quality_description(self):
        """Get human-readable match quality description"""
        quality_map = {
            'perfect_match': 'Perfect Match - All criteria met',
            'partial_match': 'Partial Match - Most criteria met',
            'amount_mismatch': 'Amount Mismatch - Amounts do not match within tolerance',
            'quantity_mismatch': 'Quantity Mismatch - Quantities do not match within tolerance',
            'hsn_mismatch': 'HSN Mismatch - HSN codes do not match',
            'description_mismatch': 'Description Mismatch - Item descriptions do not match',
            'no_match': 'No Match - No suitable GRN item found'
        }
        return quality_map.get(self.match_status, 'Unknown')

    def save(self, *args, **kwargs):
        """Override save to automatically set flags"""
        # Set requires_review flag
        self.requires_review = (
            self.match_status in ['amount_mismatch', 'quantity_mismatch', 'no_match'] or
            not self.is_within_amount_tolerance or
            not self.is_within_quantity_tolerance or
            self.has_significant_variance
        )

        # Set is_exception flag
        self.is_exception = (
            self.match_status == 'no_match' or
            (self.total_amount_variance_percentage and abs(
                self.total_amount_variance_percentage) > 15)
        )

        super().save(*args, **kwargs)


class InvoiceGrnReconciliation(models.Model):
    """
    Model to store invoice-level reconciliation between InvoiceData and ItemWiseGrn
    """

    # === MATCHING KEYS ===
    po_number = models.CharField(
        max_length=200,
        verbose_name="PO Number",
        db_index=True,
        help_text="Purchase Order Number used for matching"
    )

    grn_number = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="GRN Number",
        db_index=True,
        help_text="Goods Receipt Note Number"
    )

    invoice_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Invoice Number",
        db_index=True,
        help_text="Invoice Number from both sources"
    )

    # === REFERENCE TO SOURCE RECORDS ===
    invoice_data_id = models.IntegerField(
        verbose_name="Invoice Data ID",
        help_text="ID reference to the related invoice record"
    )

    # === MATCH STATUS ===
    MATCH_STATUS_CHOICES = [
        ('perfect_match', 'Perfect Match'),
        ('partial_match', 'Partial Match'),
        ('amount_mismatch', 'Amount Mismatch'),
        ('vendor_mismatch', 'Vendor Mismatch'),
        ('date_mismatch', 'Date Mismatch'),
        ('no_grn_found', 'No GRN Found'),
        ('multiple_grn', 'Multiple GRN Records'),
        ('no_match', 'No Match'),
    ]

    match_status = models.CharField(
        max_length=50,
        choices=MATCH_STATUS_CHOICES,
        default='no_match',
        verbose_name="Match Status",
        db_index=True
    )

    # === VENDOR VALIDATION ===
    vendor_match = models.BooleanField(
        default=False,
        verbose_name="Vendor Match",
        help_text="Whether vendor names match"
    )

    invoice_vendor = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Invoice Vendor"
    )

    grn_vendor = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="GRN Vendor"
    )

    # === GST VALIDATION ===
    gst_match = models.BooleanField(
        default=False,
        verbose_name="GST Match",
        help_text="Whether GST numbers match"
    )

    invoice_gst = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="Invoice GST"
    )

    grn_gst = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="GRN GST"
    )

    # === DATE VALIDATION ===
    date_valid = models.BooleanField(
        default=False,
        verbose_name="Date Valid",
        help_text="Whether invoice date <= GRN created date"
    )

    invoice_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Invoice Date"
    )

    grn_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="GRN Created Date"
    )

    # === INVOICE AMOUNTS ===
    invoice_subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Invoice Subtotal",
        help_text="Invoice value without GST"
    )

    invoice_cgst = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Invoice CGST"
    )

    invoice_sgst = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Invoice SGST"
    )

    invoice_igst = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Invoice IGST"
    )

    invoice_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Invoice Total",
        help_text="Total invoice amount including GST"
    )

    # === GRN AGGREGATED AMOUNTS (SUM of all line items) ===
    grn_subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="GRN Subtotal",
        help_text="Sum of all GRN line item subtotals"
    )

    grn_cgst = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="GRN Total CGST"
    )

    grn_sgst = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="GRN Total SGST"
    )

    grn_igst = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="GRN Total IGST"
    )

    grn_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="GRN Total",
        help_text="Sum of all GRN line item totals"
    )

    # === VARIANCE ANALYSIS ===
    subtotal_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Subtotal Variance",
        help_text="Invoice Subtotal - GRN Subtotal"
    )

    cgst_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="CGST Variance"
    )

    sgst_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="SGST Variance"
    )

    igst_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="IGST Variance"
    )

    total_variance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Total Variance",
        help_text="Invoice Total - GRN Total"
    )

    # === SUMMARY INFORMATION ===
    total_grn_line_items = models.IntegerField(
        default=0,
        verbose_name="Total GRN Line Items",
        help_text="Number of GRN line items matched"
    )

    matching_method = models.CharField(
        max_length=50,
        choices=[
            ('exact_match', 'PO + GRN + Invoice Number'),
            ('po_grn_match', 'PO + GRN Number'),
            ('po_only_match', 'PO Number Only'),
            ('manual_match', 'Manual Override'),
        ],
        null=True,
        blank=True,
        verbose_name="Matching Method"
    )

    reconciliation_notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Reconciliation Notes",
        help_text="Additional notes about the reconciliation"
    )

    # === TOLERANCE AND THRESHOLDS ===
    tolerance_applied = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.00'),
        verbose_name="Tolerance Applied (%)",
        help_text="Tolerance percentage applied for matching"
    )

    # === APPROVAL WORKFLOW ===
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
    ]

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        verbose_name="Approval Status"
    )

    approved_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Approved By"
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Approved At"
    )

    status = models.BooleanField(
        default=False,
        verbose_name="Status",
        help_text="User approval status - True when user approves"
    )

    invoice_approval = models.BooleanField(
        default=False,
        verbose_name="Invoice Approval"
    )


    # === METADATA ===
    reconciled_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Reconciled At"
    )

    reconciled_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Reconciled By"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )

    # === FLAGS ===
    is_auto_matched = models.BooleanField(
        default=True,
        verbose_name="Auto Matched",
        help_text="Whether this was automatically matched"
    )

    requires_review = models.BooleanField(
        default=False,
        verbose_name="Requires Review",
        help_text="Whether this reconciliation needs manual review"
    )

    is_exception = models.BooleanField(
        default=False,
        verbose_name="Is Exception",
        help_text="Whether this is flagged as an exception"
    )

    class Meta:
        db_table = 'invoice_grn_reconciliation'
        verbose_name = "Invoice GRN Reconciliation"
        verbose_name_plural = "Invoice GRN Reconciliations"
        ordering = ['-reconciled_at', 'po_number']

        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['grn_number']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['match_status']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['vendor_match', 'gst_match', 'date_valid']),
            models.Index(fields=['is_exception', 'requires_review']),
            models.Index(fields=['reconciled_at']),
        ]

        # Prevent duplicate reconciliations
        unique_together = [
            ['invoice_data_id', 'po_number']
        ]

    def __str__(self):
        return f"Reconciliation: {self.po_number} - {self.match_status}"

    @property
    def is_within_tolerance(self):
        """Check if total variance is within tolerance"""
        if self.total_variance is None or self.grn_total is None or self.grn_total == 0:
            return False

        variance_pct = abs(self.total_variance / self.grn_total) * 100
        return variance_pct <= self.tolerance_applied

    @property
    def match_score(self):
        """Calculate overall match score (0-100)"""
        score = 0

        # Basic match (30 points)
        if self.po_number:
            score += 30

        # Vendor match (20 points)
        if self.vendor_match:
            score += 20

        # GST match (15 points)
        if self.gst_match:
            score += 15

        # Date validation (10 points)
        if self.date_valid:
            score += 10

        # Amount tolerance (25 points)
        if self.is_within_tolerance:
            score += 25
        elif self.total_variance is not None and self.grn_total is not None and self.grn_total != 0:
            variance_pct = abs(self.total_variance / self.grn_total) * 100
            variance_ratio = variance_pct / self.tolerance_applied
            if variance_ratio <= 2.0:  # Within 2x tolerance
                score += max(5, 25 - (variance_ratio * 10))

        return min(100, score)

    @property
    def exception_reasons(self):
        """Get list of exception reasons"""
        reasons = []

        if not self.vendor_match:
            reasons.append("Vendor mismatch")
        if not self.gst_match:
            reasons.append("GST number mismatch")
        if not self.date_valid:
            reasons.append("Date validation failed")
        if not self.is_within_tolerance:
            if self.total_variance is not None and self.grn_total is not None and self.grn_total != 0:
                variance_pct = abs(self.total_variance / self.grn_total) * 100
                reasons.append(
                    f"Amount variance {variance_pct:.2f}% exceeds tolerance")
            else:
                reasons.append("Amount variance exceeds tolerance")

        if self.total_grn_line_items == 0:
            reasons.append("No matching GRN records found")

        return reasons

    def save(self, *args, **kwargs):
        """Override save to automatically set flags"""
        # Calculate variance percentage for flags
        variance_pct = 0
        if self.total_variance is not None and self.grn_total is not None and self.grn_total != 0:
            variance_pct = abs(self.total_variance / self.grn_total) * 100

        # Set requires_review flag
        self.requires_review = (
            self.match_status in ['amount_mismatch', 'vendor_mismatch', 'multiple_grn'] or
            not self.is_within_tolerance or
            self.total_grn_line_items == 0
        )

        # Set is_exception flag
        self.is_exception = (
            self.match_status in ['no_match', 'no_grn_found'] or
            variance_pct > 10.0
        )

        super().save(*args, **kwargs)
