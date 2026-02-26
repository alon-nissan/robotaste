"""
HTML sanitization utilities to prevent XSS attacks.

Provides safe alternatives to rendering user-provided content as HTML.
"""

import html
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Escapes all HTML special characters to prevent injection of malicious scripts.
    
    Args:
        text: Text that may contain HTML tags
        
    Returns:
        Escaped text safe for display
        
    Example:
        >>> sanitize_html("<script>alert('xss')</script>")
        "&lt;script&gt;alert('xss')&lt;/script&gt;"
    """
    if text is None:
        return ""
    return html.escape(str(text))


def sanitize_for_display(text: Optional[str], max_length: Optional[int] = None) -> str:
    """
    Sanitize text for safe display in UI.
    
    Args:
        text: Text to sanitize
        max_length: Optional maximum length (truncates if longer)
        
    Returns:
        Sanitized text safe for display
    """
    if text is None:
        return ""
    
    sanitized = sanitize_html(text)
    
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized
