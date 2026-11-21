import os
import sys
import time
import subprocess
import shutil
import urllib.request
from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
backend_path = os.path.join(ROOT_DIR, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
db_file = os.path.join(ROOT_DIR, "decidr.db").replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
os.chdir(ROOT_DIR)

def log(msg: str):
    print(msg, flush=True)

def wait_for_url(url: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status in (200, 304, 404):
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def record_demo():
    log("=" * 60)
    log("Decidr End-to-End Demo Video Recorder")
    log("=" * 60)

    # 1. Reset demo state
    log("[1/5] Resetting demo state with scripts/demo_reset.py...")
    from scripts.demo_reset import run_demo_reset
    run_demo_reset()

    backend_proc = None
    frontend_proc = None

    try:
        # 2. Check or start backend
        log("[2/5] Ensuring backend server is running on http://localhost:8000...")
        if not wait_for_url("http://localhost:8000/health", timeout=2):
            log("Starting FastAPI backend on port 8000...")
            python_bin = sys.executable
            backend_env = os.environ.copy()
            backend_env["PYTHONPATH"] = os.path.join(ROOT_DIR, "backend")
            backend_proc = subprocess.Popen(
                [python_bin, "-m", "uvicorn", "app.main:app", "--port", "8000"],
                cwd=os.path.join(ROOT_DIR, "backend"),
                env=backend_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if not wait_for_url("http://localhost:8000/health", timeout=15):
                out, err = backend_proc.communicate(timeout=2) if backend_proc.poll() is not None else ("unknown", "unknown")
                log(f"Backend stdout: {out}")
                log(f"Backend stderr: {err}")
                raise RuntimeError("Backend failed to start on http://localhost:8000")
            log("Backend running.")
        else:
            log("Backend is already running.")

        # 3. Check or start frontend
        log("[3/5] Ensuring frontend server is running on http://localhost:3000...")
        if not wait_for_url("http://localhost:3000", timeout=2):
            log("Starting Next.js frontend on port 3000...")
            frontend_proc = subprocess.Popen(
                "npx next start -p 3000",
                cwd=os.path.join(ROOT_DIR, "frontend"),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if not wait_for_url("http://localhost:3000", timeout=20):
                log("Production start timed out, falling back to next dev...")
                if frontend_proc:
                    try:
                        frontend_proc.terminate()
                    except Exception:
                        pass
                frontend_proc = subprocess.Popen(
                    "npx next dev -p 3000",
                    cwd=os.path.join(ROOT_DIR, "frontend"),
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if not wait_for_url("http://localhost:3000", timeout=25):
                    out, err = frontend_proc.communicate(timeout=2) if frontend_proc.poll() is not None else ("unknown", "unknown")
                    log(f"Frontend stdout: {out}")
                    log(f"Frontend stderr: {err}")
                    raise RuntimeError("Frontend failed to start on http://localhost:3000")
            log("Frontend running.")
        else:
            log("Frontend is already running.")

        # 4. Launch Playwright & Drive Demo
        log("[4/5] Launching Playwright Chromium with video recording...")
        temp_video_dir = os.path.join(ROOT_DIR, "docs", "raw_video")
        os.makedirs(temp_video_dir, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir=temp_video_dir,
                record_video_size={"width": 1280, "height": 720},
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            page.on("console", lambda msg: log(f"  [Browser Console] {msg.type}: {msg.text}"))
            page.on("pageerror", lambda err: log(f"  [Browser Error] {err}"))

            # --- Scene 1: Home / Meetings Overview (0:00 - 0:25) ---
            log("  -> Scene 1: Home & Meetings List")
            page.goto("http://localhost:3000/", wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            log(f"Page title: {page.title()}")

            # --- Scene 2: Process Meeting 2 (0:25 - 0:50) ---
            log("  -> Scene 2: Processing Meeting 2")
            process_btn = page.locator("button:has-text('Process')").first
            try:
                if process_btn.is_visible():
                    process_btn.click()
                    log("     Clicked 'Process' on Meeting 2. Waiting for extraction & watchdog...")
                    page.wait_for_timeout(6000)
                else:
                    log("     'Process' button not currently visible.")
            except Exception as e:
                log(f"     Process button note: {e}")
            page.wait_for_timeout(2500)

            # --- Scene 3: Review Queue & Premise Break Alert (0:50 - 1:25) ---
            log("  -> Scene 3: Review Queue & Premise Break Inspection")
            page.goto("http://localhost:3000/review", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Locate and show the Premise Break
            confirm_btn = page.locator("button:has-text('Confirm Break')").first
            try:
                confirm_btn.wait_for(state="visible", timeout=8000)
                page.wait_for_timeout(3500)
                log("     Clicking 'Confirm Break' on Premise Break alert...")
                confirm_btn.click()
                page.wait_for_timeout(3000)
            except Exception as e:
                log(f"     Confirm Break button note: {e}")

            # --- Scene 4: Blast Radius & Affected Work (1:25 - 2:00) ---
            log("  -> Scene 4: Affected Work & Blast Radius Analysis")
            page.goto("http://localhost:3000/affected", wait_until="domcontentloaded")
            page.wait_for_timeout(4500)

            # Inspect hours at risk and dependency chain
            # Click 'Review Repair Plan'
            repair_plan_link = page.locator("a:has-text('Review Repair Plan'), button:has-text('Review Repair Plan')").first
            try:
                repair_plan_link.wait_for(state="visible", timeout=8000)
                log("     Opening Repair Plan from Affected Work...")
                repair_plan_link.click()
                page.wait_for_timeout(3500)
            except Exception:
                page.goto("http://localhost:3000/review", wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

            # --- Scene 5: Repair Plan Approval (2:00 - 2:25) ---
            log("  -> Scene 5: Repair Plan Approval Gate")
            approve_btn = page.locator("button:has-text('Approve Selected')").first
            try:
                approve_btn.wait_for(state="visible", timeout=8000)
                page.wait_for_timeout(2500)
                log("     Clicking 'Approve Selected'...")
                approve_btn.click()
                page.wait_for_timeout(3500)
            except Exception as e:
                log(f"     Approve button note: {e}")

            # --- Scene 6: My Week & Downstream Verification (2:25 - 2:45) ---
            log("  -> Scene 6: My Week & Broken Premise Warnings")
            page.goto("http://localhost:3000/my-week", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            # --- Scene 7: Decision Ledger (2:45 - 3:00) ---
            log("  -> Scene 7: Decision Ledger & Audit Trace")
            page.goto("http://localhost:3000/ledger", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            try:
                row = page.locator("table tbody tr").first
                if row.is_visible():
                    row.click()
                    page.wait_for_timeout(3500)
            except Exception as e:
                log(f"     Ledger row note: {e}")

            # --- Scene 8: Immutable Audit Log (3:00 - 3:15) ---
            log("  -> Scene 8: Audit Log Invariant Verification")
            page.goto("http://localhost:3000/audit", wait_until="domcontentloaded")
            page.wait_for_timeout(4500)

            # Close context to flush video to disk
            context.close()
            saved_video = page.video.path()
            browser.close()

            target_video = os.path.join(ROOT_DIR, "docs", "backup-demo.webm")
            if saved_video and os.path.exists(saved_video):
                shutil.copy2(saved_video, target_video)
                log(f"[5/5] Success! Video saved to: {target_video} ({os.path.getsize(target_video)} bytes)")
            else:
                log("[5/5] Warning: Video file path was not captured properly.")
            shutil.rmtree(temp_video_dir, ignore_errors=True)

    finally:
        if backend_proc:
            log("Terminating background backend process...")
            backend_proc.terminate()
        if frontend_proc:
            log("Terminating background frontend process...")
            frontend_proc.terminate()

    log("Demo recording script finished.")

if __name__ == "__main__":
    record_demo()
