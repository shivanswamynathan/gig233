"""
Updated table schema definitions for the chatbot semantic search system.
This file contains reconciliation table schemas that the chatbot can query.
"""

TABLE_SCHEMAS = [
    {
        "table_name": "invoice_grn_reconciliation",
        "schema_description": """
        Invoice-level reconciliation data comparing invoices with GRN (Goods Receipt Note) records.
        This table stores header-level matching results, variance analysis, and approval status between invoices and GRNs.
        Used for analyzing invoice-GRN matching success, identifying mismatches, and tracking approval workflows.
        Contains vendor validation, GST verification, date validation, and amount variance calculations.
        """,
        "columns_info": {
            "id": "Primary key",
            "po_number": "Purchase Order Number used for matching",
            "grn_number": "Goods Receipt Note Number",
            "invoice_number": "Invoice Number from both sources",
            "invoice_data_id": "ID reference to the related invoice record",
            "match_status": "Match status (perfect_match, partial_match, amount_mismatch, vendor_mismatch, date_mismatch, no_grn_found, multiple_grn, no_match)",
            "vendor_match": "Whether vendor names match (boolean)",
            "invoice_vendor": "Vendor name from invoice",
            "grn_vendor": "Vendor name from GRN",
            "gst_match": "Whether GST numbers match (boolean)",
            "invoice_gst": "GST number from invoice",
            "grn_gst": "GST number from GRN",
            "date_valid": "Whether invoice date <= GRN created date (boolean)",
            "invoice_date": "Date from invoice",
            "grn_date": "GRN creation date",
            "invoice_subtotal": "Invoice value without GST",
            "invoice_cgst": "Central GST amount from invoice",
            "invoice_sgst": "State GST amount from invoice", 
            "invoice_igst": "Integrated GST amount from invoice",
            "invoice_total": "Total invoice amount including GST",
            "grn_subtotal": "Sum of all GRN line item subtotals",
            "grn_cgst": "Total CGST from GRN line items",
            "grn_sgst": "Total SGST from GRN line items",
            "grn_igst": "Total IGST from GRN line items",
            "grn_total": "Sum of all GRN line item totals",
            "subtotal_variance": "Invoice Subtotal - GRN Subtotal",
            "cgst_variance": "CGST amount difference",
            "sgst_variance": "SGST amount difference",
            "igst_variance": "IGST amount difference",
            "total_variance": "Invoice Total - GRN Total",
            "total_grn_line_items": "Number of GRN line items matched",
            "matching_method": "Method used for matching (exact_match, po_grn_match, po_only_match, manual_match)",
            "reconciliation_notes": "Additional notes about the reconciliation",
            "tolerance_applied": "Tolerance percentage applied for matching",
            "approval_status": "Approval status (pending, approved, rejected, escalated)",
            "approved_by": "Person who approved the reconciliation",
            "approved_at": "When the reconciliation was approved",
            "status": "User approval status - True when user approves",
            "reconciled_at": "When the reconciliation was performed",
            "reconciled_by": "Person who performed the reconciliation",
            "updated_at": "Last update timestamp",
            "is_auto_matched": "Whether this was automatically matched",
            "requires_review": "Whether this reconciliation needs manual review",
            "is_exception": "Whether this is flagged as an exception"
        },
        "sample_questions": [
            "How many invoices have perfect matches with GRNs?",
            "Show me all invoices with amount mismatches above 5%",
            "Which vendors have the most reconciliation exceptions?",
            "What are the common reasons for GRN-invoice mismatches?",
            "Show me all pending approvals for reconciliation",
            "Which PO numbers have multiple GRN records causing issues?",
            "What is the total variance amount across all reconciliations?",
            "Show invoices where vendor names don't match with GRN",
            "Which reconciliations require manual review?",
            "What is the success rate of automatic matching?",
            "Show me reconciliations with GST number mismatches",
            "Which invoices have no matching GRN found?",
            "What are the largest amount variances in reconciliation?",
            "Show me all rejected reconciliations and their reasons",
            "Which reconciliations were escalated for approval?",
            "What percentage of invoices are within tolerance limits?",
            "Show me date validation failures in reconciliation",
            "Which PO numbers have the highest variance amounts?",
            "Show reconciliations that were manually overridden",
            "What is the average processing time for reconciliations?"
        ]
    },
    {
        "table_name": "invoice_item_reconciliation", 
        "schema_description": """
        Item-level reconciliation data comparing individual invoice line items with GRN line items.
        This table stores detailed line-by-line matching results, variance analysis, and matching scores.
        Used for item-level reconciliation analysis, identifying quantity/price variances, and HSN code matching.
        Contains detailed matching algorithms scores, tolerance flags, and item-specific variance calculations.
        """,
        "columns_info": {
            "id": "Primary key",
            "invoice_data_id": "ID reference to the parent invoice record",
            "invoice_item_data_id": "ID reference to the invoice line item",
            "grn_item_id": "ID reference to the matched GRN line item (null if no match)",
            "reconciliation_batch_id": "Batch ID for tracking this reconciliation run",
            "match_status": "Item match status (perfect_match, partial_match, amount_mismatch, quantity_mismatch, hsn_mismatch, description_mismatch, no_match)",
            "match_score": "Overall match score (0.0000 to 1.0000)",
            "hsn_match_score": "HSN code matching score",
            "description_match_score": "Item description matching score",
            "amount_match_score": "Amount matching score",
            "quantity_match_score": "Quantity matching score",
            "invoice_item_sequence": "Item sequence in invoice",
            "invoice_item_description": "Invoice item description",
            "invoice_item_hsn": "HSN code from invoice",
            "invoice_item_quantity": "Quantity from invoice",
            "invoice_item_unit": "Unit of measurement from invoice",
            "invoice_item_unit_price": "Unit price from invoice",
            "invoice_item_subtotal": "Invoice item subtotal",
            "invoice_item_cgst_rate": "CGST rate from invoice",
            "invoice_item_cgst_amount": "CGST amount from invoice",
            "invoice_item_sgst_rate": "SGST rate from invoice",
            "invoice_item_sgst_amount": "SGST amount from invoice",
            "invoice_item_igst_rate": "IGST rate from invoice",
            "invoice_item_igst_amount": "IGST amount from invoice",
            "invoice_item_total_tax": "Total tax amount from invoice",
            "invoice_item_total_amount": "Total amount from invoice",
            "grn_item_description": "GRN item description",
            "grn_item_hsn": "HSN code from GRN",
            "grn_item_quantity": "Received quantity from GRN",
            "grn_item_unit": "Unit of measurement from GRN",
            "grn_item_unit_price": "Unit price from GRN",
            "grn_item_subtotal": "GRN item subtotal",
            "grn_item_cgst_rate": "CGST rate from GRN",
            "grn_item_cgst_amount": "CGST amount from GRN",
            "grn_item_sgst_rate": "SGST rate from GRN",
            "grn_item_sgst_amount": "SGST amount from GRN",
            "grn_item_igst_rate": "IGST rate from GRN",
            "grn_item_igst_amount": "IGST amount from GRN",
            "grn_item_total_tax": "Total tax amount from GRN",
            "grn_item_total_amount": "Total amount from GRN",
            "quantity_variance": "Invoice Quantity - GRN Quantity",
            "quantity_variance_percentage": "Quantity variance as percentage",
            "subtotal_variance": "Invoice Subtotal - GRN Subtotal", 
            "subtotal_variance_percentage": "Subtotal variance as percentage",
            "cgst_variance": "CGST amount difference",
            "sgst_variance": "SGST amount difference",
            "igst_variance": "IGST amount difference",
            "total_tax_variance": "Total tax amount difference",
            "total_amount_variance": "Invoice Total - GRN Total",
            "total_amount_variance_percentage": "Total amount variance as percentage",
            "unit_rate_variance": "Invoice Unit Price - GRN Unit Price",
            "is_within_amount_tolerance": "Whether amount variance is within configured tolerance",
            "is_within_quantity_tolerance": "Whether quantity variance is within configured tolerance",
            "tolerance_percentage_applied": "Amount tolerance applied (%)",
            "quantity_tolerance_percentage_applied": "Quantity tolerance applied (%)",
            "hsn_match_weight_applied": "HSN match weight used in scoring",
            "description_match_weight_applied": "Description match weight used in scoring",
            "amount_match_weight_applied": "Amount match weight used in scoring",
            "requires_review": "Whether this item reconciliation needs manual review",
            "is_exception": "Whether this item is flagged as an exception",
            "is_auto_matched": "Whether this was automatically matched",
            "reconciliation_notes": "Additional notes about this item reconciliation",
            "po_number": "Purchase Order Number",
            "invoice_number": "Invoice Number",
            "grn_number": "GRN Number",
            "vendor_name": "Vendor Name",
            "reconciled_at": "When the reconciliation was performed",
            "updated_at": "Last update timestamp"
        },
        "sample_questions": [
            "Which items have the highest quantity variances?",
            "Show me all items with HSN code mismatches",
            "What are the most common reasons for item matching failures?",
            "Which items require manual review due to variances?",
            "Show items where unit prices differ significantly between invoice and GRN",
            "What is the average matching score for automatically matched items?",
            "Which HSN codes have the highest variance rates?",
            "Show me items with perfect description matches but amount mismatches",
            "What percentage of items are within tolerance limits?",
            "Which items have no matching GRN records?",
            "Show items with the largest absolute amount variances",
            "Which vendors have the most item-level exceptions?",
            "What are the top 10 items by total amount variance?",
            "Show items where CGST rates don't match between invoice and GRN",
            "Which reconciliation batches had the lowest success rates?",
            "Show me items with quantity received less than invoiced",
            "What is the distribution of match scores across all items?",
            "Which items have high description match scores but low overall scores?",
            "Show items where tax calculations differ between invoice and GRN",
            "What percentage of items require manual review vs auto-approval?",
            "Show items with unit rate variances above ₹100",
            "Which PO numbers have the most item-level discrepancies?",
            "Show me recent reconciliations that were flagged as exceptions",
            "What are the common patterns in mismatched item descriptions?",
            "Which items have quantity variances above 10%?"
        ]
    }
]


def get_table_schemas():
    """
    Get all table schemas for the chatbot system.
    
    Returns:
        list: List of table schema dictionaries
    """
    return TABLE_SCHEMAS


def get_table_schema_by_name(table_name: str):
    """
    Get a specific table schema by name.
    
    Args:
        table_name (str): Name of the table
        
    Returns:
        dict or None: Table schema dictionary or None if not found
    """
    for schema in TABLE_SCHEMAS:
        if schema['table_name'] == table_name:
            return schema
    return None


def get_all_sample_questions():
    """
    Get all sample questions from all tables.
    
    Returns:
        dict: Dictionary with table names as keys and sample questions as values
    """
    questions = {}
    for schema in TABLE_SCHEMAS:
        questions[schema['table_name']] = schema['sample_questions']
    return questions