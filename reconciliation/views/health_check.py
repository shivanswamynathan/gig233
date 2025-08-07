# your_app/views/health_check.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "message": "Server is running",
                "timestamp": datetime.now().isoformat()
            },
            status=status.HTTP_200_OK
        )
