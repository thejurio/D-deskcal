# error_messages.py
"""
User-friendly error messages with recovery suggestions for the calendar application.
Provides consistent, actionable error communication across the application.
"""

class ErrorMessages:
    """Centralized error message definitions with user-friendly language and recovery suggestions."""
    
    # Network and Connectivity Errors
    NETWORK_ERROR = {
        'title': 'Network Connection Error',
        'message': 'Unable to connect to the internet. Please check your connection and try again.',
        'suggestions': [
            'Check your internet connection',
            'Verify firewall settings',
            'Try again in a few minutes'
        ],
        'code': 'NETWORK_001'
    }
    
    CONNECTION_TIMEOUT = {
        'title': 'Connection Timeout',
        'message': 'The server is taking too long to respond.',
        'suggestions': [
            'Check your internet speed',
            'Try again later',
            'Contact support if problem persists'
        ],
        'code': 'NETWORK_002'
    }
    
    SERVER_ERROR = {
        'title': 'Server Error',
        'message': 'The server encountered an error while processing your request.',
        'suggestions': [
            'Try again in a few minutes',
            'Check service status',
            'Contact support if problem persists'
        ],
        'code': 'NETWORK_003'
    }
    
    # File System Errors
    PERMISSION_ERROR = {
        'title': 'Permission Denied',
        'message': 'The application does not have permission to access required files.',
        'suggestions': [
            'Run the application as administrator',
            'Check file and folder permissions',
            'Ensure the application folder is not read-only'
        ],
        'code': 'FILE_001'
    }
    
    FILE_NOT_FOUND = {
        'title': 'File Not Found',
        'message': 'A required file could not be found.',
        'suggestions': [
            'Restart the application',
            'Reinstall the application if problem persists',
            'Check if antivirus software is blocking files'
        ],
        'code': 'FILE_002'
    }
    
    DISK_SPACE_ERROR = {
        'title': 'Insufficient Disk Space',
        'message': 'There is not enough space on your disk to complete this operation.',
        'suggestions': [
            'Free up disk space',
            'Move large files to another drive',
            'Empty the recycle bin'
        ],
        'code': 'FILE_003'
    }
    
    # Database Errors
    DATABASE_ERROR = {
        'title': 'Database Error',
        'message': 'An error occurred while accessing the calendar database.',
        'suggestions': [
            'Restart the application',
            'Check if database file is corrupted',
            'Contact support for data recovery'
        ],
        'code': 'DB_001'
    }
    
    DATA_CORRUPTION = {
        'title': 'Data File Corrupted',
        'message': 'A data file appears to be corrupted and will be reset to default values.',
        'suggestions': [
            'The application will continue with default settings',
            'Your calendar events should not be affected',
            'Reconfigure your preferences as needed'
        ],
        'code': 'DB_002'
    }
    
    # Authentication Errors  
    AUTH_TOKEN_EXPIRED = {
        'title': 'Authentication Expired',
        'message': 'Your Google Calendar authentication has expired.',
        'suggestions': [
            'Click "Login" to reauthenticate',
            'Check your Google account status',
            'Ensure you have internet connectivity'
        ],
        'code': 'AUTH_001'
    }
    
    AUTH_TOKEN_INVALID = {
        'title': 'Authentication Error',
        'message': 'Your authentication credentials are invalid or corrupted.',
        'suggestions': [
            'Click "Logout" and log in again',
            'Check your Google account permissions',
            'Clear browser cookies if using web authentication'
        ],
        'code': 'AUTH_002'
    }
    
    GOOGLE_API_ERROR = {
        'title': 'Google Calendar API Error',
        'message': 'Unable to communicate with Google Calendar services.',
        'suggestions': [
            'Check your internet connection',
            'Verify Google Calendar service status',
            'Try logging out and logging back in'
        ],
        'code': 'AUTH_003'
    }
    
    # Calendar Sync Errors
    SYNC_ERROR = {
        'title': 'Calendar Sync Error',
        'message': 'Unable to synchronize calendar data with remote services.',
        'suggestions': [
            'Check your internet connection',
            'Verify your account permissions',
            'Try manual sync in a few minutes'
        ],
        'code': 'SYNC_001'
    }
    
    EVENT_CONFLICT = {
        'title': 'Event Conflict',
        'message': 'This event conflicts with existing calendar data.',
        'suggestions': [
            'Check for duplicate events',
            'Verify event times and dates',
            'Try refreshing calendar data'
        ],
        'code': 'SYNC_002'
    }
    
    # Application Errors
    MEMORY_ERROR = {
        'title': 'Insufficient Memory',
        'message': 'The application is running low on available memory.',
        'suggestions': [
            'Close other applications to free memory',
            'Restart the calendar application',
            'Consider upgrading system memory'
        ],
        'code': 'APP_001'
    }
    
    UNEXPECTED_ERROR = {
        'title': 'Unexpected Error',
        'message': 'An unexpected error has occurred.',
        'suggestions': [
            'Try the operation again',
            'Restart the application if problem persists',
            'Report this issue to support with error details'
        ],
        'code': 'APP_002'
    }
    
    # Configuration Errors
    SETTINGS_ERROR = {
        'title': 'Settings Error',
        'message': 'Unable to save or load application settings.',
        'suggestions': [
            'Check file permissions in application folder',
            'Run application as administrator',
            'Settings will use default values'
        ],
        'code': 'CONFIG_001'
    }
    
    INVALID_CONFIGURATION = {
        'title': 'Invalid Configuration',
        'message': 'The application configuration contains invalid data.',
        'suggestions': [
            'Configuration will be reset to defaults',
            'Reconfigure your preferences',
            'Check for invalid date/time settings'
        ],
        'code': 'CONFIG_002'
    }
    
    @staticmethod
    def get_message(error_type):
        """
        Get error message details by error type.
        
        Args:
            error_type (str): The error type constant name
            
        Returns:
            dict: Error message details with title, message, suggestions, and code
        """
        return getattr(ErrorMessages, error_type, ErrorMessages.UNEXPECTED_ERROR)
    
    @staticmethod
    def format_suggestions(suggestions):
        """
        Format suggestion list for display.
        
        Args:
            suggestions (list): List of suggestion strings
            
        Returns:
            str: Formatted suggestions string
        """
        if not suggestions:
            return ""
        
        if len(suggestions) == 1:
            return f"Suggestion: {suggestions[0]}"
        
        formatted = "Suggestions:\n"
        for i, suggestion in enumerate(suggestions, 1):
            formatted += f"{i}. {suggestion}\n"
        
        return formatted.strip()


class CalendarError(Exception):
    """Base exception class for calendar-specific errors."""
    
    def __init__(self, message, error_code=None, suggestions=None):
        super().__init__(message)
        self.error_code = error_code
        self.suggestions = suggestions or []


class NetworkError(CalendarError):
    """Exception for network-related errors."""
    pass


class DatabaseError(CalendarError):
    """Exception for database-related errors."""
    pass


class AuthenticationError(CalendarError):
    """Exception for authentication-related errors."""
    pass


class FileOperationError(CalendarError):
    """Exception for file operation errors."""
    pass


class SettingsError(CalendarError):
    """Exception for settings and configuration errors."""
    pass


class SyncError(CalendarError):
    """Exception for calendar synchronization errors."""
    pass