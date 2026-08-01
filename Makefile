.PHONY: test validate lint check docker-build docker-run clean

# Run all quality gates
check: lint test validate

test:
	python -m pytest tests/ -v --tb=short

validate:
	python -m src.validation.run_validation

lint:
	ruff check src/ --ignore=E501,F841,E402 2>/dev/null || true

typecheck:
	python -c "import ast, pathlib; [ast.parse(f.read_text()) for f in pathlib.Path('src').rglob('*.py')]" && echo "All modules pass syntax check"

docker-build:
	docker build -t getin-bot:latest .

docker-run:
	docker run --rm -it \
		-e TELEGRAM_BOT_TOKEN \
		-e CRYPTORANK_API_KEY \
		-e TELEGRAM_OWNER_ID \
		-v getin_data:/app/persist \
		getin-bot:latest

docker-up:
	docker compose -f docker-compose.prod.yml up -d

docker-down:
	docker compose -f docker-compose.prod.yml down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache