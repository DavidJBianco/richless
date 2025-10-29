# mdless - Terminal Markdown Paginator

A modern command-line utility that brings rich Markdown rendering to your terminal.

## Features

- **Syntax Highlighting**: Beautiful code blocks with syntax highlighting
- **Rich Formatting**: Headers, lists, links, and more
- **Less Integration**: Uses the familiar `less` pager for navigation
- **Auto-Detection**: Automatically renders `.md` and `.MD` files

## Installation

```bash
pip install mdless
```

## Usage

View a Markdown file:

```bash
mdless README.md
```

Force Markdown rendering on any file:

```bash
mdless --md document.txt
```

Pass options to less:

```bash
mdless -N README.md  # Show line numbers
```

## Code Example

Here's a simple Python function:

```python
def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"Hello, {name}!"

# Usage
print(greet("World"))
```

## Lists

### Unordered List
- First item
- Second item
  - Nested item
  - Another nested item
- Third item

### Ordered List
1. Initialize project
2. Write code
3. Test thoroughly
4. Deploy

## Quotes

> The best way to predict the future is to invent it.
>
> — Alan Kay

## Links and Emphasis

Visit the [project repository](https://github.com/example/mdless) for more information.

You can use *italic text*, **bold text**, or even ***bold italic text*** for emphasis.

## Tables

| Feature | Status | Notes |
|---------|--------|-------|
| Markdown Rendering | ✓ | Rich library |
| Less Integration | ✓ | Seamless |
| Syntax Highlighting | ✓ | Pygments |
| Cross-platform | ✓ | macOS & Linux |

---

**Enjoy beautiful Markdown in your terminal!**
