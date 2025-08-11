import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .services import get_chatbot_service

logger = logging.getLogger(__name__)

class ChatbotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Don't generate session_id here - let services.py handle it
        self.session_id = None
        await self.accept()
        
        # Send welcome message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to chatbot'
        }))

    async def disconnect(self, close_code):
        logger.info(f"Chatbot WebSocket disconnected: {self.session_id}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'chat_message')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'get_history':
                await self.handle_get_history(data)
            else:
                await self.send_error("Unknown message type")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error in WebSocket receive: {str(e)}")
            await self.send_error("Internal server error")

    async def handle_chat_message(self, data):
        question = data.get('question', '').strip()
        
        if not question:
            await self.send_error("Question is required")
            return

        # Send typing indicator
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'message': 'Processing your question...'
        }))

        try:
            # Pass self.session_id (None for first call) - services.py will generate UUID
            result = await self.process_chatbot_question(question, self.session_id)
            
            # Store the session_id returned by services.py for future calls
            self.session_id = result['session_id']
            
            # Send response
            await self.send(text_data=json.dumps({
                'type': 'chat_response',
                'success': result['success'],
                'response': result['response'],
                'session_id': result['session_id'],
                'conversation_id': result.get('conversation_id'),
                'metadata': result.get('metadata', {}),
                'timestamp': self.get_current_timestamp()
            }))
            
        except Exception as e:
            logger.error(f"Error processing chatbot question: {str(e)}")
            await self.send_error("Failed to process your question")

    async def handle_get_history(self, data):
        if not self.session_id:
            await self.send_error("No conversation history yet")
            return
            
        try:
            limit = data.get('limit', 10)
            history = await self.get_conversation_history(self.session_id, limit)
            
            await self.send(text_data=json.dumps({
                'type': 'history_response',
                'success': True,
                'history': history,
                'session_id': self.session_id
            }))
            
        except Exception as e:
            logger.error(f"Error getting history: {str(e)}")
            await self.send_error("Failed to get conversation history")

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'success': False,
            'message': message,
            'timestamp': self.get_current_timestamp()
        }))

    @database_sync_to_async
    def process_chatbot_question(self, question, session_id):
        chatbot_service = get_chatbot_service()
        return chatbot_service.process_question(question, session_id)

    @database_sync_to_async
    def get_conversation_history(self, session_id, limit):
        chatbot_service = get_chatbot_service()
        return chatbot_service.get_conversation_history(session_id, limit)

    def get_current_timestamp(self):
        from datetime import datetime
        return datetime.now().isoformat()