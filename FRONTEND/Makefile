.PHONY: up down dev ingest test test-frontend test-e2e clean

up:
	docker compose up -d

down:
	docker compose down

dev:
	cd frontend && npm run dev

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

ingest:
	python3 -m ingestion.run_all

test: test-frontend test-backend

test-frontend:
	cd frontend && npm run build

test-backend:
	pytest backend/tests

test-e2e:
	cd frontend && npx playwright test

clean:
	rm -rf frontend/node_modules frontend/dist
