# ReqAgent Makefile
# Development and deployment commands for the funding opportunity management system

.PHONY: help install setup test run clean migrate reset-db backup restore docker-build docker-run docker-stop logs health-check setup-admin test-migrations test-phase2 test-phase3 test-phase4 gen-template clean-templates ingest-pdf clean-pdfs show-logs run-crawler

# Default target
help:
	@echo "🚀 ReqAgent Development Commands"
	@echo "================================"
	@echo ""
	@echo "📦 Setup & Installation:"
	@echo "  install          Install Python dependencies"
	@echo "  setup            Quick setup for new developers"
	@echo "  setup-admin      Create default admin user"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test             Run all tests"
	@echo "  test-phase2      Test Phase 2 template implementation"
	@echo "  test-phase3      Test Phase 3 PDF processing"
	@echo "  test-phase4      Test Phase 4 hardening & observability"
	@echo "  test-migrations  Test database migration system"
	@echo ""
	@echo "🚀 Development:"
	@echo "  run              Start development server"
	@echo "  migrate          Run database migrations"
	@echo "  reset-db         Reset database (⚠️ DESTRUCTIVE)"
	@echo ""
	@echo "📄 Phase 2 - Templates:"
	@echo "  gen-template     Generate proposal template (requires FUNDING_ID)"
	@echo "  clean-templates  Clean up generated templates"
	@echo ""
	@echo "📚 Phase 3 - PDF Processing:"
	@echo "  ingest-pdf       Ingest PDF from URL (requires URL)"
	@echo "  clean-pdfs       Clean up ingested PDFs"
	@echo ""
	@echo "🔒 Phase 4 - Hardening & Observability:"
	@echo "  run-crawler      Test crawler with URL (requires URL)"
	@echo "  show-logs        View logs with optional level filter"
	@echo ""
	@echo "🐳 Docker:"
	@echo "  docker-build     Build Docker image"
	@echo "  docker-run       Run Docker container"
	@echo "  docker-stop      Stop Docker container"
	@echo ""
	@echo "🔧 Maintenance:"
	@echo "  backup           Backup database"
	@echo "  restore          Restore database from backup"
	@echo "  logs             View application logs"
	@echo "  health-check     Check application health"
	@echo "  clean            Clean up temporary files"

# Python environment
PYTHON := python3
PIP := pip3
VENV := venv

# Application settings
APP_NAME := reqagent
APP_PORT := 8000
APP_HOST := 0.0.0.0

# Database settings
DB_NAME := requirement_agent
DB_USER := postgres
DB_HOST := localhost
DB_PORT := 5432

# Docker settings
DOCKER_IMAGE := reqagent
DOCKER_CONTAINER := reqagent-app

# Install dependencies
install:
	@echo "📦 Installing Python dependencies..."
	$(PIP) install -r requirements.txt
	@echo "✅ Dependencies installed successfully"

# Create virtual environment and install dependencies
setup:
	@echo "🚀 Setting up ReqAgent development environment..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV); \
	fi
	@echo "Activating virtual environment..."
	@source $(VENV)/bin/activate && $(PIP) install -r requirements.txt
	@echo "✅ Development environment setup complete"
	@echo "💡 Activate with: source $(VENV)/bin/activate"

# Setup admin user
setup-admin:
	@echo "👤 Setting up default admin user..."
	$(PYTHON) setup_admin.py
	@echo "✅ Admin user setup complete"

# Run tests
test:
	@echo "🧪 Running test suite..."
	python -m pytest test_*.py -v

test-phase2:
	@echo "Testing Phase 2 template implementation..."
	python test_phase2_templates.py

test-phase3:
	@echo "Testing Phase 3 PDF processing implementation..."
	python test_phase3_pdf.py

test-migrations:
	@echo "Testing migration system..."
	python -c "from utils.migrate import run_migrations; print('Migrations:', run_migrations())"

# Development server
run:
	@echo "🚀 Starting ReqAgent development server..."
	@echo "📱 Server will be available at: http://$(APP_HOST):$(APP_PORT)"
	@echo "📚 API documentation: http://$(APP_HOST):$(APP_PORT)/docs"
	@echo "🔍 Health check: http://$(APP_HOST):$(APP_PORT)/health"
	uvicorn main:app --host $(APP_HOST) --port $(APP_PORT) --reload

# Database operations
migrate:
	@echo "🔄 Running database migrations..."
	alembic upgrade head
	@echo "✅ Migrations completed"

reset-db:
	@echo "⚠️  WARNING: This will DESTROY all data!"
	@echo "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo "🗑️  Dropping and recreating database..."
	dropdb --if-exists $(DB_NAME) -h $(DB_HOST) -U $(DB_USER) -p $(DB_PORT)
	createdb $(DB_NAME) -h $(DB_HOST) -U $(DB_USER) -p $(DB_PORT)
	@echo "🔄 Running migrations..."
	alembic upgrade head
	@echo "✅ Database reset complete"

