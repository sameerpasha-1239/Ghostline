import sys
import json
import re
import ast
import operator
from typing import Optional, Callable, Dict, Any, List, Tuple
import requests
from pydantic import BaseModel, Field

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def normalize_tray_badge(
    badge: Optional[str],
    is_validated: bool = True,
    is_multiple_choice: bool = True,
    status: str = "normal"
) -> str:
    """
    Centralized, bulletproof badge normalizer.
    Guarantees that NO code path can EVER pass an entire answer string
    or unconstrained text into the 32x32 system tray icon.

    Rules:
    - If status == 'thinking': '' (tray renders ellipsis)
    - If status == 'ready': 'R'
    - If status == 'error' or not is_validated or badge in ('Uncertain', '?', '!', None, ''):
        returns '!' if status == 'error' else '?'
    - If is_multiple_choice is False (open-ended question):
        returns '✓' if is_validated else '?'
    - If is_multiple_choice is True:
        If badge is a short recognized option label (<= 4 chars, e.g. '1', '2', 'A', 'B', '(i)', '(iv)'):
            returns clean label
        Else (if an answer string was accidentally passed):
            returns '✓' if is_validated else '?'
    - Absolute length ceiling: 4 characters max.
    """
    if status == "thinking":
        return ""
    if status == "ready":
        return "R"
    if badge in ("?", "Uncertain", "uncertain"):
        return "?"
    if badge == "!" or status == "error":
        return "!"
    if not is_validated or badge in ("", None):
        return "?"

    # Open-ended questions ALWAYS use short status glyph '✓' (never full answer text)
    if not is_multiple_choice:
        return "✓"

    raw = str(badge).strip()

    # For multiple-choice questions, check if raw is a concise label (e.g. '1', '2', 'A', 'B', '(i)', '(iv)')
    if len(raw) <= 4 and (" " not in raw or raw.startswith("(")):
        return raw

    # Fallback safety: if full answer string was passed, represent with short status symbol
    return "✓"


class AnswerResult(BaseModel):
    source_option_label: str = Field(default="Uncertain", description="The exact validated option label (e.g. '3', 'B', '(ii)', '✓') or 'Uncertain' if unvalidated")
    option_text: str = Field(default="", description="The exact text content of the validated option")
    explanation: str = Field(default="", description="Short, concise 1-2 sentence explanation or rationale")
    is_validated: bool = Field(default=False, description="Whether the answer was successfully validated against known options or format")
    validation_status: str = Field(default="uncertain", description="Validation status: 'validated', 'uncertain', 'error', 'hallucination_rejected', 'open_ended_factual'")
    confidence_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Calibrated confidence metadata and validation telemetry")
    answer_option: str = Field(default="Uncertain", description="Backward-compatible alias for source_option_label or short open-ended answer")
    proposed_option: Optional[str] = Field(default=None, description="The raw option proposed by the model before validation")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Heuristic confidence score (not proof of factual truth)")
    raw_response: str = Field(default="", description="Complete raw text from the model")
    error: Optional[str] = Field(default=None, description="Validation or parsing error message if uncertain")
    is_multiple_choice: bool = Field(default=True, description="Whether the question was multiple-choice")
    is_unlabelled_mcq: bool = Field(default=False, description="Whether multiple-choice options were unlabelled")
    code_snippet: Optional[str] = Field(default=None, description="Extracted code solution or programming snippet")
    code_language: str = Field(default="", description="Identified language for code snippet (python, javascript, sql, etc.)")
    question_type: str = Field(default="mcq", description="Detected question type: 'mcq', 'code', 'theory', 'true_false', 'numerical', 'fill_blank', 'unknown'")
    direct_answer: str = Field(default="", description="Direct concise answer, numerical value, formula, or option value")

    @property
    def tray_badge(self) -> str:
        if self.is_validated and (not self.is_multiple_choice or self.question_type in ["code", "theory", "numerical", "fill_blank", "true_false"]):
            if self.question_type == "code":
                return "Code"
            if self.question_type == "true_false":
                return "T" if str(self.source_option_label).strip().lower().startswith(("t", "y")) else "F"
            if self.source_option_label and self.source_option_label not in ("Uncertain", "?", "!"):
                return normalize_tray_badge(self.source_option_label, is_validated=True, is_multiple_choice=False)
            return "✓"
        return normalize_tray_badge(
            self.source_option_label,
            is_validated=self.is_validated,
            is_multiple_choice=self.is_multiple_choice,
            status="error" if self.validation_status == "error" else "normal"
        )

