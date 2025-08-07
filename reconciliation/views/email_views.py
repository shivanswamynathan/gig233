# reconciliation/document_processing/views/email_views.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from document_processing.utils.email_service import EmailService

# Set up logger
logger = logging.getLogger(__name__)

class SendInvoiceNotificationView(APIView):
    def post(self, request):
        try:
            to = request.data.get('to')
            subject = request.data.get('subject')
            message = request.data.get('message')

            if not all([to, subject, message]):
                logger.warning("Missing email fields: to=%s, subject=%s", to, subject)
                return Response(
                    {"success": False, "error": "Missing required fields"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            email_service = EmailService()
            success = email_service.send_email(to, subject, message)

            if success:
                logger.info("Email sent to %s with subject '%s'", to, subject)
                return Response(
                    {"success": True, "message": "Email sent successfully."},
                    status=status.HTTP_200_OK
                )
            else:
                logger.error("Email service returned failure for %s", to)
                return Response(
                    {"success": False, "message": "Failed to send email."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error("Failed to send email: %s", str(e), exc_info=True)
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
