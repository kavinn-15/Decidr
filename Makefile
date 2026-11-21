.PHONY: dev test seed reset eval

dev:
	@powershell -Command "Start-Process powershell -ArgumentList 'cd backend; ..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000'; cd frontend; npm run dev"

test:
	@powershell -Command "cd backend; ..\.venv\Scripts\pytest.exe -v"

seed:
	@powershell -Command "cd backend; ..\.venv\Scripts\python.exe -m app.db.seed"

reset:
	@powershell -Command "Remove-Item -Path decidr.db, backend\decidr.db, .llm_cache\* -Force -ErrorAction SilentlyContinue; Write-Host 'Reset complete.'"

eval:
	@powershell -Command "cd backend; ..\.venv\Scripts\python.exe -m app.eval"
