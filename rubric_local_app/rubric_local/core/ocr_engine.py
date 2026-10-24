import os
import sys
import json
import subprocess
import tempfile
import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image
from pydantic import BaseModel, Field

class ParsedQuestion(BaseModel):
    raw_text: str = ""
    lines: List[str] = Field(default_factory=list)
    question_text: str = ""
    options: Dict[str, str] = Field(default_factory=dict)
    is_multiple_choice: bool = False
    is_unlabelled_mcq: bool = False
    is_valid_question: bool = True
    validation_reason: str = ""

def get_win_ocr_binary_path() -> Path:
    # 1. Check PyInstaller bundled resource directory (_MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        meipass_p = Path(sys._MEIPASS) / "bin" / "win_ocr.exe"
        if meipass_p.exists():
            return meipass_p

    # 2. Check relative to executable parent (_internal or adjacent bin)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for cand in [exe_dir / "bin" / "win_ocr.exe", exe_dir / "_internal" / "bin" / "win_ocr.exe"]:
            if cand.exists():
                return cand

    # 3. Check relative to source repository root
    base_dir = Path(__file__).resolve().parent.parent.parent
    bin_path = base_dir / "bin" / "win_ocr.exe"
    if bin_path.exists():
        return bin_path

    # 4. Check current working directory
    for cand in [Path.cwd() / "bin" / "win_ocr.exe", Path.cwd() / "rubric_local_app" / "bin" / "win_ocr.exe"]:
        if cand.exists():
            return cand

    raise FileNotFoundError(f"win_ocr.exe not found. Searched base_dir={bin_path}")

def run_native_ocr(image: Image.Image) -> Dict:
    """Executes native Windows.Media.Ocr on the provided PIL Image without flashing console windows."""
    ocr_bin = get_win_ocr_binary_path()
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
        
    try:
        # Preprocessing: upscale if image is small for superior OCR accuracy
        w, h = image.size
        if w < 1200:
            scale = 2
            image = image.resize((w * scale, h * scale), Image.Resampling.LANCZOS)

        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(tmp_path, format="PNG")
        
        creationflags = 0
        startupinfo = None
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

        t0_sub = time.perf_counter()
        logging.info("[PID:%d] Executing native OCR subprocess: %s %s (creationflags=0x%08X)",
                     os.getpid(), ocr_bin, tmp_path, creationflags)

        proc = subprocess.run(
            [str(ocr_bin), tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
        t_sub = (time.perf_counter() - t0_sub) * 1000.0
        logging.info("[PID:%d] OCR subprocess completed in %.1fms (returncode=%d, output_bytes=%d)",
                     os.getpid(), t_sub, proc.returncode, len(proc.stdout or ""))
        
        if proc.returncode != 0:
            raise RuntimeError(f"OCR binary exited with code {proc.returncode}: {proc.stderr}")
            
        data = json.loads(proc.stdout)
        return data
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def _is_meaningful_question(text: str, options: Dict[str, str]) -> Tuple[bool, str]:
    """
    Validates whether the extracted text and options represent a legitimate question.
    Rejects arbitrary UI chrome, file tabs, and isolated word lists while supporting:
    - Multiple-choice questions (labelled, unlabelled, bulleted)
    - Interrogative questions with '?'
    - Imperative problem stems ('Solve for', 'Evaluate', 'Determine', 'Find', 'Select', 'Consider', 'Given')
    - Programming / code-based assessment problems
    - Multi-line technical stems
    """
    cleaned = text.strip()
    if not cleaned:
        return False, "Empty text detected from screen capture."
        
    words = cleaned.split()
    if len(words) < 2 or len(cleaned) < 8:
        return False, f"Extracted text is too short ({len(words)} words, {len(cleaned)} chars) to be a valid question."

    # 1. Multiple-choice questions (at least 2 options detected)
    if len(options) >= 2 and len(words) >= 3:
        return True, "Valid multiple-choice question."

    # 2. Interrogative question mark
    if "?" in cleaned:
        return True, "Valid question with interrogative question mark."

    # 3. Question numbering or problem prefixes (e.g. Question 1:, Q1., Problem:, Task:)
    if re.match(r"^(?:Question\b|Q\s*[\d\.\:]|Problem\b|Exercise\b|Task\b|Example\b|\d+[\.\)])", cleaned, re.IGNORECASE):
        if len(words) >= 3:
            return True, "Valid question with problem prefix."

    # 4. Assessment verbs and interrogative phrases (covers standard and online proctored tests)
    assessment_pattern = re.compile(
        r"\b("
        r"which\s+(?:of\s+the\s+following|one|choice|statement|option)|"
        r"what\s+(?:is|are|does|will|would|can|should|was|were)|"
        r"how\s+(?:many|much|do|does|can|could|is|are|to)|"
        r"why\s+(?:is|are|do|does|did)|"
        r"solve\s+(?:for|the|this)|"
        r"evaluate\s+(?:the|each|all|following)|"
        r"calculate\s+(?:the|all|each|following)|"
        r"determine\s+(?:the|all|whether|which|if|following)|"
        r"find\s+(?:the|all|each|value|out|which|what)|"
        r"select\s+(?:the|all|one|which|correct|following)|"
        r"choose\s+(?:the|all|one|which|correct|following)|"
        r"identify\s+(?:the|all|each|which|following)|"
        r"explain\s+(?:the|how|why|what|following)|"
        r"define\s+(?:the|what|how)|"
        r"describe\s+(?:the|how|why)|"
        r"simplify\s+(?:the|each|following)|"
        r"consider\s+(?:the|a|an|following)|"
        r"given\s+(?:that|the|a|an|following)|"
        r"suppose\s+(?:that|a|an)|"
        r"assume\s+(?:that|a|an)|"
        r"match\s+(?:the|column|each)|"
        r"complete\s+(?:the|following)|"
        r"fill\s+in\s+the\s+blank|"
        r"true\s+or\s+false|"
        r"output\s+of\s+(?:the|following)|"
        r"what\s+will\s+be\s+the\s+output|"
        r"predict\s+the\s+output|"
        r"state\s+whether"
        r")\b",
        re.IGNORECASE
    )
    if assessment_pattern.search(cleaned) and len(words) >= 3:
        return True, "Valid question with assessment verb or interrogative stem."

    # 5. Programming / code question detection
    code_indicators = ["def ", "class ", "int main", "public static", "SELECT ", "console.log", "return ", "#include", "import "]
    if any(ind in cleaned for ind in code_indicators) and len(words) >= 5:
        return True, "Valid programming question with code keywords."

    # 6. Technical problem statement ending in a colon or containing mathematical relation
    if len(words) >= 8 and (cleaned.rstrip().endswith(":") or re.search(r"\b[a-zA-Z]\s*=\s*[\d\w]", cleaned)):
        return True, "Valid technical problem statement."

    return False, "Captured text does not contain question indicators or multiple-choice options."

def parse_question_structure(ocr_data: Dict) -> ParsedQuestion:
    """
    Parses OCR text into question stem and multiple-choice options.
    Supports arbitrary option labeling schemes:
    - Letter labels: A, B, C, D (e.g. A. / A) / (A) / [A])
    - Numeric labels: 1, 2, 3, 4 (e.g. 1. / 1) / (1) / [1])
    - Roman numeral labels: (i), (ii), (iii), (iv) / i., ii., iii., iv.
    - True / False / OX format
    - Bulleted options: •, -, *, >
    - Genuinely unlabelled options (list of choices following question stem)
    - Disambiguates question numbers, years, decimals, and arithmetic from option labels.
    """
    if isinstance(ocr_data, str):
        ocr_data = {"text": ocr_data, "lines": [line.strip() for line in ocr_data.splitlines() if line.strip()]}
    raw_text = ocr_data.get("text", "") or ""
    raw_lines = [line.strip() for line in ocr_data.get("lines", []) if line.strip()]
    
    if not raw_lines and raw_text:
        raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # Normalize lines: split multi-option lines (e.g. "1) Red  2) Green  3) Blue" or "A) Paris  B) London")
    lines = []
    inline_split_regex = re.compile(
        r"\s+(?=(?:"
        r"[\(\[]?(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})[\)\]\-]\s+"
        r"|\((?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\)\s+"
        r"|\[(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\]\s+"
        r"|(?:[A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})[\.\:](?!\d)\s+"
        r"))"
    )
    for line in raw_lines:
        subparts = inline_split_regex.split(line)
        for part in subparts:
            p = part.strip()
            if p:
                lines.append(p)

    # Option prefix regex:
    # Delimiters: ')', ']', '-', or '.' / ':' NOT followed by a digit (prevent matching decimals e.g. 3.14 or ratios 1:2)
    opt_prefix_regex = re.compile(
        r"^(?:"
        r"[\(\[]?([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})[\)\]\-]\s*"
        r"|\(([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\)\s*"
        r"|\[([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})\]\s*"
        r"|([A-Za-z]|[1-9]\d?|[ivxIVX]{1,4})[\.\:](?!\d)\s*"
        r")(.*)$"
    )
    
    bullet_regex = re.compile(r"^[•\-\*\>]\s*(.+)$")

    candidates = []
    for idx, line in enumerate(lines):
        m = opt_prefix_regex.match(line)
        if m:
            raw_key = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            val = m.group(5).strip()
            # If line is parenthesized, preserve parentheses for Roman numerals or numbers if written as (i) or (1)
            if line.startswith("(") and (raw_key.lower() in ["i", "ii", "iii", "iv", "v", "x"] or raw_key.isdigit()):
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

    # Disambiguate leading question numbers (e.g. "3. Which of the following..." or "1. What is...")
    option_entries = [c for c in candidates if c.get("key") is not None]
    if option_entries:
        first = option_entries[0]
        val_lower = first["val"].lower()
        is_stem_like = (
            "?" in first["line"]
            or any(val_lower.startswith(w) for w in [
                "which", "what", "how", "why", "explain", "find", "determine", "identify",
                "calculate", "state", "select", "a company", "in python", "consider"
            ])
            or len(first["val"].split()) >= 6
        )
        if is_stem_like and len(option_entries) > 1:
            first["is_stem"] = True
            first["key"] = None

    non_stem_candidates = [c for c in candidates if not c.get("is_stem")]
    labeled_candidates = [c for c in non_stem_candidates if c.get("key") is not None]
    bullet_candidates = [c for c in non_stem_candidates if c.get("is_bullet")]

    options = {}
    question_lines = []
    is_unlabelled = False

    if len(labeled_candidates) >= 2:
        # Check if first key is an outlier before a standard sequence (e.g. question '3' before '1', '2', '3', '4')
        keys = [c["key"] for c in labeled_candidates]
        if len(keys) >= 3 and keys[0] in ["1", "2", "3", "4", "5", "6", "7", "8", "9"] and keys[1] == "1":
            labeled_candidates[0]["is_stem"] = True
            labeled_candidates = labeled_candidates[1:]
        elif len(keys) >= 3 and keys[0] in ["1", "2", "3", "4", "5", "6", "7", "8", "9"] and keys[1] in ["A", "(i)", "i"]:
            labeled_candidates[0]["is_stem"] = True
            labeled_candidates = labeled_candidates[1:]

        in_options = False
        current_k = None
        for c in candidates:
            if c.get("is_stem") or (not in_options and c.get("key") is None):
                question_lines.append(c["line"])
            elif c.get("key") is not None and c in labeled_candidates:
                in_options = True
                current_k = c["key"]
                options[current_k] = c["val"]
            elif in_options and current_k:
                # Continuation line
                options[current_k] += " " + c["line"]
    elif len(bullet_candidates) >= 2:
        # Bulleted options without alphanumeric labels -> assign 1-based sequential indices
        is_unlabelled = True
        for idx, b in enumerate(bullet_candidates, 1):
            options[str(idx)] = b["val"]
        for c in candidates:
            if not c.get("is_bullet"):
                question_lines.append(c["line"])
    else:
        # Check for genuinely unlabelled multiple choice options (plain list of choices following a question stem)
        stem_end_idx = -1
        interrogative_regex = re.compile(
            r"\b(which|what|how|why|explain|define|calculate|determine|find|select|identify|state)\b",
            re.IGNORECASE
        )
        for i, c in enumerate(candidates):
            c_text = c["val"].strip()
            if "?" in c_text or interrogative_regex.search(c_text) or c_text.endswith(":"):
                stem_end_idx = i

        if stem_end_idx >= 0 and len(candidates) - (stem_end_idx + 1) >= 2:
            potential_opts = candidates[stem_end_idx + 1:]
            # Ensure potential option lines are concise and do not contain question stems
            valid_unlabelled = True
            for opt_cand in potential_opts:
                opt_str = opt_cand["val"].strip()
                if not opt_str or "?" in opt_str or len(opt_str) > 140:
                    valid_unlabelled = False
                    break
            
            if valid_unlabelled and 2 <= len(potential_opts) <= 8:
                is_unlabelled = True
                for idx, opt_cand in enumerate(potential_opts, 1):
                    options[str(idx)] = opt_cand["val"].strip()
                for c in candidates[:stem_end_idx + 1]:
                    question_lines.append(c["line"])

        if not options:
            # Truly open-ended question or unparsed text
            for c in candidates:
                question_lines.append(c["line"])

    question_text = " ".join(question_lines).strip()
    is_mcq = len(options) >= 2
    
    # Structural validity verification
    is_valid, reason = _is_meaningful_question(question_text if question_text else raw_text, options)
    
    return ParsedQuestion(
        raw_text=raw_text,
        lines=lines,
        question_text=question_text if question_text else raw_text,
        options=options,
        is_multiple_choice=is_mcq,
        is_unlabelled_mcq=is_unlabelled,
        is_valid_question=is_valid,
        validation_reason=reason
    )

