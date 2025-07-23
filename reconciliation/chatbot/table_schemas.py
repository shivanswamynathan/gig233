# reconciliation/chatbot/table_schemas.py
"""
Table schema definitions for the chatbot semantic search system.
This file contains all table schemas that the chatbot can query.
"""

TABLE_SCHEMAS = [
    {
        "table_name": "item_wise_grn",
        "schema_description": """
        Item-wise Goods Receipt Note (GRN) data containing detailed information about received items from suppliers.
        This table stores individual line items for each GRN including quantities, prices, tax details, and supplier information.
        Used for tracking received goods, supplier performance, and reconciliation with invoices.
        """,
        "columns_info": {
            "id": "Primary key",
            "s_no": "Serial number",
            "type": "Transaction type (e.g., InterStock)",
            "sku_code": "Stock Keeping Unit code",
            "category": "Product category",
            "sub_category": "Product sub-category", 
            "item_name": "Name/description of the item",
            "unit": "Unit of measurement (piece, kg, etc.)",
            "grn_no": "Goods Receipt Note Number",
            "hsn_no": "Harmonized System of Nomenclature code",
            "po_no": "Purchase Order Number",
            "remarks": "Additional remarks or notes",
            "created_by": "Person who created the GRN",
            "grn_created_at": "Date when GRN was created",
            "seller_invoice_no": "Invoice number from seller",
            "supplier_invoice_date": "Date of supplier invoice",
            "supplier": "Supplier/vendor name",
            "concerned_person": "Person responsible for the transaction",
            "pickup_location": "Pickup location name",
            "pickup_gstin": "GST Identification Number for pickup location",
            "pickup_city": "Pickup city",
            "pickup_state": "Pickup state", 
            "delivery_location": "Delivery location name",
            "delivery_gstin": "GST Identification Number for delivery location",
            "delivery_city": "Delivery city",
            "delivery_state": "Delivery state",
            "price": "Unit price of the item",
            "received_qty": "Quantity received",
            "returned_qty": "Quantity returned",
            "discount": "Discount amount",
            "tax": "Tax rate percentage",
            "sgst_tax": "State GST rate percentage",
            "sgst_tax_amount": "State GST amount",
            "cgst_tax": "Central GST rate percentage", 
            "cgst_tax_amount": "Central GST amount",
            "igst_tax": "Integrated GST rate percentage",
            "igst_tax_amount": "Integrated GST amount",
            "cess": "Cess amount",
            "subtotal": "Subtotal before taxes",
            "tax_amount": "Total tax amount",
            "total": "Total amount including all taxes and charges",
            "upload_batch_id": "Batch ID for the upload session",
            "extracted_data": "Whether invoice data has been extracted"
        },
        "sample_questions": [
            "How many items were received for PO number X?",
            "What is the total value of items received from supplier Y?",
            "Show me all GRNs created in the last month",
            "Which items have the highest received quantities?",
            "What are the tax amounts for items in GRN number Z?",
            "Show supplier performance by total received quantities",
            "List all items with unit price above ₹1000",
            "What is the total GST collected per supplier?",
            "Show items received but not yet extracted for invoicing",
            "Which locations receive the most items?",
            "What is the average price per item for supplier ABC?",
            "Show me items with high return quantities",
            "Which HSN codes have the highest tax rates?",
            "List all items delivered to Mumbai",
            "What is the total discount given per supplier?"
        ]
    },
    {
        "table_name": "invoice_data", 
        "schema_description": """
        Invoice data extracted from invoice documents (PDFs, images) containing header-level information.
        This table stores vendor details, invoice numbers, dates, and total amounts for reconciliation with GRN data.
        Each record represents one invoice document that has been processed through OCR/LLM extraction.
        """,
        "columns_info": {
            "id": "Primary key",
            "attachment_number": "Attachment number (1-5)",
            "attachment_url": "Original attachment URL",
            "file_type": "File processing type (pdf_text, pdf_image, image, unknown)",
            "original_file_extension": "Original file extension",
            "vendor_name": "Vendor/supplier company name",
            "vendor_pan": "Vendor PAN number",
            "vendor_gst": "Vendor GST number (15 digits)",
            "invoice_date": "Date of the invoice",
            "invoice_number": "Invoice/bill number",
            "po_number": "Purchase Order Number referenced in invoice",
            "grn_number": "GRN number referenced in invoice",
            "invoice_value_without_gst": "Invoice value before GST",
            "cgst_rate": "Central GST rate percentage",
            "cgst_amount": "Central GST amount",
            "sgst_rate": "State GST rate percentage", 
            "sgst_amount": "State GST amount",
            "igst_rate": "Integrated GST rate percentage",
            "igst_amount": "Integrated GST amount",
            "total_gst_amount": "Total GST amount",
            "invoice_total_post_gst": "Final invoice amount including GST",
            "items_data": "JSON data of line items",
            "processing_status": "Processing status (pending, processing, completed, failed)",
            "error_message": "Error message if processing failed",
            "extracted_at": "When the data was extracted",
            "type": "Invoice type",
            "failure_reason": "Reason for extraction failure",
            "manually_enter": "Manually entered key"
        },
        "sample_questions": [
            "How many invoices were processed successfully?",
            "What is the total invoice amount for vendor X?",
            "Show me all invoices for PO number Y?",
            "Which invoices failed during processing?",
            "What is the average invoice value per vendor?",
            "Show invoices with GST amounts above ₹10,000",
            "List all invoices processed in the last week",
            "Which vendors have the most invoices?",
            "Show invoices with processing errors",
            "What are the total GST collections per month?",
            "Which invoices have the highest CGST amounts?",
            "Show me invoices processed today",
            "What is the total value of invoices from vendor ABC?",
            "List invoices with missing PO numbers",
            "Which file types have the highest success rates?"
        ]
    },
    {
        "table_name": "invoice_item_data",
        "schema_description": """
        Individual line items from invoices containing detailed product/service information.
        This table stores item-level details like descriptions, quantities, rates, HSN codes, and tax breakdowns.
        Used for item-level reconciliation with GRN line items and detailed financial analysis.
        """,
        "columns_info": {
            "id": "Primary key",
            "invoice_data_id": "Reference to parent invoice record",
            "item_description": "Product/service description",
            "hsn_code": "HSN/SAC code for the item",
            "quantity": "Item quantity", 
            "unit_of_measurement": "Unit (PCS, KG, LTR, etc.)",
            "unit_price": "Rate per unit",
            "invoice_value_item_wise": "Item-wise invoice value before tax",
            "cgst_rate": "Central GST rate percentage",
            "cgst_amount": "Central GST amount for this item",
            "sgst_rate": "State GST rate percentage",
            "sgst_amount": "State GST amount for this item", 
            "igst_rate": "Integrated GST rate percentage",
            "igst_amount": "Integrated GST amount for this item",
            "total_tax_amount": "Total tax amount for this item",
            "item_total_amount": "Final amount for this item including tax",
            "po_number": "Purchase Order Number",
            "invoice_number": "Invoice number",
            "vendor_name": "Vendor name",
            "manually_enter": "Manually entered key",
            "item_sequence": "Item sequence number in invoice"
        },
        "sample_questions": [
            "What are the most expensive items per unit?",
            "Show me all items with HSN code X",
            "Which items have the highest tax amounts?",
            "What is the total quantity of product Y ordered?",
            "Show items with unit price above ₹500",
            "List all items from vendor Z", 
            "What are the total tax collections per HSN code?",
            "Show items with quantity greater than 100",
            "Which invoice has the most line items?",
            "What is the average item value per invoice?",
            "Which HSN codes are most frequently used?",
            "Show me items with IGST instead of CGST+SGST",
            "What is the total value of items in KG units?",
            "List items with high tax rates above 18%",
            "Which vendors supply the most variety of items?"
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