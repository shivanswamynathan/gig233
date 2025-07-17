from django.http import JsonResponse
from typing import Dict, Any, List


class PaginationHelper:
    """
    Utility class for handling pagination in API views
    """
    
    def __init__(self, request, default_limit: int = 10, max_limit: int = 10):
        """
        Initialize pagination helper
        
        Args:
            request: Django request object
            default_limit: Default number of records per page
            max_limit: Maximum allowed records per page
        """
        self.request = request
        self.default_limit = default_limit
        self.max_limit = max_limit
        
        # Parse and validate pagination parameters
        self.page, self.limit = self._parse_pagination_params()
        self.offset = (self.page - 1) * self.limit
    
    def _parse_pagination_params(self) -> tuple:
        """
        Parse and validate page and limit parameters from request
        
        Returns:
            tuple: (page, limit)
        """
        try:
            page = int(self.request.GET.get('page', 1))
            limit = int(self.request.GET.get('limit', self.default_limit))
            
            # Validate page number
            if page < 1:
                page = 1
                
            # Validate limit
            if limit > self.max_limit:
                limit = self.max_limit
            elif limit < 1:
                limit = self.default_limit
                
            return page, limit
            
        except ValueError:
            # Return defaults if parsing fails
            return 1, self.default_limit
    
    def validate_params(self) -> Dict[str, Any]:
        """
        Validate pagination parameters and return error response if invalid
        
        Returns:
            dict: Error response or None if valid
        """
        try:
            # Try to parse parameters again to catch any errors
            page = int(self.request.GET.get('page', 1))
            limit = int(self.request.GET.get('limit', self.default_limit))
            
            if page < 1:
                return {
                    'success': False,
                    'error': 'Page number must be greater than 0'
                }
            
            if limit < 1:
                return {
                    'success': False,
                    'error': 'Limit must be greater than 0'
                }
                
            if limit > self.max_limit:
                return {
                    'success': False,
                    'error': f'Limit cannot exceed {self.max_limit} records per page'
                }
            
            return None  # No errors
            
        except ValueError:
            return {
                'success': False,
                'error': 'Invalid page or limit values. Must be integers.'
            }
    
    def paginate_queryset(self, queryset):
        """
        Apply pagination to a Django queryset
        
        Args:
            queryset: Django queryset to paginate
            
        Returns:
            tuple: (paginated_queryset, total_count)
        """
        total_count = queryset.count()
        paginated_queryset = queryset[self.offset:self.offset + self.limit]
        
        return paginated_queryset, total_count
    
    def get_pagination_info(self, total_count: int) -> Dict[str, Any]:
        """
        Generate pagination information for API response
        
        Args:
            total_count: Total number of records
            
        Returns:
            dict: Pagination information
        """
        total_pages = (total_count + self.limit - 1) // self.limit
        has_next = self.page < total_pages
        has_previous = self.page > 1
        
        return {
            'current_page': self.page,
            'total_pages': total_pages,
            'total_count': total_count,
            'limit': self.limit,
            'has_next': has_next,
            'has_previous': has_previous,
            'records_on_page': min(self.limit, total_count - self.offset) if total_count > self.offset else 0
        }
    
    def create_paginated_response(self, data: List[Dict], total_count: int, 
                                message: str = None) -> JsonResponse:
        """
        Create a standardized paginated JSON response
        
        Args:
            data: List of data records
            total_count: Total number of records
            message: Optional success message
            
        Returns:
            JsonResponse: Standardized paginated response
        """
        pagination_info = self.get_pagination_info(total_count)
        
        # Update records_on_page with actual data length
        pagination_info['records_on_page'] = len(data)
        
        response_data = {
            'success': True,
            'data': data,
            'pagination': pagination_info
        }
        
        if message:
            response_data['message'] = message
        else:
            response_data['message'] = f'Retrieved {len(data)} records from page {self.page}'
        
        return JsonResponse(response_data, status=200)


def create_error_response(error_message: str, status_code: int = 400) -> JsonResponse:
    """
    Create a standardized error response
    
    Args:
        error_message: Error message to return
        status_code: HTTP status code
        
    Returns:
        JsonResponse: Standardized error response
    """
    return JsonResponse({
        'success': False,
        'error': error_message,
        'message': 'Request failed'
    }, status=status_code)


def create_server_error_response(error_message: str) -> JsonResponse:
    """
    Create a standardized server error response
    
    Args:
        error_message: Error message to return
        
    Returns:
        JsonResponse: Standardized server error response
    """
    return JsonResponse({
        'success': False,
        'error': 'Internal Server Error',
        'message': f'Server error: {error_message}'
    }, status=500)