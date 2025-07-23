# reconciliation/chatbot/models.py
from django.db import models
from pgvector.django import VectorField
import uuid

class TableSchema(models.Model):
    """Store table schemas with their embeddings for semantic search"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    table_name = models.CharField(max_length=100, unique=True)
    schema_description = models.TextField(help_text="Human-readable description of the table")
    columns_info = models.JSONField(help_text="Detailed column information")
    sample_questions = models.JSONField(help_text="Sample questions this table can answer")
    embedding = VectorField(dimensions=384, help_text="Vector embedding of the schema description")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chatbot_table_schema'
        verbose_name = "Table Schema"
        verbose_name_plural = "Table Schemas"
        indexes = [
            models.Index(fields=['table_name']),
            # Vector similarity search index will be created separately
        ]
    
    def __str__(self):
        return f"Schema: {self.table_name}"


class ChatConversation(models.Model):
    """Store chat conversations for context and history"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, db_index=True)
    user_question = models.TextField()
    matched_tables = models.JSONField(help_text="Tables matched for this question")
    generated_sql = models.TextField(blank=True, null=True)
    sql_result = models.JSONField(blank=True, null=True)
    natural_response = models.TextField(blank=True, null=True)
    processing_time_ms = models.IntegerField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chatbot_conversation'
        verbose_name = "Chat Conversation"
        verbose_name_plural = "Chat Conversations"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Chat {self.session_id}: {self.user_question[:50]}..."