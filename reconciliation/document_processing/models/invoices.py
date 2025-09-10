from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class InvoiceData(models.Model):
    """Model to store extracted invoice data from attachments"""

    # === SOURCE REFERENCE ===

    attachment_number = models.CharField(
        max_length=2,
        choices=[('1', 'Attachment 1'), ('2', 'Attachment 2'),
                 ('3', 'Attachment 3'), ('4', 'Attachment 4'), ('5', 'Attachment 5')],
        verbose_name="Attachment Number"
    )

    attachment_url = models.URLField(
        max_length=1000,
        verbose_name="Original Attachment URL"
    )

    # === FILE CLASSIFICATION ===
    file_type = models.CharField(
        max_length=20,
        choices=[
            ('pdf_text', 'PDF - Text Based'),
            ('pdf_image', 'PDF - Image Based'),
            ('image', 'Image File'),
            ('unknown', 'Unknown/Failed'),
        ],
        verbose_name="File Processing Type"
    )

    original_file_extension = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Original File Extension",
        help_text="Original file extension (.pdf, .jpg, .png, etc.)"
    )

    # === INVOICE DATA ===
    vendor_name = models.CharField(max_length=255, blank=True, null=True)
    vendor_pan = models.CharField(max_length=10, blank=True, null=True)
    vendor_gst = models.CharField(max_length=15, blank=True, null=True)
    invoice_date = models.DateField(blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    po_number = models.CharField(
        max_length=200, blank=True, null=True, db_index=True)
    grn_number = models.CharField(max_length=100, blank=True, null=True)

    # === FINANCIAL DATA ===
    invoice_value_without_gst = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    cgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True)
    cgst_amount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    sgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True)
    sgst_amount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    igst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True)
    igst_amount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_gst_amount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    cess_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        verbose_name="CESS Rate"
    )
    cess_amount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="CESS Amount"
    )
    transport_charges = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Transport Charges"
    )
    invoice_total_post_gst = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    invoice_discount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Invoice Discount"
    )

    # === STATUS FLAGS ===
    matched = models.BooleanField(
        default=False,
        verbose_name="Matched"
    )

    duplicates = models.BooleanField(
        default=False,
        verbose_name="Duplicates"
    )

    # === ITEMS (JSON) ===
    items_data = models.JSONField(blank=True, null=True)

    # === PROCESSING METADATA ===
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True, null=True)
    extracted_at = models.DateTimeField(blank=True, null=True)

    # === TIMESTAMPS ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # === INVOICE TYPE ===
    type = models.CharField(
        max_length=50,
        default='invoice',
        db_index=True,
        verbose_name='Type'
    )

    # === FAILURE HANDLING ===
    failure_reason = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Failure Reason"
    )

    manually_enter = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Manually enter",
        help_text="Key entered manually from frontend"
    )

    class Meta:
        db_table = 'invoice_data'
        verbose_name = "Invoice Data"
        verbose_name_plural = "Invoice Data Records"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['vendor_gst']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['file_type']),
            models.Index(fields=['attachment_url']),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number or 'Unknown'} - PO {self.po_number or 'N/A'}"

    def save(self, *args, **kwargs):

        # Auto-extract PAN from GST if not set
        if self.vendor_gst and not self.vendor_pan and len(self.vendor_gst) >= 15:
            self.vendor_pan = self.vendor_gst[2:12]

        super().save(*args, **kwargs)


class InvoiceItemData(models.Model):
    """Model to store individual invoice items separately"""

    invoice_data_id = models.IntegerField(
        verbose_name="Invoice Data ID",
        help_text="ID reference to the related invoice record"
    )

    # === ITEM DETAILS ===
    item_description = models.CharField(
        max_length=1000,
        verbose_name="Item Description"
    )

    hsn_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="HSN Code"
    )

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.0000'))],
        verbose_name="Quantity"
    )

    unit_of_measurement = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Unit of Measurement"
    )

    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.0000'))],
        verbose_name="Unit Price"
    )

    invoice_value_item_wise = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Item-wise Invoice Value"
    )

    # === TAX DETAILS ===
    cgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="CGST Rate"
    )

    cgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="CGST Amount"
    )

    sgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="SGST Rate"
    )

    sgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="SGST Amount"
    )

    igst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="IGST Rate"
    )

    igst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="IGST Amount"
    )

    cess_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        verbose_name="CESS Rate"
    )
    cess_amount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="CESS Amount"
    )

    # === DISCOUNT FIELD ===
    discount_amount = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Discount Amount"
    )

    total_tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total Tax Amount"
    )

    item_total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Item Total Amount"
    )

    # === REFERENCE FIELDS ===
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

    vendor_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Vendor Name"
    )

    manually_enter = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Manually Enter",
        help_text="Key entered manually from frontend"
    )

    item_sequence = models.PositiveIntegerField(
        default=1,
        verbose_name="Item Sequence"
    )

    # === TIMESTAMPS ===
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        db_table = 'invoice_item_data'
        verbose_name = "Invoice Item Data"
        verbose_name_plural = "Invoice Items Data"
        ordering = ['invoice_data_id', 'item_sequence']
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['hsn_code']),
            models.Index(fields=['vendor_name']),
            models.Index(fields=['invoice_data_id', 'item_sequence']),
        ]

    def __str__(self):
        return f"Item {self.item_sequence}: {self.item_description[:50]} - Invoice {self.invoice_number}"

    @property
    def calculated_total_tax(self):
        """Calculate total tax from individual tax components"""
        total = Decimal('0.00')
        if self.cgst_amount:
            total += self.cgst_amount
        if self.sgst_amount:
            total += self.sgst_amount
        if self.igst_amount:
            total += self.igst_amount
        return total if total > 0 else None
