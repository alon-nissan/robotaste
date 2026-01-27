"""
Safe expression evaluation utilities to prevent code injection.

Provides a secure alternative to eval() for evaluating mathematical expressions.
"""

import ast
import operator
import logging
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

# Allowed operators for safe evaluation
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval_expression(expression: str, variables: Dict[str, Any]) -> Union[float, int]:
    """
    Safely evaluate a mathematical expression with given variables.
    
    Only allows basic arithmetic operations (+, -, *, /, **) and numerical constants.
    This prevents code injection attacks that could occur with eval().
    
    Args:
        expression: Mathematical expression string (e.g., "0.7 * a + 0.3 * b")
        variables: Dictionary of variable names to their values
        
    Returns:
        Result of the expression evaluation as float or int
        
    Raises:
        ValueError: If expression contains unsafe operations or invalid syntax
        
    Example:
        >>> safe_eval_expression("0.7 * x + 0.3 * y", {"x": 5, "y": 3})
        4.4
    """
    try:
        # Parse the expression into an AST
        tree = ast.parse(expression, mode='eval')
        
        # Evaluate the expression tree safely
        result = _eval_node(tree.body, variables)
        
        return result
    except SyntaxError as e:
        logger.error(f"Invalid expression syntax: {expression} - {e}")
        raise ValueError(f"Invalid expression syntax: {e}")
    except Exception as e:
        logger.error(f"Error evaluating expression '{expression}': {e}")
        raise ValueError(f"Failed to evaluate expression: {e}")


def _eval_node(node: ast.AST, variables: Dict[str, Any]) -> Union[float, int]:
    """
    Recursively evaluate an AST node.
    
    Args:
        node: AST node to evaluate
        variables: Dictionary of variable names to their values
        
    Returns:
        Evaluated result
        
    Raises:
        ValueError: If node contains unsafe operations
    """
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Name):
        # Look up variable value
        if node.id not in variables:
            raise ValueError(f"Variable '{node.id}' not found in provided variables")
        return variables[node.id]
    elif isinstance(node, ast.BinOp):
        # Binary operation (e.g., a + b, a * b)
        if type(node.op) not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        return SAFE_OPERATORS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp):
        # Unary operation (e.g., -x, +x)
        if type(node.op) not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operation: {type(node.op).__name__}")
        operand = _eval_node(node.operand, variables)
        return SAFE_OPERATORS[type(node.op)](operand)
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")
