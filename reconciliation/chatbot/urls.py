from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Main chatbot query endpoint
    path('query/', views.ChatbotQueryAPIView.as_view(), name='chatbot_query'),
    
    # Conversation history
    path('history/<str:session_id>/', views.ChatbotHistoryAPIView.as_view(), name='chatbot_history'),
    
    
    # Initialize/refresh embeddings
    path('initialize/', views.ChatbotInitializeAPIView.as_view(), name='chatbot_initialize'),
    
]