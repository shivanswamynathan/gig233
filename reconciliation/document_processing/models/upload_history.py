from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class UploadHistory(models.Model):
    """
    Model to track file upload history
    """

    batch_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Batch ID",
        db_index=True
    )

    filename = models.CharField(
        max_length=255,
        verbose_name="Filename"
    )

    file_size = models.BigIntegerField(
        verbose_name="File Size (bytes)"
    )

    total_records = models.IntegerField(
        verbose_name="Total Records Processed",
        validators=[MinValueValidator(0)]
    )

    successful_records = models.IntegerField(
        verbose_name="Successful Records",
        validators=[MinValueValidator(0)]
    )

    failed_records = models.IntegerField(
        verbose_name="Failed Records",
        validators=[MinValueValidator(0)]
    )

    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('partial', 'Partially Completed'),
        ],
        default='processing',
        verbose_name="Processing Status"
    )

    invoice_extracted = models.BooleanField(
        default=False,
        verbose_name="Invoice Extracted",
    )

    error_details = models.TextField(
        blank=True,
        null=True,
        verbose_name="Error Details"
    )

    data_uploaded = models.BooleanField(
        default=False,
        verbose_name="Data Uploaded"
    )

    uploaded_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Uploaded By"
    )

    extracted_invoice_count = models.IntegerField(
        default=0,
        verbose_name="Extracted Invoice Count",
        help_text="Number of invoices extracted for this upload"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )

    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Completed At"
    )

    class Meta:
        db_table = 'upload_history'
        verbose_name = "Upload History"
        verbose_name_plural = "Upload Histories"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.filename} - {self.processing_status}"

    @property
    def success_rate(self):
        """Calculate success rate of upload"""
        if self.total_records > 0:
            return (self.successful_records / self.total_records) * 100
        return 0
