import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add rubric_local_app to sys.path
app_root = Path(__file__).resolve().parent.parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

from rubric_local.core.pipeline import RubricPipeline
from rubric_local.ui.tray_indicator import TrayIndicator
from rubric_local.ui.caps_indicator import CapsLockIndicator

def run_numeric_e2e():
    print("=" * 65)
    print("  Phase 5 End-to-End Live Verification: Numeric Option Labels (1-4)")
    print("=" * 65)

    # 1. Generate rendered image containing a numeric multiple-choice question
    w, h = 800, 300
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
        font_opt = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
        font_opt = font

    # Question and numbered options 1 to 4
    draw.text((30, 30), "Question: What is 15 + 27 in standard arithmetic?", fill=(0, 0, 0), font=font)
    draw.text((30, 80), "1. 32", fill=(0, 0, 0), font=font_opt)
    draw.text((30, 120), "2. 40", fill=(0, 0, 0), font=font_opt)
    draw.text((30, 160), "3. 42", fill=(0, 0, 0), font=font_opt)
    draw.text((30, 200), "4. 52", fill=(0, 0, 0), font=font_opt)

    print("[*] Generated synthetic test question with numeric options 1..4.")
    
    # 2. Run through full RubricPipeline
    pipeline = RubricPipeline(model_name="phi3:mini")
    res = pipeline.process_from_image(img)

    ans = res.answer_result
    print("\n--- Pipeline Execution Output ---")
    print(f"[*] Raw Model Response: {ans.raw_response.strip()[:100]}...")
    print(f"[*] Validated: {ans.is_validated}")
    print(f"[*] Source Option Label: '{ans.source_option_label}'")
    print(f"[*] Option Text: '{ans.option_text}'")
    print(f"[*] Explanation: '{ans.explanation}'")
    print(f"[*] Confidence Metadata: {ans.confidence_metadata}")

    # 3. Assertions
    assert ans.is_validated, "Answer must be validated"
    assert ans.source_option_label == "3", f"Expected label '3', got '{ans.source_option_label}' (MUST NOT BE 'C'!)"
    assert "42" in ans.option_text, f"Expected option text to contain '42', got '{ans.option_text}'"
    print("\n[+] Verification Check: Answer label is '3' and NOT 'C'. (PASSED)")

    # 4. Tray Indicator consistency
    tray = TrayIndicator()
    badge_img = tray.create_image(ans.source_option_label, status="normal")
    assert badge_img.size == (32, 32)
    print(f"[+] Verification Check: Tray badge image rendered with glyph '{ans.source_option_label}'. (PASSED)")

    # 5. Caps Lock Indicator live test
    caps = CapsLockIndicator(enabled=True, pulse_ms=80, gap_ms=80)
    initial_caps = caps.get_caps_state()
    print(f"[*] Caps Lock initial state: {'ON' if initial_caps else 'OFF'}")
    print(f"[*] Pulsing {caps.label_to_pulse_count(ans.source_option_label)} times for answer '{ans.source_option_label}'...")

    caps.pulse(ans.source_option_label)
    time.sleep(1.0) # Wait for pulses to complete

    final_caps = caps.get_caps_state()
    print(f"[*] Caps Lock final state: {'ON' if final_caps else 'OFF'}")
    assert initial_caps == final_caps, f"Caps Lock state changed from {initial_caps} to {final_caps}!"
    print("[+] Verification Check: Caps Lock state restored with 0 drift. (PASSED)")

    print("\n" + "=" * 65)
    print("  ALL NUMERIC E2E VERIFICATION CHECKS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_numeric_e2e()