def extract_code_block(text: str) -> Tuple[Optional[str], str]:
    """Helper to detect and extract markdown code fence from model response."""
    if not text:
        return None, ""
    m = re.search(r"```([a-zA-Z0-9_\-\+]*)\s*\n(.*?)```", text, re.DOTALL)
    if m:
        lang = m.group(1).strip().lower() or "code"
        code = m.group(2).rstrip()
        return code, lang
    return None, ""

ALLOWED_MATH_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _safe_eval_ast(node: ast.AST):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Non-numeric constant")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_MATH_OPERATORS:
            raise ValueError(f"Operator {op_type} not allowed")
        left = _safe_eval_ast(node.left)
        right = _safe_eval_ast(node.right)
        return ALLOWED_MATH_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_MATH_OPERATORS:
            raise ValueError(f"Operator {op_type} not allowed")
        operand = _safe_eval_ast(node.operand)
        return ALLOWED_MATH_OPERATORS[op_type](operand)
    else:
        raise ValueError(f"Node type {type(node)} not allowed")

def try_solve_deterministic_math(text: str) -> Tuple[Optional[str], Optional[float]]:
    """
    Deterministically and safely solves standard arithmetic expressions and simple linear equations.
    Only allows basic arithmetic AST evaluation (pure math, zero risk of code injection).
    """
    if not text:
        return None, None

    # 1. Linear equation: e.g. "3x + 15 = 42" or "2y - 6 = 12"
    m_lin = re.search(r"\b([+-]?\s*\d*)\s*([a-zA-Z])\s*([+-]\s*\d+)\s*=\s*([+-]?\s*\d+)\b", text)
    if m_lin:
        a_str, var, b_str, c_str = m_lin.groups()
        a_str = a_str.replace(" ", "")
        if not a_str or a_str == "+":
            a = 1.0
        elif a_str == "-":
            a = -1.0
        else:
            try:
                a = float(a_str)
            except ValueError:
                a = 0.0
        try:
            b = float(b_str.replace(" ", ""))
            c = float(c_str.replace(" ", ""))
            if a != 0:
                sol = (c - b) / a
                sol_num = int(sol) if sol.is_integer() else round(sol, 4)
                return f"{var} = {sol_num}", float(sol_num)
        except Exception:
            pass

    # 2. Arithmetic expression: e.g. "25 * 4 - 30 / 2" or "17 % 5 + 2 * 3^2"
    m_arith = re.search(r"(\d+(?:\.\d+)?(?:\s*[\+\-\*\/\%\^]\s*\d+(?:\.\d+)?)+)", text)
    if m_arith:
        expr = m_arith.group(1).strip()
        expr = re.sub(r"\s+", "", expr)
        expr = re.sub(r"[\+\-\*\/\%\^]+$", "", expr)
        py_expr = expr.replace("^", "**")
        try:
            tree = ast.parse(py_expr, mode='eval')
            val = _safe_eval_ast(tree.body)
            if isinstance(val, (int, float)):
                val_num = int(val) if float(val).is_integer() else round(float(val), 4)
                return str(val_num), float(val_num)
        except Exception:
            pass

    return None, None