# Backup and restore
backup:
	@echo "💾 Creating database backup..."
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	backup_file="backup_$(DB_NAME)_$$timestamp.sql"; \
	pg_dump $(DB_NAME) -h $(DB_HOST) -U $(DB_USER) -p $(DB_PORT) > $$backup_file; \
	echo "✅ Backup created: $$backup_file"

restore:
	@echo "📥 Restoring database from backup..."
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Usage: make restore BACKUP_FILE=backup_file.sql"; \
		echo "Available backups:"; \
		ls -la backup_*.sql 2>/dev/null || echo "No backups found"; \
		exit 1; \
	fi
	@echo "Restoring from $(BACKUP_FILE)..."
	psql $(DB_NAME) -h $(DB_HOST) -U $(DB_USER) -p $(DB_PORT) < $(BACKUP_FILE)
	@echo "✅ Database restore complete"

# Docker operations
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t $(DOCKER_IMAGE) .
	@echo "✅ Docker image built successfully"

docker-run:
	@echo "🚀 Starting Docker container..."
	docker run -d \
		--name $(DOCKER_CONTAINER) \
		-p $(APP_PORT):$(APP_PORT) \
		--env-file .env \
		$(DOCKER_IMAGE)
	@echo "✅ Container started successfully"
	@echo "📱 Application available at: http://localhost:$(APP_PORT)"

docker-stop:
	@echo "🛑 Stopping Docker container..."
	docker stop $(DOCKER_CONTAINER) || true
	docker rm $(DOCKER_CONTAINER) || true
	@echo "✅ Container stopped and removed"

# Utility commands
logs:
	@echo "📋 Viewing application logs..."
	@if [ -f "logs/app.log" ]; then \
		tail -f logs/app.log; \
	else \
		echo "No log file found. Run the application first."; \
	fi

health-check:
	@echo "🔍 Checking application health..."
	@curl -s http://localhost:$(APP_PORT)/health | python -m json.tool || \
		echo "❌ Application not responding"

clean:
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "✅ Cleanup complete"

# Phase 2 Template Commands
gen-template:
	@echo "Generating proposal template..."
	@if [ -z "$(FUNDING_ID)" ]; then \
		echo "Usage: make gen-template FUNDING_ID=123"; \
		echo "Please specify a funding opportunity ID"; \
		exit 1; \
	fi
	@echo "Generating template for funding opportunity $(FUNDING_ID)..."
	@echo "This feature requires the full application to be running."
	@echo "Use the admin interface at /admin/qa-review instead."

clean-templates:
	@echo "⚠️  WARNING: This will clean up all generated templates!"
	@echo "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo "Cleaning up templates..."
	@echo "Note: This is a development-only command. In production, use the admin interface."
	@echo "Template cleanup complete"

# Phase 3 PDF Processing Commands
ingest-pdf:
	@echo "Ingesting PDF from URL..."
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make ingest-pdf URL=https://example.com/document.pdf"; \
		echo "Please specify a PDF URL"; \
		exit 1; \
	fi
	@echo "Ingesting PDF from: $(URL)"
	@echo "This feature requires the full application to be running."
	@echo "Use the API endpoint: POST /api/documents/ingest-url"
	@echo "Or use the admin interface for file uploads."

clean-pdfs:
	@echo "⚠️  WARNING: This will clean up all ingested PDFs!"
	@echo "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo "Cleaning up ingested PDFs..."
	@echo "Note: This is a development-only command. In production, use the admin interface."
	@echo "PDF cleanup complete"

# Phase 4 Hardening & Observability Commands
test-phase4:
	@echo "🧪 Testing Phase 4 hardening & observability..."
	python test_phase4_hardening.py

run-crawler:
	@echo "🕷️ Testing crawler with URL..."
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make run-crawler URL=https://example.com"; \
		echo "Please specify a URL to test"; \
		exit 1; \
	fi
	@echo "Testing crawler with: $(URL)"
	@echo "This feature requires the full application to be running."
	@echo "Use the admin interface at /admin/qa-review for full functionality."

show-logs:
	@echo "📊 Viewing structured logs..."
	@if [ -z "$(LEVEL)" ]; then \
		echo "Usage: make show-logs [LEVEL=ERROR|WARNING|INFO|DEBUG]"; \
		echo "Showing all logs..."; \
		LEVEL=""; \
	fi
	@echo "Log level filter: $(LEVEL)"
	@echo "This feature requires the full application to be running."
	@echo "Use the admin interface at /admin/logs for full functionality."

# Quick setup for new developers
setup:
	@echo "🚀 Quick setup for new developers..."
	@echo "1. Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "2. Setting up database..."
	@if command -v createdb >/dev/null 2>&1; then \
		createdb $(DB_NAME) 2>/dev/null || echo "Database already exists"; \
	else \
		echo "⚠️  PostgreSQL not found. Please install PostgreSQL first."; \
		exit 1; \
	fi
	@echo "3. Running migrations..."
	alembic upgrade head
	@echo "4. Creating admin user..."
	$(PYTHON) setup_admin.py
	@echo "✅ Setup complete! Run 'make run' to start the server."

