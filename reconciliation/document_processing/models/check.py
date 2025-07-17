from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Check(models.Model):
    """
    Model to store user approval actions on reconciliation records
    """

    # Reference fields from reconciliation
    po_number = models.CharField(
        max_length=200,
        verbose_name="PO Number",
        db_index=True
    )

    grn_number = models.CharField(
        max_length=200,
        verbose_name="GRN Number",
        db_index=True
    )

    invoice_number = models.CharField(
        max_length=100,
        verbose_name="Invoice Number",
        db_index=True
    )

    vendor_name = models.CharField(
        max_length=255,
        verbose_name="Vendor Name",
        db_index=True
    )

    invoice_data_id = models.IntegerField(
        verbose_name="Invoice Data ID",
        db_index=True
    )

    # Status and action fields (as mentioned in your requirement)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
        verbose_name="Status",
        db_index=True
    )

    action = models.BooleanField(
        default=False,
        verbose_name="Action",
        help_text="True when user approves, False otherwise"
    )

    # Additional tracking fields
    approved_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Approved By"
    )

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Total Amount",
        help_text="Total invoice amount for reference"
    )

    url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name="Invoice URL",
        help_text="URL to the invoice attachment"
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
        db_table = 'check'
        verbose_name = "Check Record"
        verbose_name_plural = "Check Records"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['grn_number']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['vendor_name']),
            models.Index(fields=['invoice_data_id']),
            models.Index(fields=['status']),
            models.Index(fields=['action']),
        ]

        # Prevent duplicate entries
        unique_together = [
            ['po_number', 'grn_number', 'invoice_number', 'invoice_data_id']
        ]

    def __str__(self):
        return f"Check: PO-{self.po_number} | Status-{self.status} | Action-{self.action}"
