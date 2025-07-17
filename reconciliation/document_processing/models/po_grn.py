from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class PoGrn(models.Model):
    """
    Model to store PO-GRN data from Excel/CSV uploads
    """

    # PO Information
    s_no = models.IntegerField(
        verbose_name="Serial Number",
        validators=[MinValueValidator(1)],
        help_text="Serial number from the uploaded file"
    )

    location = models.CharField(
        max_length=255,
        verbose_name="Location",
        help_text="Store/warehouse location"
    )

    po_number = models.CharField(
        max_length=100,
        verbose_name="PO Number",
        db_index=True,
        help_text="Purchase Order Number"
    )

    po_creation_date = models.DateField(
        verbose_name="PO Creation Date",
        help_text="Date when the PO was created"
    )

    no_item_in_po = models.IntegerField(
        verbose_name="Number of Items in PO",
        validators=[MinValueValidator(0)],
        help_text="Total number of items in the purchase order"
    )

    po_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="PO Amount",
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount of the purchase order"
    )

    po_status = models.CharField(
        max_length=50,
        verbose_name="PO Status",
        help_text="Status of the purchase order (e.g., Completed, In Process)"
    )

    supplier_name = models.CharField(
        max_length=255,
        verbose_name="Supplier Name",
        db_index=True,
        help_text="Name of the supplier/vendor"
    )

    concerned_person = models.CharField(
        max_length=255,
        verbose_name="Concerned Person",
        blank=True,
        null=True,
        help_text="Person responsible for the PO"
    )

    # GRN Information
    grn_number = models.CharField(
        max_length=100,
        verbose_name="GRN Number",
        db_index=True,
        blank=True,
        null=True,
        help_text="Goods Receipt Note Number"
    )

    grn_creation_date = models.DateField(
        verbose_name="GRN Creation Date",
        blank=True,
        null=True,
        help_text="Date when the GRN was created"
    )

    no_item_in_grn = models.IntegerField(
        verbose_name="Number of Items in GRN",
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
        help_text="Total number of items in the goods receipt note"
    )

    received_status = models.CharField(
        max_length=50,
        verbose_name="Received Status",
        blank=True,
        null=True,
        help_text="Status of goods receipt (e.g., Received, Pending)"
    )

    grn_subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="GRN Subtotal",
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True,
        help_text="Subtotal amount before tax in GRN"
    )

    grn_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="GRN Tax",
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True,
        help_text="Tax amount in GRN"
    )

    grn_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="GRN Amount",
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True,
        help_text="Total amount including tax in GRN"
    )

    # Upload metadata
    upload_batch_id = models.CharField(
        max_length=100,
        verbose_name="Upload Batch ID",
        db_index=True,
        help_text="Unique identifier for the upload session"
    )

    uploaded_filename = models.CharField(
        max_length=255,
        verbose_name="Uploaded Filename",
        help_text="Original filename of the uploaded file"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )

    class Meta:
        db_table = 'po_grn'
        verbose_name = "PO GRN Record"
        verbose_name_plural = "PO GRN Records"
        ordering = ['s_no', 'po_creation_date']
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['grn_number']),
            models.Index(fields=['supplier_name']),
            models.Index(fields=['upload_batch_id']),
            models.Index(fields=['po_creation_date']),
            models.Index(fields=['grn_creation_date']),
        ]

        # Unique constraint to prevent duplicate entries
        unique_together = [
            ['po_number', 'grn_number', 'upload_batch_id']
        ]

    def __str__(self):
        return f"PO: {self.po_number} - GRN: {self.grn_number or 'N/A'}"

    @property
    def po_grn_variance(self):
        """Calculate variance between PO amount and GRN amount"""
        if self.grn_amount:
            return self.po_amount - self.grn_amount
        return None

    @property
    def item_variance(self):
        """Calculate variance between PO items and GRN items"""
        if self.no_item_in_grn:
            return self.no_item_in_po - self.no_item_in_grn
        return None

    @property
    def is_fully_received(self):
        """Check if all items from PO are received in GRN"""
        return (
            self.received_status and
            self.received_status.lower() == 'received' and
            self.no_item_in_grn == self.no_item_in_po
        )