def classify_question_type(question_text: str, options: Optional[Dict[str, str]] = None) -> str:
    """Classifies question into one of: 'mcq', 'true_false', 'numerical', 'programming', 'theory'."""
    text_clean = (question_text or "").strip().lower()
    
    if options and len(options) >= 2:
        opt_keys_clean = set(k.strip("().:- ").lower() for k in options.keys())
        opt_vals_clean = set(v.strip("().:- ").lower() for v in options.values())
        if opt_keys_clean.issubset({"true", "false", "t", "f"}) or opt_vals_clean.issubset({"true", "false", "t", "f"}):
            return "true_false"
        return "mcq"

    # Open-ended
    # 1. True / False indicators
    if re.search(r"\b(?:true\s+or\s+false|state\s+whether\s+true|is\s+true\s+or\s+false|is\s+this\s+true)\b", text_clean):
        return "true_false"
    if text_clean.startswith("state whether") or text_clean.startswith("true or false:"):
        return "true_false"

    # 2. Programming / Code
    code_indicators = ["def ", "class ", "int main", "public static", "select ", "console.log", "return ", "import ", "function ", "```", "len(", "dereferencing", "pointer"]
    if any(ind in text_clean for ind in code_indicators):
        return "programming"

    # 3. Numerical / Math
    math_indicators = ["solve for", "calculate", "evaluate", "derivative", "hit ratio", "amat", "what is the result of", "ip addresses", "usable hosts"]
    if any(ind in text_clean for ind in math_indicators) or re.search(r"\d+\s*[\+\-\*\/\%\^]\s*\d+", text_clean) or re.search(r"\b[a-zA-Z]\s*=\s*\d+", text_clean):
        return "numerical"

    return "theory"


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", default_model: str = "phi3:mini"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def is_available(self) -> bool:
        """Verifies if the local Ollama daemon is reachable on localhost."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Returns list of installed local models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def solve_question(
        self,
        question_text: str,
        options: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        is_unlabelled_mcq: bool = False
    ) -> AnswerResult:
        """
        Submits question and options to local Ollama LLM and validates structured output.
        """
        selected_model = model or self.default_model

        # 1. Classify question type
        q_type = classify_question_type(question_text, options)

        # 2. Build structured, question-type-tailored prompt
        prompt = self._construct_prompt(question_text, options, is_unlabelled_mcq=is_unlabelled_mcq, question_type=q_type)

        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": stream_callback is not None,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 250
            }
        }

        full_response = ""

        try:
            if stream_callback:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    stream=True,
                    timeout=60.0
                )
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        full_response += token
                        stream_callback(token)
            else:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=60.0
                )
                resp.raise_for_status()
                full_response = resp.json().get("response", "")

            result = self._parse_and_validate_response(
                full_response,
                options,
                is_unlabelled_mcq=is_unlabelled_mcq,
                question_text=question_text,
                question_type=q_type
            )
            
            # Diagnostic logging (redacting screen content, logging structured tokens)
            try:
                print(f"[*] [LLM Diagnostic] Model: {selected_model} | Output Length: {len(full_response)} chars")
                print(f"[*] [LLM Diagnostic] Proposed: {result.proposed_option} | Validated: {result.is_validated} | Final Badge: {result.tray_badge} | Answer: {result.answer_option}")
                if result.error:
                    print(f"[!] [LLM Diagnostic] Validation Warning: {result.error}")
            except Exception:
                pass

            return result

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to local Ollama daemon at {self.base_url}. "
                "Ensure Ollama is started locally (`ollama serve`)."
            )
        except Exception as ex:
            raise RuntimeError(f"Local AI inference failed: {str(ex)}")

    def _construct_prompt(
        self,
        question: str,
        options: Optional[Dict[str, str]],
        is_unlabelled_mcq: bool = False,
        question_type: Optional[str] = None
    ) -> str:
        q_type = question_type or classify_question_type(question, options)

        if options and len(options) >= 2:
            options_list = ", ".join(options.keys())
            formatted_opts = []
            for k, v in options.items():
                if k.endswith((")", ".", ":", "-", "]")):
                    formatted_opts.append(f"{k} {v}")
                else:
                    formatted_opts.append(f"{k}) {v}")
            options_text = "Options:\n" + "\n".join(formatted_opts)

            math_hint = ""
            if any(sym in question for sym in ("^", "%", "*", "/", "+", "-")):
                math_hint = "\nNote: In mathematical expressions, '^' denotes exponentiation (e.g. 3^2 = 9), NOT bitwise XOR. Follow standard mathematical order of operations (PEMDAS).\n"

            if is_unlabelled_mcq:
                instruction_1 = f"1. On the very first line, state ONLY the single correct option number ({options_list}), formatted exactly as:\nANSWER: [OPTION_NUMBER]\n(For example: 'ANSWER: 1' or 'ANSWER: 2')"
            else:
                instruction_1 = f"1. On the very first line, state ONLY the single correct option label, formatted exactly as:\nANSWER: [OPTION_LABEL]\n(For example: 'ANSWER: 2' or 'ANSWER: B' or 'ANSWER: (ii)')"

            return f"""You are Rubric-Local, a high-precision question-answering assistant.
