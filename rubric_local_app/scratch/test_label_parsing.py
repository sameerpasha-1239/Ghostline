import re
from typing import Dict, List, Tuple

def parse_options_and_stem(lines: List[str]) -> Tuple[str, Dict[str, str], bool]:
    """
    Parses lines into question stem and options dictionary.
    Supports:
    - Letter labels: A, B, C, D (e.g. A. / A) / (A) / [A])
    - Numeric labels: 1, 2, 3, 4 (e.g. 1. / 1) / (1) / [1])
    - Roman numeral labels: (i), (ii), (iii), (iv) / i., ii., iii., iv.
    - True / False / OX
    - Unlabeled bullet points: •, -, *
    - Disambiguation of leading question number (e.g. "3. What is...")
    """
    # 1. Inline split
    inline_split_regex = re.compile(
        r'\s+(?=(?:'
        r'[\(\[]?(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})[\)\]\.\:\-]\s+'
        r'|\((?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\)\s+'
        r'|\[(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\]\s+'
        r'))'
    )
    
    split_lines = []
    for line in lines:
        parts = inline_split_regex.split(line.strip())
        for p in parts:
            p_str = p.strip()
            if p_str:
                split_lines.append(p_str)

    # Patterns for option prefixes
    # Pattern 1: Delimited prefix, e.g. "A. Text", "1) Text", "(i) Text", "[1] Text", "A: Text"
    opt_prefix_regex = re.compile(
        r'^(?:'
        r'[\(\[]?([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})[\)\]\.\:\-]\s*'
        r'|\(([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\)\s*'
        r'|\[([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\]\s*'
        r')(.*)$'
    )
    
    # Pattern 2: Bullet prefix, e.g. "• Text", "- Text", "* Text"
    bullet_regex = re.compile(r'^[•\-\*\>]\s*(.+)$')

    candidates = []
    q_lines = []
    
    for idx, line in enumerate(split_lines):
        m = opt_prefix_regex.match(line)
        if m:
            raw_key = m.group(1) or m.group(2) or m.group(3)
            val = m.group(4).strip()
            # If line is parenthesized, preserve parentheses if it was Roman or numeric
            if line.startswith("(") and (raw_key in ["i", "ii", "iii", "iv", "v", "I", "II", "III", "IV", "V"] or raw_key.isdigit()):
                key = f"({raw_key})"
            elif raw_key.isalpha() and len(raw_key) == 1:
                key = raw_key.upper()
            else:
                key = raw_key
            candidates.append({"line_idx": idx, "key": key, "raw_key": raw_key, "val": val, "line": line})
        else:
            m_bullet = bullet_regex.match(line)
            if m_bullet:
                candidates.append({"line_idx": idx, "key": None, "raw_key": None, "val": m_bullet.group(1).strip(), "line": line, "is_bullet": True})
            else:
                candidates.append({"line_idx": idx, "key": None, "raw_key": None, "val": line, "line": line, "is_text": True})

    # Now filter candidates: identify the actual option block vs question stem
    # If the first candidate has a key (e.g. "3. What is..."), is it the question stem or an option?
    # A line is a question stem if:
    # - It contains a question mark '?'
    # - It has interrogatives ("which", "what", "how", "why", "calculate", "find")
    # - Subsequent candidates start from '1' or 'A' or '(i)'
    options = {}
    question_parts = []
    
    # Find option start index
    # Check if we have standard labeled sequence
    option_entries = [c for c in candidates if c.get("key") is not None]
    
    # Check if leading entry is a question stem
    if option_entries:
        first = option_entries[0]
        val_lower = first["val"].lower()
        is_stem_like = (
            "?" in first["line"]
            or any(val_lower.startswith(w) for w in ["which", "what", "how", "why", "explain", "find", "determine", "identify", "calculate"])
            or len(first["val"].split()) >= 6
        )
        if is_stem_like and len(option_entries) > 1:
            # First labeled entry is actually a question stem (e.g. "1. Which of the following...")
            first["is_stem"] = True
            first["key"] = None

    # Check if all remaining candidates are bullets (unlabeled options)
    non_stem_candidates = [c for c in candidates if not c.get("is_stem")]
    labeled_candidates = [c for c in non_stem_candidates if c.get("key") is not None]
    bullet_candidates = [c for c in non_stem_candidates if c.get("is_bullet")]

    if len(labeled_candidates) >= 2:
        # We have labeled options!
        # Detect if we have multiple types (e.g. question number 3 followed by 1, 2, 3, 4)
        keys = [c["key"] for c in labeled_candidates]
        
        # Check if first key is an outlier before a standard sequence (e.g. '3' followed by '1', '2', '3', '4')
        if len(keys) >= 3 and keys[0] in ["1", "2", "3", "4", "5", "6", "7", "8", "9"] and keys[1] == "1":
            # keys[0] was the question number
            labeled_candidates[0]["is_stem"] = True
            labeled_candidates = labeled_candidates[1:]

        in_options = False
        current_k = None
        for c in candidates:
            if c.get("is_stem") or (not in_options and c.get("key") is None):
                question_parts.append(c["line"])
            elif c.get("key") is not None and c in labeled_candidates:
                in_options = True
                current_k = c["key"]
                options[current_k] = c["val"]
            elif in_options and current_k:
                # Continuation line
                options[current_k] += " " + c["line"]
    elif len(bullet_candidates) >= 2:
        # Unlabeled options with unambiguous structure (bullets)
        # Infer numeric labels 1, 2, 3...
        for idx, b in enumerate(bullet_candidates, 1):
            options[str(idx)] = b["val"]
        for c in candidates:
            if not c.get("is_bullet"):
                question_parts.append(c["line"])
    else:
        # No clear multiple-choice options
        for c in candidates:
            question_parts.append(c["line"])

    question_text = " ".join(question_parts).strip()
    return question_text, options, len(options) >= 2

if __name__ == "__main__":
    tests = [
        ("Letters", ["Which protocol is secure?", "A) FTP", "B) HTTP", "C) HTTPS", "D) SSH"]),
        ("Numbers", ["Which is primary color?", "1. Red", "2. Green", "3. Blue", "4. Yellow"]),
        ("Q-Num with Numbers", ["3. Which is primary color?", "1. Red", "2. Green", "3. Blue", "4. Yellow"]),
        ("Q-Num with Letters", ["5. Which protocol is secure?", "A. FTP", "B. HTTP", "C. HTTPS", "D. SSH"]),
        ("Roman Numerals", ["What is the mitotic order?", "(i) Prophase", "(ii) Metaphase", "(iii) Anaphase", "(iv) Telophase"]),
        ("Inline Numbers", ["Calculate 2+2.", "1) 3  2) 4  3) 5  4) 6"]),
        ("Bulleted Unlabeled", ["Select the relational database:", "• Redis", "• Postgres", "• Memcached"]),
    ]

    for name, lines in tests:
        q, opts, is_mcq = parse_options_and_stem(lines)
        print(f"=== {name} ===")
        print(f"Question: '{q}'")
        print(f"Options: {opts}")
        print(f"Is MCQ: {is_mcq}\n")