class ItemWiseGrn(models.Model):
    """
    Model to store item-wise GRN data from Excel/CSV uploads
    """

    # Basic Information
    s_no = models.IntegerField(
        verbose_name="Serial Number",
        validators=[MinValueValidator(1)],
        help_text="Serial number from the uploaded file"
    )

    type = models.CharField(
        max_length=100,
        verbose_name="Type",
        null=True,
        blank=True,
        help_text="Type of transaction (e.g., InterStock)"
    )

    sku_code = models.CharField(
        max_length=100,
        verbose_name="SKU Code",
        db_index=True,
        null=True,
        blank=True,
        help_text="Stock Keeping Unit code"
    )

    category = models.CharField(
        max_length=255,
        verbose_name="Category",
        null=True,
        blank=True,
        help_text="Product category"
    )

    sub_category = models.CharField(
        max_length=255,
        verbose_name="Sub Category",
        null=True,
        blank=True,
        help_text="Product sub-category"
    )

    item_name = models.CharField(
        max_length=500,
        verbose_name="Item Name",
        null=True,
        blank=True,
        help_text="Name/description of the item"
    )

    unit = models.CharField(
        max_length=50,
        verbose_name="Unit",
        null=True,
        blank=True,
        help_text="Unit of measurement (piece, kg, etc.)"
    )

    # GRN and PO Information
    grn_no = models.CharField(
        max_length=200,
        verbose_name="GRN Number",
        db_index=True,
        null=True,
        blank=True,
        help_text="Goods Receipt Note Number"
    )

    hsn_no = models.CharField(
        max_length=20,
        verbose_name="HSN Code",
        null=True,
        blank=True,
        help_text="Harmonized System of Nomenclature code"
    )

    po_no = models.CharField(
        max_length=200,
        verbose_name="PO Number",
        db_index=True,
        null=True,
        blank=True,
        help_text="Purchase Order Number"
    )

    remarks = models.TextField(
        verbose_name="Remarks",
        null=True,
        blank=True,
        help_text="Additional remarks or notes"
    )

    created_by = models.CharField(
        max_length=255,
        verbose_name="Created By",
        null=True,
        blank=True,
        help_text="Person who created the GRN"
    )

    grn_created_at = models.DateField(
        verbose_name="GRN Created Date",
        null=True,
        blank=True,
        help_text="Date when GRN was created"
    )

    # Invoice Information
    seller_invoice_no = models.CharField(
        max_length=200,
        verbose_name="Seller Invoice Number",
        null=True,
        blank=True,
        help_text="Invoice number from seller"
    )

    supplier_invoice_date = models.DateField(
        verbose_name="Supplier Invoice Date",
        null=True,
        blank=True,
        help_text="Date of supplier invoice"
    )

    supplier = models.CharField(
        max_length=500,
        verbose_name="Supplier",
        db_index=True,
        null=True,
        blank=True,
        help_text="Supplier/vendor name"
    )

    concerned_person = models.CharField(
        max_length=255,
        verbose_name="Concerned Person",
        null=True,
        blank=True,
        help_text="Person responsible for the transaction"
    )

    # Pickup Location Details
    pickup_location = models.CharField(
        max_length=500,
        verbose_name="Pickup Location",
        null=True,
        blank=True,
        help_text="Pickup location name"
    )

    pickup_gstin = models.CharField(
        max_length=15,
        verbose_name="Pickup GSTIN",
        null=True,
        blank=True,
        help_text="GST Identification Number for pickup location"
    )

    pickup_code = models.CharField(
        max_length=100,
        verbose_name="Pickup Code",
        null=True,
        blank=True,
        help_text="Pickup location code"
    )

    pickup_city = models.CharField(
        max_length=255,
        verbose_name="Pickup City",
        null=True,
        blank=True,
        help_text="Pickup city"
    )

    pickup_state = models.CharField(
        max_length=255,
        verbose_name="Pickup State",
        null=True,
        blank=True,
        help_text="Pickup state"
    )

    # Delivery Location Details
    delivery_location = models.CharField(
        max_length=500,
        verbose_name="Delivery Location",
        null=True,
        blank=True,
        help_text="Delivery location name"
    )

    delivery_gstin = models.CharField(
        max_length=15,
        verbose_name="Delivery GSTIN",
        null=True,
        blank=True,
        help_text="GST Identification Number for delivery location"
    )

    delivery_code = models.CharField(
        max_length=100,
        verbose_name="Delivery Code",
        null=True,
        blank=True,
        help_text="Delivery location code"
    )

    delivery_city = models.CharField(
        max_length=255,
        verbose_name="Delivery City",
        null=True,
        blank=True,
        help_text="Delivery city"
    )

    delivery_state = models.CharField(
        max_length=255,
        verbose_name="Delivery State",
        null=True,
        blank=True,
        help_text="Delivery state"
    )

    # Financial Information
    price = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        verbose_name="Price",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text="Unit price of the item"
    )

    received_qty = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        verbose_name="Received Quantity",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text="Quantity received"
    )

    returned_qty = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        verbose_name="Returned Quantity",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text="Quantity returned"
    )

    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Discount",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Discount amount"
    )

    tax = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Tax Rate",
        null=True,
        blank=True,
        help_text="Tax rate percentage"
    )

    # GST Details
    sgst_tax = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="SGST Tax Rate",
        null=True,
        blank=True,
        help_text="State GST rate percentage"
    )

    sgst_tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="SGST Tax Amount",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="State GST amount"
    )

    cgst_tax = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="CGST Tax Rate",
        null=True,
        blank=True,
        help_text="Central GST rate percentage"
    )

    cgst_tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="CGST Tax Amount",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Central GST amount"
    )

    igst_tax = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="IGST Tax Rate",
        null=True,
        blank=True,
        help_text="Integrated GST rate percentage"
    )

    igst_tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="IGST Tax Amount",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Integrated GST amount"
    )

    cess = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Cess",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cess amount"
    )

    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Subtotal",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Subtotal before taxes"
    )

    # VAT Information
    vat_percent = models.CharField(
        max_length=20,
        verbose_name="VAT Percentage",
        null=True,
        blank=True,
        help_text="VAT percentage"
    )

    vat_amount = models.CharField(
        max_length=50,
        verbose_name="VAT Amount",
        null=True,
        blank=True,
        help_text="VAT amount"
    )

    # TCS Information
    item_tcs_percent = models.CharField(
        max_length=20,
        verbose_name="Item TCS Percentage",
        null=True,
        blank=True,
        help_text="Item TCS percentage"
    )

    item_tcs_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Item TCS Amount",
        null=True,
        blank=True,
        help_text="Item TCS amount"
    )

    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Total Tax Amount",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total tax amount"
    )

    bill_tcs = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Bill TCS",
        null=True,
        blank=True,
        help_text="Bill TCS amount"
    )

    # Additional Charges
    delivery_charges = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Delivery Charges",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Delivery charges"
    )

    delivery_charges_tax_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Delivery Charges Tax Percentage",
        null=True,
        blank=True,
        help_text="Tax percentage on delivery charges"
    )

    additional_charges = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Additional Charges",
        null=True,
        blank=True,
        help_text="Additional charges"
    )

    inv_discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Invoice Discount",
        null=True,
        blank=True,
        help_text="Invoice level discount"
    )

    round_off = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Round Off",
        null=True,
        blank=True,
        help_text="Round off amount"
    )

    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Total Amount",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount including all taxes and charges"
    )

    # Attachment Information
    attachment_upload_date = models.DateField(
        verbose_name="Attachment Upload Date",
        null=True,
        blank=True,
        help_text="Date when attachments were uploaded"
    )

    attachment_1 = models.URLField(
        max_length=1000,
        verbose_name="Attachment 1",
        null=True,
        blank=True,
        help_text="URL to attachment 1"
    )

    attachment_2 = models.URLField(
        max_length=1000,
        verbose_name="Attachment 2",
        null=True,
        blank=True,
        help_text="URL to attachment 2"
    )

    attachment_3 = models.URLField(
        max_length=1000,
        verbose_name="Attachment 3",
        null=True,
        blank=True,
        help_text="URL to attachment 3"
    )

    attachment_4 = models.URLField(
        max_length=1000,
        verbose_name="Attachment 4",
        null=True,
        blank=True,
        help_text="URL to attachment 4"
    )

    attachment_5 = models.URLField(
        max_length=1000,
        verbose_name="Attachment 5",
        null=True,
        blank=True,
        help_text="URL to attachment 5"
    )

    # === EXTRACTION STATUS ===
    extracted_data = models.BooleanField(
        default=False,
        verbose_name="Extracted Data",
        help_text="Whether invoice data has been extracted from this GRN item"
    )

    # Upload metadata
    upload_batch_id = models.CharField(
        max_length=100,
        verbose_name="Upload Batch ID",
        db_index=True,
        help_text="Unique identifier for the upload session"
    )

    uploaded_filename = models.CharField(
        max_length=255,
        verbose_name="Uploaded Filename",
        help_text="Original filename of the uploaded file"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )

    class Meta:
        db_table = 'item_wise_grn'
        verbose_name = "Item-wise GRN Record"
        verbose_name_plural = "Item-wise GRN Records"
        ordering = ['s_no', 'grn_created_at']
        indexes = [
            models.Index(fields=['grn_no']),
            models.Index(fields=['po_no']),
            models.Index(fields=['sku_code']),
            models.Index(fields=['supplier']),
            models.Index(fields=['upload_batch_id']),
            models.Index(fields=['grn_created_at']),
            models.Index(fields=['supplier_invoice_date']),
            models.Index(fields=['created_at']),
        ]

        # Unique constraint to prevent duplicate entries within same batch
        unique_together = [
            ['grn_no', 'po_no', 'sku_code', 'upload_batch_id']
        ]

    def __str__(self):
        return f"GRN: {self.grn_no or 'N/A'} - Item: {self.item_name or 'N/A'}"

    @property
    def is_complete_data(self):
        """Check if essential data is available"""
        return bool(
            self.grn_no and
            self.item_name and
            self.supplier and
            self.received_qty is not None
        )

    @property
    def net_quantity(self):
        """Calculate net quantity (received - returned)"""
        if self.received_qty is not None and self.returned_qty is not None:
            return self.received_qty - self.returned_qty
        elif self.received_qty is not None:
            return self.received_qty
        return None

    @property
    def item_value(self):
        """Calculate total item value (price * net_quantity)"""
        if self.price is not None and self.net_quantity is not None:
            return self.price * self.net_quantity
        return None