Analyze the following multiple-choice question and determine the single correct answer option.

Question:
{question}

{options_text}
{math_hint}
Instructions:
{instruction_1}
2. On line 2, provide a clear, concise 1-2 sentence explanation justifying why this option is correct.
3. You MUST choose strictly from the provided options ({options_list}). Never invent or assume an option that is not listed.
"""

        # Non-MCQ / Open-ended prompt tailored by question type
        if q_type == "true_false":
            return f"""You are Rubric-Local, a high-precision question-answering assistant.
Analyze the following statement and determine if it is True or False.

Statement:
{question}

Instructions:
1. On line 1, state ONLY 'True' or 'False'.
2. On line 2, provide a concise 1-sentence explanation justifying why it is True or False.
"""

        elif q_type == "numerical":
            return f"""You are Rubric-Local, a high-precision mathematician and computer engineer.
Solve the following numerical problem carefully.

Problem:
{question}

Note: In mathematical expressions, '^' denotes exponentiation (e.g. 3x^3 is 3 times x cubed; 3^2 = 9), NOT bitwise XOR. Follow standard mathematical order of operations (PEMDAS).

Instructions:
1. On line 1, state ONLY the final concise numerical answer or value (e.g. '20' or 'x = 9' or '31').
2. On line 2, provide the concise step-by-step calculation or derivation.
"""

        elif q_type == "programming":
            return f"""You are Rubric-Local, a high-precision software engineer.
Analyze the following programming question.

Question:
{question}

Instructions:
1. If the question asks to write a function or code, provide clean, idiomatic code enclosed inside a markdown code block (```python ... ```).
2. If the question asks for program output or evaluation, state the exact output on line 1.
3. Provide a concise explanation on the next line.
"""

        else:  # theory
            return f"""You are Rubric-Local, a high-precision technical instructor.
Analyze the following technical question and provide a direct, factual explanation.

Question:
{question}

