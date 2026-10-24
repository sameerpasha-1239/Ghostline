import time
import logging
from typing import Optional, Callable, Dict, Any
from PIL import Image
from pydantic import BaseModel

from .capture import capture_screen_around_cursor_with_diagnostics, get_cursor_position
from .ocr_engine import run_native_ocr, parse_question_structure, ParsedQuestion
from .llm_client import OllamaClient, AnswerResult
from .pipeline_tracer import PipelineTracer

class DuplicateQuestionError(ValueError):
    """Raised when an auto-hover solve detects the exact same question that was solved recently."""
    pass

class PipelineExecutionResult(BaseModel):
    cursor_pos: tuple
    capture_time_ms: float
    ocr_time_ms: float
    llm_time_ms: float
    total_time_ms: float
    parsed_question: ParsedQuestion
    answer_result: AnswerResult
    tracer_data: Optional[Dict[str, Any]] = None

class RubricPipeline:
    def __init__(self, ollama_client: Optional[OllamaClient] = None, model_name: str = "phi3:mini"):
        self.llm = ollama_client or OllamaClient(default_model=model_name)
        self.model_name = model_name

    def process_from_cursor(
        self,
        capture_width: int = 900,
        capture_height: int = 600,
        stream_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        is_duplicate_fn: Optional[Callable[[str], bool]] = None,
        tracer: Optional[PipelineTracer] = None
    ) -> PipelineExecutionResult:
        """
        Executes the full pipeline:
        1. Capture screen at mouse position with environment telemetry.
        2. Recognize text via Windows Native OCR.
        3. Parse question and options.
        4. Solve with local Ollama LLM.
        5. Validate result.
        """
        if tracer is None:
            tracer = PipelineTracer()
        tracer.start_trace()
        t_start = time.perf_counter()
        
        # 1. Capture Stage
        if progress_callback:
            progress_callback("capturing")
        rec_cap = tracer.begin_stage("Screen Capture")
        try:
            t0 = time.perf_counter()
            img, bbox, cap_diag = capture_screen_around_cursor_with_diagnostics(
                width=capture_width, height=capture_height
            )
            t_cap = (time.perf_counter() - t0) * 1000.0
            cursor_pos = cap_diag.get("cursor", get_cursor_position())
            tracer.end_stage(rec_cap, success=True, details={
                "bbox": bbox,
                "cursor": cursor_pos,
                "is_blank_frame": cap_diag.get("is_blank_frame", False),
                "is_capture_protected": cap_diag.get("is_capture_protected", False),
                "display_affinity": cap_diag.get("display_affinity", 0),
                "grab_method": cap_diag.get("grab_method", "unknown")
            })
        except Exception as e:
            tracer.end_stage(rec_cap, success=False, error=str(e))
            raise

        # 2. OCR Stage
        if progress_callback:
            progress_callback("recognizing")
        rec_ocr = tracer.begin_stage("OCR")
        try:
            t0 = time.perf_counter()
            ocr_data = run_native_ocr(img)
            t_ocr = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_ocr, success=True, details={
                "lines_count": len(ocr_data.get("lines", [])),
                "char_count": len(ocr_data.get("text", ""))
            })
        except Exception as e:
            tracer.end_stage(rec_ocr, success=False, error=str(e))
            raise

        # 3. Question Extraction Stage
        rec_parse = tracer.begin_stage("Question Extraction")
        try:
            parsed_q = parse_question_structure(ocr_data)
            parse_details = {
                "is_valid": parsed_q.is_valid_question,
                "is_mcq": parsed_q.is_multiple_choice,
                "is_unlabelled": parsed_q.is_unlabelled_mcq,
                "options_count": len(parsed_q.options),
                "validation_reason": parsed_q.validation_reason,
                "question_length": len(parsed_q.question_text)
            }
            if not parsed_q.question_text.strip() or not parsed_q.is_valid_question:
                reason = parsed_q.validation_reason or "Empty or invalid question text."
                tracer.end_stage(rec_parse, success=False, details=parse_details, error=reason)
                logging.warning("[Pipeline Tracer] Question rejected: %s", reason)
                raise ValueError(f"Unreliable question extraction: {reason}")
            tracer.end_stage(rec_parse, success=True, details=parse_details)
        except Exception as e:
            if not rec_parse.end_time:
                tracer.end_stage(rec_parse, success=False, error=str(e))
            raise

        # Check duplicate question cache for auto-hover
        if is_duplicate_fn and is_duplicate_fn(parsed_q.question_text):
            logging.info("[Pipeline Tracer] Detected duplicate question within TTL. Skipping LLM.")
            raise DuplicateQuestionError(f"Duplicate question detected: {parsed_q.question_text[:50]}")

        # 4. LLM Solve Stage
        if progress_callback:
            progress_callback("thinking")
        rec_llm = tracer.begin_stage("Answer Generation", {"model": self.model_name})
        try:
            t0 = time.perf_counter()
            answer = self.llm.solve_question(
                question_text=parsed_q.question_text,
                options=parsed_q.options if parsed_q.is_multiple_choice else None,
                model=self.model_name,
                stream_callback=stream_callback,
                is_unlabelled_mcq=parsed_q.is_unlabelled_mcq
            )
            t_llm = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_llm, success=True, details={
                "is_validated": answer.is_validated,
                "badge": answer.tray_badge,
                "has_code": bool(getattr(answer, "code_snippet", None))
            })
        except Exception as e:
            tracer.end_stage(rec_llm, success=False, error=str(e))
            raise

        # 5. Validation Stage
        rec_val = tracer.begin_stage("Validation")
        tracer.end_stage(rec_val, success=answer.is_validated, details={
            "is_validated": answer.is_validated,
            "tray_badge": answer.tray_badge,
            "error": answer.error
        })

        t_total = (time.perf_counter() - t_start) * 1000.0

        return PipelineExecutionResult(
            cursor_pos=cursor_pos,
            capture_time_ms=t_cap,
            ocr_time_ms=t_ocr,
            llm_time_ms=t_llm,
            total_time_ms=t_total,
            parsed_question=parsed_q,
            answer_result=answer,
            tracer_data=tracer.to_dict()
        )

    def process_from_image(
        self,
        image: Image.Image,
        stream_callback: Optional[Callable[[str], None]] = None,
        tracer: Optional[PipelineTracer] = None
    ) -> PipelineExecutionResult:
        """Processes a static image for testing or headless pipelines."""
        if tracer is None:
            tracer = PipelineTracer()
        tracer.start_trace()
        t_start = time.perf_counter()
        
        rec_ocr = tracer.begin_stage("OCR")
        try:
            t0 = time.perf_counter()
            ocr_data = run_native_ocr(image)
            t_ocr = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_ocr, success=True, details={
                "lines_count": len(ocr_data.get("lines", []))
            })
        except Exception as e:
            tracer.end_stage(rec_ocr, success=False, error=str(e))
            raise

        rec_parse = tracer.begin_stage("Question Extraction")
        try:
            parsed_q = parse_question_structure(ocr_data)
            if not parsed_q.question_text.strip() or not parsed_q.is_valid_question:
                reason = parsed_q.validation_reason or "No readable question detected in image."
                tracer.end_stage(rec_parse, success=False, error=reason)
                raise ValueError(f"No readable question detected in image: {reason}")
            tracer.end_stage(rec_parse, success=True, details={
                "is_mcq": parsed_q.is_multiple_choice,
                "options_count": len(parsed_q.options)
            })
        except Exception as e:
            if not rec_parse.end_time:
                tracer.end_stage(rec_parse, success=False, error=str(e))
            raise

        rec_llm = tracer.begin_stage("Answer Generation")
        try:
            t0 = time.perf_counter()
            answer = self.llm.solve_question(
                question_text=parsed_q.question_text,
                options=parsed_q.options if parsed_q.is_multiple_choice else None,
                model=self.model_name,
                stream_callback=stream_callback,
                is_unlabelled_mcq=parsed_q.is_unlabelled_mcq
            )
            t_llm = (time.perf_counter() - t0) * 1000.0
            tracer.end_stage(rec_llm, success=True, details={
                "is_validated": answer.is_validated,
                "badge": answer.tray_badge
            })
        except Exception as e:
            tracer.end_stage(rec_llm, success=False, error=str(e))
            raise

        rec_val = tracer.begin_stage("Validation")
        tracer.end_stage(rec_val, success=answer.is_validated)

        t_total = (time.perf_counter() - t_start) * 1000.0

        return PipelineExecutionResult(
            cursor_pos=(0, 0),
            capture_time_ms=0.0,
            ocr_time_ms=t_ocr,
            llm_time_ms=t_llm,
            total_time_ms=t_total,
            parsed_question=parsed_q,
            answer_result=answer,
            tracer_data=tracer.to_dict()
        )

