.PHONY: install backend frontend test

install:
	python3.12 -m venv .venv && .venv/bin/pip install -q -r backend/requirements.txt -r backend/requirements-dev.txt
	cd frontend && npm install

backend:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && ../.venv/bin/python -m pytest -q
