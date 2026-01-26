"""
Tests for security fixes to prevent code injection and XSS.
"""

import pytest
from robotaste.utils.safe_eval import safe_eval_expression
from robotaste.utils.html_sanitizer import sanitize_html, sanitize_for_display


class TestSafeEval:
    """Test safe expression evaluation."""
    
    def test_basic_arithmetic(self):
        """Test basic arithmetic operations."""
        result = safe_eval_expression("2 + 3", {})
        assert result == 5
        
        result = safe_eval_expression("10 - 4", {})
        assert result == 6
        
        result = safe_eval_expression("3 * 4", {})
        assert result == 12
        
        result = safe_eval_expression("15 / 3", {})
        assert result == 5
    
    def test_with_variables(self):
        """Test expressions with variables."""
        variables = {"x": 10, "y": 5}
        result = safe_eval_expression("x + y", variables)
        assert result == 15
        
        result = safe_eval_expression("x * y", variables)
        assert result == 50
    
    def test_weighted_formula(self):
        """Test weighted formula like in BO target."""
        variables = {"liking": 7, "healthiness_perception": 5}
        result = safe_eval_expression("0.7 * liking + 0.3 * healthiness_perception", variables)
        expected = 0.7 * 7 + 0.3 * 5
        assert abs(result - expected) < 0.001
    
    def test_prevents_code_injection(self):
        """Test that code injection is prevented."""
        # These should all raise ValueError
        with pytest.raises(ValueError):
            safe_eval_expression("__import__('os').system('ls')", {})
        
        with pytest.raises(ValueError):
            safe_eval_expression("exec('print(123)')", {})
        
        with pytest.raises(ValueError):
            safe_eval_expression("eval('1+1')", {})
    
    def test_prevents_function_calls(self):
        """Test that function calls are blocked."""
        with pytest.raises(ValueError):
            safe_eval_expression("print(123)", {})
        
        with pytest.raises(ValueError):
            safe_eval_expression("len([1,2,3])", {})
    
    def test_missing_variable(self):
        """Test error handling for missing variables."""
        with pytest.raises(ValueError, match="not found"):
            safe_eval_expression("x + y", {"x": 5})
    
    def test_invalid_syntax(self):
        """Test error handling for invalid syntax."""
        with pytest.raises(ValueError):
            safe_eval_expression("2 +* 3", {})


class TestHTMLSanitizer:
    """Test HTML sanitization."""
    
    def test_sanitize_script_tags(self):
        """Test that script tags are escaped."""
        result = sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
    
    def test_sanitize_event_handlers(self):
        """Test that event handlers are escaped."""
        result = sanitize_html("<img src=x onerror='alert(1)'>")
        # The quotes should be escaped, preventing execution
        assert "onerror='alert" not in result
        assert "&#x27;" in result or "&quot;" in result  # Quotes are escaped
        assert "&lt;img" in result
    
    def test_sanitize_special_chars(self):
        """Test that special HTML characters are escaped."""
        result = sanitize_html("<>&\"'")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
    
    def test_sanitize_none(self):
        """Test handling of None input."""
        result = sanitize_html(None)
        assert result == ""
    
    def test_sanitize_normal_text(self):
        """Test that normal text passes through (but escaped)."""
        result = sanitize_html("Hello World")
        assert "Hello World" in result
    
    def test_sanitize_for_display_with_length(self):
        """Test text truncation."""
        long_text = "a" * 100
        result = sanitize_for_display(long_text, max_length=10)
        assert len(result) <= 13  # 10 + "..."
        assert "..." in result
    
    def test_sanitize_for_display_none(self):
        """Test handling of None."""
        result = sanitize_for_display(None)
        assert result == ""