Instructions:
1. On line 1, state a direct, concise, factual explanation answering the question in 2-3 sentences.
2. Directly mention the core architectural and technical terms (e.g. mechanisms, protocols, components, definitions).
"""

    def _parse_and_validate_response(
        self,
        text: str,
        options: Optional[Dict[str, str]],
        is_unlabelled_mcq: bool = False,
        question_text: str = "",
        question_type: Optional[str] = None
    ) -> AnswerResult:
        cleaned = text.strip()
        code_snip, code_lang = extract_code_block(cleaned)

        if not cleaned:
            return AnswerResult(
                source_option_label="Uncertain",
                option_text="",
                answer_option="Uncertain",
                proposed_option=None,
                is_validated=False,
                validation_status="uncertain",
                confidence=0.0,
                confidence_metadata={"calibrated": False, "score": 0.0, "status": "empty_response"},
                explanation="Model returned an empty response.",
                raw_response=text,
                error="Empty model response",
                is_multiple_choice=bool(options and len(options) >= 2),
                is_unlabelled_mcq=is_unlabelled_mcq,
                code_snippet=None,
                code_language="",
                question_type="unknown",
                direct_answer=""
            )

        # CASE 1: Multiple Choice Question with extracted options
        if options and len(options) >= 2:
            # Deterministic arithmetic cross-validation check for MCQs
            det_math_ans, det_math_num = try_solve_deterministic_math(question_text)
            opt_math_match = None
            if det_math_ans or det_math_num is not None:
                for k, v in options.items():
                    v_clean = v.strip().lower()
                    if (det_math_ans and det_math_ans.lower() == v_clean) or (
                        det_math_num is not None and str(int(det_math_num) if float(det_math_num).is_integer() else det_math_num) == v_clean
                    ):
                        opt_math_match = k
                        break

            # Build normalized lookup table: maps normalized keys to the exact source key
            lookup: Dict[str, str] = {}
            for k in options.keys():
                lookup[k] = k
                lookup[k.lower()] = k
                lookup[k.upper()] = k
                clean = k.strip("()[]:.- ")
                if clean:
                    lookup[clean] = k
                    lookup[clean.lower()] = k
                    lookup[clean.upper()] = k

            lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
            first_line = lines[0] if lines else ""

            proposed = None
            
            # Pattern 1: Explicit "ANSWER: [TOKEN]"
            m_ans = re.search(r"ANSWER\s*[:\-]?\s*(\([^\)]+\)|\[[^\]]+\]|[^\s,;]+)", first_line, re.IGNORECASE)
            if m_ans:
                proposed = m_ans.group(1).strip()

            # Pattern 2: Option prefix on line 1, e.g. "B) ...", "3. ...", "(ii) ..."
            if not proposed:
                m_prefix = re.match(r"^(\([^\)]+\)|\[[^\]]+\]|[^\s\)\.\:\-]+)[\)\]\.\:\-]\s*", first_line)
                if m_prefix:
                    candidate = m_prefix.group(1).strip()
                    if candidate in lookup or candidate.strip("()[]:.- ") in lookup:
                        proposed = candidate

            # Pattern 3: "Option X" or "Choice X"
            if not proposed:
                m_opt = re.search(r"(?:Correct\s+Option|Option|Choice|Answer)\s*[:\-]?\s*(\([^\)]+\)|\[[^\]]+\]|[^\s,;]+)", first_line, re.IGNORECASE)
                if m_opt:
                    proposed = m_opt.group(1).strip()

            # Pattern 4: Global search for explicit "ANSWER: [TOKEN]" anywhere in text
            if not proposed:
                m_global = re.search(r"\bANSWER\s*[:\-]?\s*(\([^\)]+\)|\[[^\]]+\]|[^\s,;]+)", cleaned, re.IGNORECASE)
                if m_global:
                    proposed = m_global.group(1).strip()

            # Pattern 5: Content match — check if model responded directly with option text
            if not proposed:
                for k, v in options.items():
                    if v and len(v) >= 3 and v.lower() in first_line.lower():
                        proposed = k
                        break

            # STRICT VALIDATION: Resolve proposed token against exact source options
            matched_key = None
            if proposed:
                matched_key = lookup.get(proposed) or lookup.get(proposed.strip("()[]:.- ")) or lookup.get(proposed.upper()) or lookup.get(proposed.lower())

            # Fallback: if proposed was not an option key, check if model answered with the option VALUE
            if not matched_key:
                if proposed:
                    proposed_clean = proposed.strip("()[]:.- ").lower()
                    for k, v in options.items():
                        v_clean = v.strip().lower()
                        if proposed_clean == v_clean or proposed.lower() == v.lower():
                            matched_key = k
                            break

                if not matched_key:
                    for k, v in options.items():
                        v_clean = v.strip().lower()
                        if len(v_clean) >= 2 and (f" {v_clean} " in f" {first_line.lower()} " or first_line.lower().endswith(v_clean)):
                            matched_key = k
                            break

            # Deterministic math match fallback: if model was unparseable or made arithmetic error, but math matched an option
            if not matched_key and opt_math_match:
                matched_key = opt_math_match
                proposed = opt_math_match

            is_tf = bool(set(k.strip("().:- ").lower() for k in options.keys()).issubset({"true", "false", "t", "f"}))
            mcq_type = "true_false" if is_tf else "mcq"

            if matched_key and matched_key in options:
                validated_label = matched_key
                opt_content = options[validated_label]
                
                # Extract explanation lines
                explanation_lines = lines[1:] if (len(lines) > 1 and lines[0].startswith(("ANSWER", proposed or "", validated_label))) else lines
                explanation = "\n".join(explanation_lines).strip()
                if not explanation:
                    explanation = f"Option {validated_label}: {opt_content}"
                if opt_math_match and opt_math_match == validated_label:
                    explanation = f"[Verified by deterministic calculation: {det_math_ans}]\n{explanation}"

                return AnswerResult(
                    source_option_label=validated_label,
                    option_text=opt_content,
                    answer_option=validated_label,
                    proposed_option=proposed,
                    is_validated=True,
                    validation_status="validated",
                    confidence=0.98 if opt_math_match == validated_label else 0.95,
                    confidence_metadata={
                        "score": 0.98 if opt_math_match == validated_label else 0.95,
                        "calibrated": False,
                        "validation_type": "exact_option_match",
                        "matched_key": validated_label,
                        "disclaimer": "Schema validation confirms deterministic alignment with extracted options, not factual ground truth."
                    },
                    explanation=explanation,
                    raw_response=cleaned,
                    is_multiple_choice=True,
                    is_unlabelled_mcq=is_unlabelled_mcq,
                    code_snippet=code_snip,
                    code_language=code_lang,
                    question_type=mcq_type,
                    direct_answer=opt_content
                )
            else:
                err_msg = (
                    f"Model proposed option '{proposed}', which does not exist in valid choices {list(options.keys())}."
                    if proposed else
                    f"Model output could not be deterministically parsed into an option in {list(options.keys())}."
                )
                return AnswerResult(
                    source_option_label="Uncertain",
                    option_text="",
                    answer_option="Uncertain",
                    proposed_option=proposed,
                    is_validated=False,
                    validation_status="hallucination_rejected" if proposed else "uncertain",
                    confidence=0.0,
                    confidence_metadata={
                        "score": 0.0,
                        "calibrated": False,
                        "validation_type": "rejected",
                        "disclaimer": "Schema validation rejected model output as ungrounded or absent."
                    },
                    explanation=f"Uncertain: {err_msg}\n\nRaw output:\n{cleaned}",
                    raw_response=cleaned,
                    error=err_msg,
                    is_multiple_choice=True,
                    is_unlabelled_mcq=is_unlabelled_mcq,
                    code_snippet=code_snip,
                    code_language=code_lang,
                    question_type="unknown",
                    direct_answer=""
                )

        # CASE 2: Open-ended question without multiple-choice options
        lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
        if lines:
            short_ans = lines[0]
            short_ans = re.sub(r"^(?:ANSWER|Answer)\s*[:\-]?\s*", "", short_ans).strip()
            explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else short_ans
            
            # Detect question type
            m_tf = re.match(r"^(true|false|yes|no)\b", short_ans, re.IGNORECASE)
            if code_snip:
                q_type = "code"
                source_label = "Code"
            elif m_tf or question_type == "true_false":
                q_type = "true_false"
                val_tf = "True" if ((m_tf and m_tf.group(1).lower() in ("true", "yes")) or ("true" in short_ans.lower() and "false" not in short_ans.lower())) else "False"
                short_ans = val_tf
                source_label = val_tf
            elif question_type == "numerical" or re.search(r"^\s*([a-zA-Z]\s*=\s*|[-+]?\d*\.?\d+)", short_ans):
                q_type = "numerical"
                source_label = "✓"
                # Check deterministic math calculation
                det_ans, det_num = try_solve_deterministic_math(question_text)
                if det_ans:
                    short_ans = det_ans
                    explanation = f"Calculated: {det_ans}\n{explanation}"
            elif "fill in" in cleaned.lower() or "blank" in cleaned.lower():
                q_type = "fill_blank"
                source_label = "✓"
            else:
                q_type = "theory"
                source_label = "✓"

            return AnswerResult(
                source_option_label=source_label,
                option_text=short_ans[:100],
                answer_option=short_ans[:100],
                proposed_option=short_ans[:100],
                is_validated=True,
                validation_status="open_ended_factual",
                confidence=0.85,
                confidence_metadata={
                    "score": 0.85,
                    "calibrated": False,
                    "validation_type": "open_ended_heuristic",
                    "disclaimer": "Factual heuristic without multiple-choice verification."
                },
                explanation=explanation,
                raw_response=cleaned,
                is_multiple_choice=False,
                is_unlabelled_mcq=False,
                code_snippet=code_snip,
                code_language=code_lang,
                question_type=q_type,
                direct_answer=short_ans
            )

        return AnswerResult(
            source_option_label="Uncertain",
            option_text="",
            answer_option="Uncertain",
            proposed_option=None,
            is_validated=False,
            validation_status="uncertain",
            confidence=0.0,
            confidence_metadata={"score": 0.0, "calibrated": False},
            explanation="Could not extract an answer from model response.",
            raw_response=cleaned,
            error="Empty parsed lines",
            is_multiple_choice=False,
            is_unlabelled_mcq=False,
            code_snippet=None,
            code_language="",
            question_type="unknown",
            direct_answer=""
        )

