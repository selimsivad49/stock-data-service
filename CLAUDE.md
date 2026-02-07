# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Stock Data Service - an enterprise-ready FastAPI microservice for managing stock price and financial data using yfinance as the data source. The service features JWT/API key authentication, role-based access control, rate limiting, and comprehensive monitoring capabilities.

## Development Commands

### Environment Setup
```bash
# Development environment (default)
cp .env.dev .env
docker-compose up -d

# Production environment  
ENVIRONMENT=production docker-compose -f docker-compose.prod.yml up -d

# Test environment
cp .env.test .env
```

### Service Management
```bash
# Start services with logs
docker-compose up -d && docker-compose logs -f web

# Rebuild and restart
docker-compose down && docker-compose up --build -d

# Check health status
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

### Database Operations
```bash
# Backup database (all data)
./scripts/backup_data.sh

# Backup stock data only (exclude users/api_keys)
./scripts/backup_data.sh data

# Restore database from backup (merge mode - default)
./scripts/restore_data.sh stock_data_migration_YYYYMMDD_HHMMSS.tar.gz

# Restore database from backup (replace mode - drop existing data)
./scripts/restore_data.sh stock_data_migration_YYYYMMDD_HHMMSS.tar.gz replace

# Windows
scripts\backup_data.bat
scripts\restore_data.bat stock_data_migration_YYYYMMDD_HHMMSS.tar.gz

# Access MongoDB directly
docker-compose exec mongo mongosh -u admin -p password --authenticationDatabase admin stock_data
```

### Development Workflow
```bash
# Run local development (without Docker)
pip install -r requirements.txt
uvicorn app.main:app --reload

# Connect to MongoDB (Docker)
docker-compose up -d mongo

# View application logs
docker-compose logs -f web

# Monitor system metrics
curl http://localhost:8000/api/monitoring/metrics
```

## Architecture Overview

### Core Components

**FastAPI Application (`app/main.py`)**
- Main application entry point with lifespan management
- Middleware stack: Security, Logging, Authentication
- Router registration for all API endpoints
- Comprehensive health check endpoint

**Authentication & Authorization System**
- `app/services/auth_service.py`: JWT token management and password hashing
- `app/services/api_key_service.py`: API key generation and validation
- `app/middleware/auth_middleware.py`: Authentication dependency injection with role/scope checking
- `app/services/rate_limit_service.py`: Per-user/API-key rate limiting with cache-based tracking

**Data Management Layer**
- `app/services/data_manager.py`: Orchestrates automatic data fetching from yfinance when data is missing
- `app/services/stock_service.py`: Direct database CRUD operations
- `app/services/yfinance_service.py`: yfinance API integration with rate limiting and error handling
- `app/services/cache_service.py`: In-memory caching with TTL management

**API Endpoints Structure**
- `/api/auth/*`: User authentication, registration, API key management
- `/api/users/*`: User management (admin only)
- `/api/stocks/*`: Stock data and info endpoints with automatic data fetching
- `/api/admin/*`: System administration functions
- `/api/monitoring/*`: Health checks and metrics

### Data Flow Architecture

1. **Request Authentication**: All requests pass through authentication middleware that validates JWT tokens or API keys
2. **Rate Limiting**: Rate limits applied based on user role, API key, or IP address
3. **Data Retrieval**: DataManager checks cache → database → yfinance (automatic fallback)
4. **Response Caching**: Successful responses cached with appropriate TTL values

### Database Schema (MongoDB)

**Collections with optimized indexes:**
- `users`: User accounts with authentication data
- `api_keys`: API key management with expiration
- `daily_prices`: Stock daily price data with symbol+date unique index
- `stock_info`: Company information with text search capabilities
- `financials`: Financial statements with period-based indexing

### Environment Configuration

**Environment-specific settings** (`.env.dev`, `.env.prod`, `.env.test`):
- MongoDB connection strings and credentials
- JWT secrets and token expiration settings
- Rate limiting configurations per environment
- Cache TTL values (disabled in test, extended in production)
- Logging levels and yfinance timeout settings

### Security Features

**Multi-layer Security Implementation:**
- JWT authentication with configurable expiration
- API key authentication for external clients  
- Role-based access control (admin/user/readonly)
- Rate limiting at multiple levels (user, API key, IP)
- Security headers (CORS, CSP, XSS protection)
- bcrypt password hashing with strength validation

### Docker Architecture

**Multi-stage Dockerfile:**
- Base stage with Python 3.11 and dependencies
- Production stage with optimized image size
- Development stage with hot reload support

**Production Stack (docker-compose.prod.yml):**
- Nginx reverse proxy with rate limiting
- FastAPI application with resource limits
- MongoDB with persistent data volumes
- Automated backup system

## Key Implementation Patterns

### Authentication Context Pattern
All protected endpoints use dependency injection to get authentication context:
```python
auth_context: AuthContext = Depends(require_read_access)
# or
auth_context: AuthContext = Depends(require_write_access)
```

### Automatic Data Fetching Pattern
Data endpoints use DataManager for intelligent data retrieval:
```python
# Checks cache → database → yfinance automatically
data = await data_manager.get_daily_prices_with_auto_fetch(symbol, ...)
```

### Error Handling Pattern
Standardized error responses across all endpoints:
```python
raise HTTPException(status_code=404, detail={
    "error": {
        "code": "STOCK_NOT_FOUND",
        "message": "指定された銘柄が見つかりません",
        "details": {"symbol": symbol}
    }
})
```

### Service Layer Pattern
All business logic encapsulated in service classes:
- Database operations in `*_service.py`
- External API calls in dedicated service classes
- Middleware for cross-cutting concerns

## Configuration Management

**Settings loaded via environment variables** (`app/config/settings.py`):
- Automatic environment detection (development/production/test)
- Environment-specific configuration file loading
- Default values with production overrides
- Type validation and environment property helpers

## Important Notes

- **Default Admin User**: Created during database initialization (username: `admin`, password: `admin123` - change in production)
- **Rate Limiting**: Implemented at application level, not dependent on external services
- **Japanese Stock Support**: Prioritized with `.T` suffix handling for Tokyo Stock Exchange
- **Caching Strategy**: Multi-level caching (in-memory → database → external API)
- **MongoDB Indexes**: Optimized for stock symbol and date-based queries
- **Environment Isolation**: Complete separation between dev/prod/test environments

## API Documentation

- Swagger UI available at `/docs` when running
- Complete API specification in `API_DOCUMENTATION.md`
- All endpoints support both JWT and API key authentication (except public endpoints)