class GrnSummary(models.Model):
    """
    Model to store GRN summary data aggregated from ItemWiseGrn
    This enables header-level reconciliation with invoices
    """

    # === IDENTIFICATION FIELDS ===
    grn_number = models.CharField(
        max_length=200,
        verbose_name="GRN Number",
        db_index=True,
        unique=True,
        help_text="Unique GRN number"
    )

    po_number = models.CharField(
        max_length=200,
        verbose_name="PO Number",
        db_index=True,
        help_text="Purchase Order Number"
    )

    supplier_name = models.CharField(
        max_length=500,
        verbose_name="Supplier Name",
        db_index=True,
        help_text="Supplier/vendor name"
    )

    grn_created_date = models.DateField(
        verbose_name="GRN Created Date",
        null=True,
        blank=True,
        help_text="Date when GRN was created"
    )

    supplier_invoice_date = models.DateField(
        verbose_name="Supplier Invoice Date",
        null=True,
        blank=True,
        help_text="Date of supplier invoice"
    )

    seller_invoice_number = models.CharField(
        max_length=200,
        verbose_name="Seller Invoice Number",
        null=True,
        blank=True,
        help_text="Invoice number from seller"
    )

    # === LOCATION DETAILS ===
    pickup_location = models.CharField(
        max_length=500,
        verbose_name="Pickup Location",
        null=True,
        blank=True,
        help_text="Pickup location name"
    )

    pickup_gstin = models.CharField(
        max_length=15,
        verbose_name="Pickup GSTIN",
        null=True,
        blank=True,
        help_text="GST Identification Number for pickup location"
    )

    pickup_city = models.CharField(
        max_length=255,
        verbose_name="Pickup City",
        null=True,
        blank=True
    )

    pickup_state = models.CharField(
        max_length=255,
        verbose_name="Pickup State",
        null=True,
        blank=True
    )

    delivery_location = models.CharField(
        max_length=500,
        verbose_name="Delivery Location",
        null=True,
        blank=True,
        help_text="Delivery location name"
    )

    delivery_gstin = models.CharField(
        max_length=15,
        verbose_name="Delivery GSTIN",
        null=True,
        blank=True,
        help_text="GST Identification Number for delivery location"
    )

    delivery_city = models.CharField(
        max_length=255,
        verbose_name="Delivery City",
        null=True,
        blank=True
    )

    delivery_state = models.CharField(
        max_length=255,
        verbose_name="Delivery State",
        null=True,
        blank=True
    )

    # === AGGREGATED AMOUNTS (calculated from ItemWiseGrn) ===
    total_items_count = models.IntegerField(
        default=0,
        verbose_name="Total Items Count",
        help_text="Number of line items in this GRN"
    )

    total_received_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.0000'))],
        verbose_name="Total Received Quantity",
        help_text="Sum of all received quantities"
    )

    total_subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total Subtotal",
        help_text="Sum of all subtotals before tax"
    )

    total_cgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total CGST Amount",
        help_text="Sum of all CGST amounts"
    )

    total_sgst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total SGST Amount",
        help_text="Sum of all SGST amounts"
    )

    total_igst_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total IGST Amount",
        help_text="Sum of all IGST amounts"
    )

    total_tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total Tax Amount",
        help_text="Sum of all tax amounts"
    )

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total Amount",
        help_text="Sum of all total amounts including taxes"
    )

    # === METADATA ===
    created_by = models.CharField(
        max_length=255,
        verbose_name="Created By",
        null=True,
        blank=True,
        help_text="Person who created the GRN"
    )

    concerned_person = models.CharField(
        max_length=255,
        verbose_name="Concerned Person",
        null=True,
        blank=True,
        help_text="Person responsible for the transaction"
    )

    upload_batch_id = models.CharField(
        max_length=100,
        verbose_name="Upload Batch ID",
        db_index=True,
        help_text="Batch ID from ItemWiseGrn upload"
    )

    # === PROCESSING FLAGS ===
    is_reconciled = models.BooleanField(
        default=False,
        verbose_name="Is Reconciled",
        help_text="Whether this GRN has been reconciled with invoices"
    )

    reconciliation_status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('matched', 'Matched'),
            ('variance', 'Variance Found'),
            ('no_invoice', 'No Invoice Found'),
        ],
        default='pending',
        verbose_name="Reconciliation Status"
    )

    # === TIMESTAMPS ===
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )

    last_aggregated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Aggregated At",
        help_text="When the aggregation was last calculated"
    )

    class Meta:
        db_table = 'grn_summary'
        verbose_name = "GRN Summary"
        verbose_name_plural = "GRN Summaries"
        ordering = ['-grn_created_date', 'grn_number']
        indexes = [
            models.Index(fields=['grn_number']),
            models.Index(fields=['po_number']),
            models.Index(fields=['supplier_name']),
            models.Index(fields=['pickup_gstin']),
            models.Index(fields=['seller_invoice_number']),
            models.Index(fields=['grn_created_date']),
            models.Index(fields=['reconciliation_status']),
            models.Index(fields=['upload_batch_id']),
            models.Index(
                fields=['grn_number', 'po_number', 'seller_invoice_number']),
        ]

        unique_together = [
            ['grn_number', 'po_number', 'seller_invoice_number']
        ]

    def __str__(self):
        return f"GRN {self.grn_number} - PO {self.po_number} - {self.supplier_name}"

    @property
    def total_gst_amount(self):
        """Calculate total GST amount"""
        total = Decimal('0.00')
        if self.total_cgst_amount:
            total += self.total_cgst_amount
        if self.total_sgst_amount:
            total += self.total_sgst_amount
        if self.total_igst_amount:
            total += self.total_igst_amount
        return total if total > 0 else None

    @property
    def variance_from_items(self):
        """Check if calculated total matches sum of item totals"""
        if self.total_subtotal and self.total_gst_amount:
            calculated_total = self.total_subtotal + self.total_gst_amount
            if self.total_amount:
                return abs(calculated_total - self.total_amount)
        return None
