# error_handler.py
"""
Centralized error handling system for the calendar application.
Provides consistent error dialogs, logging, and recovery mechanisms.
"""

import logging
import traceback
from typing import Optional, List
from PyQt6.QtWidgets import QMessageBox, QApplication, QPushButton, QTextEdit, QVBoxLayout, QDialog, QLabel
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont

from error_messages import ErrorMessages, CalendarError

logger = logging.getLogger(__name__)


class ErrorDialog(QDialog):
    """Enhanced error dialog with expandable details and recovery suggestions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calendar Application")
        self.setMinimumWidth(400)
        self.resize(500, 300)
        
        # 에러 다이얼로그는 고정된 불투명도 적용 (메인 프로그램의 투명도 설정과 독립적)
        self.setWindowOpacity(0.95)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Error icon and main message
        self.main_label = QLabel()
        self.main_label.setWordWrap(True)
        font = QFont()
        font.setPointSize(10)
        self.main_label.setFont(font)
        layout.addWidget(self.main_label)
        
        # Suggestions text
        self.suggestions_label = QLabel()
        self.suggestions_label.setWordWrap(True)
        self.suggestions_label.setStyleSheet("color: #666; margin-top: 10px;")
        layout.addWidget(self.suggestions_label)
        
        # Expandable details section
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        self.details_text.setReadOnly(True)
        self.details_text.hide()
        layout.addWidget(self.details_text)
        
        # Buttons
        self.show_details_btn = QPushButton("Show Details")
        self.show_details_btn.clicked.connect(self.toggle_details)
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setDefault(True)
        
        # Button layout
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.show_details_btn)
        button_layout.addWidget(self.ok_btn)
        layout.addLayout(button_layout)
        
        self.details_visible = False
    
    def toggle_details(self):
        """Toggle visibility of error details."""
        self.details_visible = not self.details_visible
        
        if self.details_visible:
            self.details_text.show()
            self.show_details_btn.setText("Hide Details")
            self.resize(500, 400)
        else:
            self.details_text.hide()
            self.show_details_btn.setText("Show Details")
            self.resize(500, 300)
    
    def set_error_info(self, title: str, message: str, suggestions: List[str] = None, details: str = None):
        """Set error information for the dialog."""
        self.setWindowTitle(title)
        self.main_label.setText(f"<b>{title}</b><br><br>{message}")
        
        if suggestions:
            suggestions_text = ErrorMessages.format_suggestions(suggestions)
            self.suggestions_label.setText(suggestions_text)
        else:
            self.suggestions_label.hide()
        
        if details:
            self.details_text.setText(details)
            self.show_details_btn.show()
        else:
            self.show_details_btn.hide()


class ErrorHandler(QObject):
    """Centralized error handling system with logging and user notifications."""
    
    error_occurred = pyqtSignal(str, str, list)  # title, message, suggestions
    critical_error = pyqtSignal(str)  # For errors that require app shutdown
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.error_count = 0
        self.last_error_time = 0
        self.error_suppression_timer = QTimer()
        self.error_suppression_timer.setSingleShot(True)
    
    def handle_exception(self, 
                        exception: Exception, 
                        context: str = None,
                        show_dialog: bool = True,
                        user_message: str = None) -> bool:
        """
        Handle an exception with appropriate logging and user notification.
        
        Args:
            exception: The exception that occurred
            context: Additional context about where the error occurred
            show_dialog: Whether to show error dialog to user
            user_message: Custom user-friendly message (optional)
            
        Returns:
            bool: True if error was handled gracefully, False for critical errors
        """
        self.error_count += 1
        
        # Log the exception with full details
        error_details = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'context': context or 'Unknown',
            'stack_trace': traceback.format_exc()
        }
        
        self.logger.error(
            f"Exception in {context}: {type(exception).__name__}: {exception}",
            extra=error_details,
            exc_info=True
        )
        
        # Determine error type and get appropriate message
        error_info = self._classify_exception(exception, user_message)
        
        # Show user dialog if requested and not suppressed
        if show_dialog and not self._is_error_suppressed():
            self._show_error_dialog(
                error_info['title'],
                error_info['message'], 
                error_info['suggestions'],
                error_details['stack_trace']
            )
        
        # Emit signals for other components
        self.error_occurred.emit(
            error_info['title'],
            error_info['message'],
            error_info['suggestions']
        )
        
        # Check if this is a critical error
        if self._is_critical_error(exception):
            self.critical_error.emit(str(exception))
            return False
            
        return True
    
    def _classify_exception(self, exception: Exception, user_message: str = None) -> dict:
        """Classify exception and return appropriate error message info."""
        
        if user_message:
            return {
                'title': 'Error',
                'message': user_message,
                'suggestions': [],
                'code': 'CUSTOM_001'
            }
        
        # Specific exception type mappings
        if isinstance(exception, FileNotFoundError):
            return ErrorMessages.FILE_NOT_FOUND
        elif isinstance(exception, PermissionError):
            return ErrorMessages.PERMISSION_ERROR
        elif isinstance(exception, OSError):
            if "No space left" in str(exception).lower():
                return ErrorMessages.DISK_SPACE_ERROR
            return ErrorMessages.FILE_NOT_FOUND
        elif isinstance(exception, ConnectionError):
            return ErrorMessages.NETWORK_ERROR
        elif isinstance(exception, TimeoutError):
            return ErrorMessages.CONNECTION_TIMEOUT
        elif hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            return ErrorMessages.SERVER_ERROR
        elif isinstance(exception, ValueError):
            return ErrorMessages.INVALID_CONFIGURATION
        elif isinstance(exception, MemoryError):
            return ErrorMessages.MEMORY_ERROR
        elif isinstance(exception, CalendarError):
            # Custom calendar exceptions have their own messages
            return {
                'title': type(exception).__name__.replace('Error', ' Error'),
                'message': str(exception),
                'suggestions': getattr(exception, 'suggestions', []),
                'code': getattr(exception, 'error_code', 'CALENDAR_001')
            }
        else:
            return ErrorMessages.UNEXPECTED_ERROR
    
    def _is_critical_error(self, exception: Exception) -> bool:
        """Determine if an error is critical and requires app shutdown."""
        critical_types = [
            MemoryError,
            SystemError,
            KeyboardInterrupt,
            SystemExit
        ]
        
        return any(isinstance(exception, error_type) for error_type in critical_types)
    
    def _is_error_suppressed(self) -> bool:
        """Check if error dialogs should be suppressed due to frequency."""
        import time
        current_time = time.time()
        
        # Suppress if more than 5 errors in last 60 seconds
        if self.error_count > 5 and (current_time - self.last_error_time) < 60:
            return True
        
        self.last_error_time = current_time
        return False
    
    def _show_error_dialog(self, title: str, message: str, suggestions: List[str], details: str):
        """Show error dialog to user."""
        try:
            # Ensure we have a QApplication instance
            app = QApplication.instance()
            if not app:
                return
                
            dialog = ErrorDialog()
            dialog.set_error_info(title, message, suggestions, details)
            dialog.exec()
            
        except Exception as dialog_error:
            # Fallback if custom dialog fails
            self.logger.error(f"Error showing error dialog: {dialog_error}")
            QMessageBox.critical(None, title, message)
    
    def handle_file_error(self, file_path: str, operation: str, exception: Exception):
        """Handle file operation errors with specific context."""
        context = f"File {operation} operation on {file_path}"
        
        if isinstance(exception, FileNotFoundError):
            user_message = f"The file '{file_path}' could not be found."
        elif isinstance(exception, PermissionError):
            user_message = f"Permission denied accessing '{file_path}'. Try running as administrator."
        else:
            user_message = f"Error during {operation} operation on '{file_path}'."
        
        self.handle_exception(exception, context, user_message=user_message)
    
    def handle_network_error(self, url: str, operation: str, exception: Exception):
        """Handle network operation errors with specific context."""
        context = f"Network {operation} operation to {url}"
        
        if isinstance(exception, ConnectionError):
            user_message = "Cannot connect to the server. Please check your internet connection."
        elif isinstance(exception, TimeoutError):
            user_message = "The server is taking too long to respond. Please try again later."
        else:
            user_message = f"Network error during {operation}."
        
        self.handle_exception(exception, context, user_message=user_message)
    
    def handle_database_error(self, operation: str, exception: Exception):
        """Handle database operation errors with specific context."""
        context = f"Database {operation} operation"
        user_message = "A database error occurred. Your data should be safe, but some operations may be unavailable."
        
        self.handle_exception(exception, context, user_message=user_message)
    
    def reset_error_count(self):
        """Reset error count (useful for testing or after app restart)."""
        self.error_count = 0
        self.last_error_time = 0


# Global error handler instance
_global_error_handler = None


def get_error_handler() -> ErrorHandler:
    """Get or create the global error handler instance."""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def handle_exception(exception: Exception, 
                   context: str = None,
                   show_dialog: bool = True,
                   user_message: str = None) -> bool:
    """
    Convenience function to handle exceptions using the global error handler.
    
    Args:
        exception: The exception that occurred
        context: Additional context about where the error occurred
        show_dialog: Whether to show error dialog to user
        user_message: Custom user-friendly message (optional)
        
    Returns:
        bool: True if error was handled gracefully, False for critical errors
    """
    handler = get_error_handler()
    return handler.handle_exception(exception, context, show_dialog, user_message)