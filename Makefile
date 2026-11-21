.PHONY: dev test seed reset eval

dev:
	@powershell -Command "Start-Process powershell -ArgumentList 'cd backend; ..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000'; cd frontend; npm run dev"

test:
	@powershell -Command ".venv\Scripts\pytest.exe backend\tests -v"

seed:
	@powershell -Command ".venv\Scripts\python.exe scripts\seed.py"

reset:
	@powershell -Command ".venv\Scripts\python.exe scripts\reset_db.py; Remove-Item -Path .llm_cache\* -Force -ErrorAction SilentlyContinue; Write-Host 'Reset complete.'"

eval:
	@powershell -Command ".venv\Scripts\python.exe -m app.eval"
