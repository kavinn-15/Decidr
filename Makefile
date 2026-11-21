.PHONY: dev test seed reset demo-reset eval record-demo

dev:
	@powershell -Command "Start-Process powershell -ArgumentList 'cd backend; ..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000'; cd frontend; npm run dev"

test:
	@powershell -Command ".venv\Scripts\pytest.exe backend\tests -v"

seed:
	@powershell -Command ".venv\Scripts\python.exe scripts\seed.py"

reset:
	@powershell -Command ".venv\Scripts\python.exe scripts\reset_db.py; Write-Host 'Reset complete.'"

demo-reset:
	@powershell -Command ".venv\Scripts\python.exe scripts\demo_reset.py; Write-Host 'Demo reset complete.'"

eval:
	@powershell -Command ".venv\Scripts\python.exe backend\eval\run_eval.py"

record-demo:
	@powershell -Command ".venv\Scripts\python.exe scripts\record_demo.py"

