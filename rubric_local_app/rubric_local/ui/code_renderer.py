import re
import tkinter as tk
from typing import Tuple, Optional, List

# Common language keywords for fast offline syntax highlighting
KEYWORDS = {
    # Python
    "def", "class", "return", "import", "from", "as", "if", "elif", "else",
    "for", "while", "try", "except", "finally", "with", "yield", "lambda",
    "pass", "break", "continue", "raise", "assert", "global", "nonlocal",
    "async", "await", "None", "True", "False",
    # JavaScript / TypeScript
    "function", "const", "let", "var", "new", "this", "typeof", "instanceof",
    "switch", "case", "default", "catch", "throw", "export", "interface", "type",
    # SQL
    "select", "from", "where", "insert", "into", "update", "delete", "join",
    "left", "right", "inner", "outer", "group", "by", "order", "having",
    "limit", "create", "table", "alter", "drop", "index", "values",
    # C/C++/Java/C#
    "public", "private", "protected", "static", "void", "int", "float",
    "double", "char", "bool", "boolean", "string", "struct", "enum",
    # Go / Rust
    "func", "package", "fn", "mut", "impl", "trait", "pub"
}

TYPE_NAMES = {
    "str", "int", "float", "bool", "list", "dict", "set", "tuple",
    "any", "object", "array", "number", "boolean", "void", "promise"
}


def extract_code_and_prose(text: str) -> Tuple[str, Optional[str], str]:
    """
    Separates markdown code blocks from prose explanation text.

    Returns:
        Tuple of (clean_prose: str, code_snippet: Optional[str], language: str)
    """
    if not text:
        return "", None, ""

    # Check for markdown code fences: ```[lang]\n...\n```
    fence_pattern = re.compile(r"```([a-zA-Z0-9_\-\+]*)\s*\n(.*?)```", re.DOTALL)
    m = fence_pattern.search(text)
    if m:
        lang = m.group(1).strip().lower() or "code"
        code = m.group(2).rstrip()
        # Remove the code fence from prose
        prose_before = text[:m.start()].strip()
        prose_after = text[m.end():].strip()
        prose = f"{prose_before}\n\n{prose_after}".strip()
        return prose, code, lang

    # Fallback: check for single unclosed code fence at end of stream
    unclosed_pattern = re.compile(r"```([a-zA-Z0-9_\-\+]*)\s*\n(.*)$", re.DOTALL)
    m_unc = unclosed_pattern.search(text)
    if m_unc:
        lang = m_unc.group(1).strip().lower() or "code"
        code = m_unc.group(2).rstrip()
        prose = text[:m_unc.start()].strip()
        return prose, code, lang

    # Check if the entire response looks like pure code (e.g. starts with def/function/SELECT)
    lines = [l for l in text.splitlines() if l.strip()]
    if lines:
        first = lines[0].strip()
        first_token = first.split()[0].lower() if first.split() else ""
        if first_token in {"def", "class", "import", "from"}:
            return "Code Solution", text.strip(), "python"
        elif first_token in {"function", "const", "let", "var"}:
            return "Code Solution", text.strip(), "javascript"
        elif first_token in {"select", "insert", "update", "delete", "create"}:
            return "Code Solution", text.strip(), "sql"
        elif first_token in {"#include", "public", "private", "struct"}:
            return "Code Solution", text.strip(), "cpp"
        elif first_token in {"package", "func"}:
            return "Code Solution", text.strip(), "go"
        elif first_token in {"fn", "impl", "trait"}:
            return "Code Solution", text.strip(), "rust"

    return text.strip(), None, ""


def apply_syntax_highlighting(text_widget: tk.Text, code: Optional[str], language: str = "", lang: str = ""):
    """
    Renders code into a Tkinter Text widget with styled syntax coloring:
    - Keywords: Emerald Green (#34d399)
    - Strings: Amber (#fbbf24)
    - Comments: Slate Gray (#64748b)
    - Numbers: Purple (#c084fc)
    - Types: Sky Blue (#38bdf8)
    """
    text_widget.configure(state="normal")
    text_widget.delete("1.0", tk.END)
    if not code:
        text_widget.configure(state="disabled")
        return

    text_widget.insert("1.0", code)

    # Configure tag styles matching dark aesthetic (support both short and descriptive tag names)
    text_widget.tag_configure("kw", foreground="#34d399", font=("Consolas", 9, "bold"))
    text_widget.tag_configure("keyword", foreground="#34d399", font=("Consolas", 9, "bold"))
    text_widget.tag_configure("str", foreground="#fbbf24")
    text_widget.tag_configure("string", foreground="#fbbf24")
    text_widget.tag_configure("comment", foreground="#64748b", font=("Consolas", 9, "italic"))
    text_widget.tag_configure("num", foreground="#c084fc")
    text_widget.tag_configure("number", foreground="#c084fc")
    text_widget.tag_configure("type", foreground="#38bdf8")

    # Apply line-by-line highlighting
    for line_idx, line in enumerate(code.splitlines(), start=1):
        if not line:
            continue

        # 1. Comments
        comment_match = re.search(r"(#|//|--)(.*)$", line)
        comment_start = len(line)
        if comment_match:
            c_start = comment_match.start()
            comment_start = c_start
            text_widget.tag_add("comment", f"{line_idx}.{c_start}", f"{line_idx}.end")

        # 2. Strings (single and double quotes before comment)
        code_part = line[:comment_start]
        for str_match in re.finditer(r"([\"'])(?:\\.|[^\\])*?\1", code_part):
            s_start, s_end = str_match.span()
            text_widget.tag_add("str", f"{line_idx}.{s_start}", f"{line_idx}.{s_end}")
            text_widget.tag_add("string", f"{line_idx}.{s_start}", f"{line_idx}.{s_end}")

        # 3. Numbers
        for num_match in re.finditer(r"\b\d+(?:\.\d+)?\b", code_part):
            n_start, n_end = num_match.span()
            existing_tags = text_widget.tag_names(f"{line_idx}.{n_start}")
            if "str" not in existing_tags and "string" not in existing_tags:
                text_widget.tag_add("num", f"{line_idx}.{n_start}", f"{line_idx}.{n_end}")
                text_widget.tag_add("number", f"{line_idx}.{n_start}", f"{line_idx}.{n_end}")

        # 4. Words (Keywords and Types)
        for word_match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code_part):
            w_start, w_end = word_match.span()
            word = word_match.group(0)
            existing_tags = text_widget.tag_names(f"{line_idx}.{w_start}")
            if "str" in existing_tags or "string" in existing_tags or "comment" in existing_tags:
                continue

            if word.lower() in KEYWORDS or word in KEYWORDS:
                text_widget.tag_add("kw", f"{line_idx}.{w_start}", f"{line_idx}.{w_end}")
                text_widget.tag_add("keyword", f"{line_idx}.{w_start}", f"{line_idx}.{w_end}")
            elif word.lower() in TYPE_NAMES:
                text_widget.tag_add("type", f"{line_idx}.{w_start}", f"{line_idx}.{w_end}")

    text_widget.configure(state="disabled")
