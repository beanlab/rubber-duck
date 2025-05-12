from agents import function_tool


@function_tool
def add_math(a, b):
    """
    A simple math function that adds two numbers.
    """
    return a + b

