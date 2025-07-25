import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .services import get_chatbot_service
from .schema_embedder import get_schema_embedder

logger = logging.getLogger(__name__)


class ChatbotQueryAPIView(APIView):
    """
    Main chatbot API endpoint for processing user questions
    
    POST /api/v1/chatbot/query/
    
    Request Body:
    {
        "question": "How many invoices were processed last week?",
        "session_id": "optional-session-id"
    }
    
    Response:
    {
        "success": true,
        "response": "Natural language response...",
        "session_id": "session-uuid",
        "conversation_id": "conversation-uuid",
        "metadata": {
            "matched_tables": ["invoice_data"],
            "similarity_scores": [0.85],
            "result_count": 42,
            "processing_time_ms": 1250,
            "sql_query": "SELECT COUNT(*) FROM invoice_data WHERE..."
        }
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            # Handle both JSON and form data
            if hasattr(request, 'data') and request.data:
                # DRF parsed data
                question = request.data.get('question', '').strip()
                session_id = request.data.get('session_id')
            else:
                # Fallback to manual JSON parsing
                import json
                try:
                    body = json.loads(request.body.decode('utf-8'))
                    question = body.get('question', '').strip()
                    session_id = body.get('session_id')
                except json.JSONDecodeError:
                    return Response({
                        'success': False,
                        'error': 'Invalid JSON in request body'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate required fields
            if not question:
                return Response({
                    'success': False,
                    'error': 'Question is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate question length
            if len(question) > 500:
                return Response({
                    'success': False,
                    'error': 'Question is too long. Please keep it under 500 characters.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process the question
            logger.info(f"Received chatbot query: {question[:100]}...")
            
            chatbot_service = get_chatbot_service()
            result = chatbot_service.process_question(question, session_id)
            
            # Return response
            if result['success']:
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in ChatbotQueryAPIView: {str(e)}")
            return Response({
                'success': False,
                'error': 'Internal server error occurred',
                'message': 'Please try again or contact support if the issue persists'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatbotHistoryAPIView(APIView):
    """
    Get conversation history for a session
    
    GET /api/v1/chatbot/history/{session_id}/?limit=10
    """
    permission_classes = [AllowAny]
    
    def get(self, request, session_id):
        try:
            # Get limit parameter
            limit = int(request.query_params.get('limit', 10))
            if limit > 50:
                limit = 50  # Maximum limit
            elif limit < 1:
                limit = 10
            
            # Get conversation history
            chatbot_service = get_chatbot_service()
            history = chatbot_service.get_conversation_history(session_id, limit)
            
            return Response({
                'success': True,
                'session_id': session_id,
                'conversation_count': len(history),
                'conversations': history
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({
                'success': False,
                'error': 'Invalid limit parameter. Must be a number.'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in ChatbotHistoryAPIView: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve conversation history'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class ChatbotInitializeAPIView(APIView):
    """
    Initialize or refresh schema embeddings
    
    POST /api/v1/chatbot/initialize/
    
    This endpoint should be called:
    1. After first installation
    2. When table schemas change
    3. To refresh embeddings
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            logger.info("Starting chatbot schema initialization...")
            
            schema_embedder = get_schema_embedder()
            schema_embedder.initialize_schemas()
            
            # Get count of initialized schemas
            from .models import TableSchema
            schema_count = TableSchema.objects.count()
            
            logger.info(f"Chatbot initialization completed. {schema_count} schemas processed.")
            
            return Response({
                'success': True,
                'message': f'Chatbot initialized successfully with {schema_count} table schemas',
                'schemas_processed': schema_count
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in ChatbotInitializeAPIView: {str(e)}")
            return Response({
                'success': False,
                'error': f'Failed to initialize chatbot: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


