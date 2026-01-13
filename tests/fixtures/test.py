#!/usr/bin/env python3
"""Test Python file for syntax highlighting."""

def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"

class Example:
    def __init__(self, value: int):
        self.value = value

if __name__ == "__main__":
    print(greet("World"))
