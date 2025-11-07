# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CLICK** is a HoReCa (Hotel, Restaurant, Catering) recruitment platform consisting of:
- **FastAPI Backend** - REST API with MongoDB (Beanie ODM)
- **Telegram Bot** - Main user interface (aiogram 3.x)
- **Telegram Channels** - Automatic job posting and resume publication
- **Analytics & Recommendations** - ML-based candidate-vacancy matching

## Quick Commands

### Development
```bash
# Start all services with Docker
make docker-up          # or: docker-compose up -d

# Local development
make install            # Install dependencies
make dev               # Run backend with hot reload (port 8000)
python -m bot.main     # Run Telegram bot separately

# Only databases (for local development)
docker-compose up mongodb redis -d
```

### Testing
```bash
make test              # Run pytest with coverage
pytest tests/test_users.py              # Run specific test
pytest --cov=backend --cov=bot          # Generate coverage report
```

### Code Quality
```bash
make lint              # flake8 + mypy
make format            # black + isort
make clean             # Remove cache files
```

### Docker Management
```bash
make docker-down       # Stop containers
make docker-logs       # View logs
make docker-rebuild    # Rebuild from scratch
docker-compose logs -f bot      # Bot logs only
docker-compose logs -f backend  # Backend logs only
```

## Architecture

### Three-Layer Structure

1. **Backend (FastAPI)** - `backend/`
   - Entry point: `backend/main.py`
   - Models: Beanie ODM documents (User, Resume, Vacancy, Response, Publication, Analytics)
   - API Routes: RESTful endpoints under `/api/v1/`
   - Services: Business logic (TelegramPublisher, NotificationService, AnalyticsService, RecommendationService)
   - Database: MongoDB connection via Motor (async driver)

2. **Telegram Bot (aiogram 3.x)** - `bot/`
   - Entry point: `bot/main.py`
   - Handlers: Split by role (applicant/, employer/, common/)
   - States: FSM states for resume/vacancy creation (aiogram FSM)
   - Keyboards: Inline/reply keyboards
   - Storage: Redis for FSM state persistence

3. **Shared** - `shared/`
   - Constants: Positions (60+), skills, cuisines, work schedules, enums
   - Utils: Common utilities used by both backend and bot

### Key Design Patterns

**FSM-Based Wizards**: Resume and vacancy creation use multi-step FSM flows
- Resume: `resume_creation.py` → `resume_completion.py` → `resume_finalize.py`
- Vacancy: `vacancy_creation.py` → `vacancy_completion.py` → `vacancy_finalize.py`

**Service Layer**: Business logic separated from API/handlers
- `TelegramPublisher`: Auto-publishes to channels based on position category
- `NotificationService`: Sends Telegram notifications to users
- `AnalyticsService`: Tracks views, responses, conversions
- `RecommendationService`: ML-based matching (position, skills, location, salary)

**API-Bot Communication**: Bot calls backend API for all data operations
- Bot handles user interaction and FSM state
- Backend handles data persistence and business logic
- Services in backend can be called from both API routes and bot handlers

## Important Workflows

### Resume Publication Flow
1. User completes resume via bot FSM → `bot/handlers/applicant/resume_finalize.py`
2. Bot sends data to backend API → `POST /api/v1/resumes`
3. Backend creates Resume document in MongoDB
4. `TelegramPublisher.publish_resume()` posts to appropriate channel based on position category
5. Creates `Publication` record with message_id and channel info
6. Bot notifies user of successful publication

### Vacancy Publication Flow
1. Employer completes vacancy via bot FSM → `bot/handlers/employer/vacancy_finalize.py`
2. Bot sends to backend → `POST /api/v1/vacancies`
3. Backend creates Vacancy document
4. `TelegramPublisher.publish_vacancy()` posts to channel
5. Publication record created
6. Notification sent to employer

### Job Application Flow
1. Applicant searches vacancies → `bot/handlers/applicant/vacancy_search.py`
2. User clicks "Apply" → selects resume + cover letter
3. Bot creates Response → `POST /api/v1/responses`
4. Employer gets notification via `NotificationService`
5. Employer reviews in response_management → `bot/handlers/employer/response_management.py`
6. Status updates (viewed, accepted, rejected, invited) trigger notifications back to applicant

### Recommendation System
- **Algorithm**: 0-100 score based on weighted criteria
  - Position match: 30% (15% for partial match)
  - Skills overlap: 25% (proportional to matches)
  - Location match: 15% (10% if willing to relocate)
  - Salary compatibility: 15% (10% if within ±10-20%)
  - Experience level: 10% (graduated scoring)
  - Education match: 5%
- API: `GET /api/v1/recommendations/vacancies-for-resume/{resume_id}`
- Bot: Shows top matches with match_details explaining the score

## Configuration

### Environment Variables (.env)
Required:
- `BOT_TOKEN` - Get from @BotFather
- `SECRET_KEY` - Random 32+ char string for JWT
- `MONGODB_URL` - Default: `mongodb://mongodb:27017` (Docker) or `mongodb://localhost:27017` (local)
- `REDIS_HOST` - Default: `redis` (Docker) or `localhost` (local)

Telegram Channels (16 total):
- `CHANNEL_VACANCIES_*` - 8 channels for job postings by category
- `CHANNEL_RESUMES_*` - 8 channels for resume postings by category
- Categories: BARMEN, WAITERS, COOKS, BARISTA, ADMIN, SUPPORT, OTHER, GENERAL

### Settings Module (`config/settings.py`)
- Uses Pydantic Settings V2 for type-safe config
- Auto-loads from `.env` file
- Properties: `redis_url`, `is_production`, `is_development`

## Database Collections

### users
- Indexed: `telegram_id` (unique), `role`, `created_at`
- Fields: Telegram info, role (applicant/employer), contacts, company data (for employers)

### resumes
- Fields: Personal info, position, salary, experience (list of WorkExperience), education, skills, languages
- Status: draft, published, archived
- Analytics: views_count, responses_count

### vacancies
- Fields: Company info, position, location, salary, requirements, conditions, benefits
- Status: draft, published, active, paused, archived
- Analytics: views_count, responses_count

### responses
- Links: applicant_id, resume_id, vacancy_id, employer_id
- Type: application (from applicant), invitation (from employer)
- Status: pending, viewed, accepted, rejected, invited
- Fields: cover_letter, employer_message, status_updated_at

### publications
- Tracks Telegram channel posts
- Fields: entity_id, entity_type (resume/vacancy), channel, message_id, is_published

### analytics
- Stores view/response events for metrics
- Used by AnalyticsService for detailed statistics

## Constants and Enums

All in `shared/constants/`:

**Position Categories** (`PositionCategory` enum):
- BARMAN (9 specializations)
- WAITER (6 specializations)
- COOK (9 specializations + 19 cuisine types)
- BARISTA (6 specializations)
- MANAGEMENT (18 positions)
- SUPPORT (8 positions)

**Statuses**:
- `UserRole`: APPLICANT, EMPLOYER, MANAGER
- `ResumeStatus`: draft, published, archived
- `VacancyStatus`: draft, published, active, paused, archived
- `ResponseStatus`: pending, viewed, accepted, rejected, invited

**Other Constants**:
- `WORK_SCHEDULES`: Full-time, part-time, shifts, flexible, etc.
- `EMPLOYMENT_TYPES`: Full employment, contract, project-based, etc.
- `BENEFITS`: Free meals, tips, housing, transport, etc.
- `MAJOR_CITIES`: Moscow, St. Petersburg, etc.

## Bot Handler Organization

### Applicant Handlers (`bot/handlers/applicant/`)
- `resume_creation.py` - FSM: name, city, contacts
- `resume_completion.py` - FSM: position, salary, experience, education, skills
- `resume_finalize.py` - Preview, edit, publish
- `resume_handlers.py` - View my resumes, responses
- `vacancy_search.py` - Search jobs, apply with cover letter
- `recommendations.py` - Get recommended vacancies based on resume

### Employer Handlers (`bot/handlers/employer/`)
- `vacancy_creation.py` - FSM: position, company info, location
- `vacancy_completion.py` - FSM: salary, requirements, conditions, benefits
- `vacancy_finalize.py` - Preview, edit, publish
- `vacancy_handlers.py` - Manage vacancies
- `resume_search.py` - Search candidates, invite to job
- `response_management.py` - Review applications, accept/reject/invite
- `recommendations.py` - Get recommended candidates for vacancy

### Common Handlers (`bot/handlers/common/`)
- `start.py` - /start command, role selection
- `help_handler.py` - /help command
- `statistics.py` - User analytics dashboard

## Testing

### Test Structure
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests

### Testing Telegram Channels
See `docs/TESTING.md` for detailed guide. Quick steps:
1. Create test channel in Telegram
2. Add bot as admin with "Post Messages" permission
3. Update all `CHANNEL_*` variables in `.env` to your test channel
4. Restart: `docker-compose restart`
5. Create and publish a resume/vacancy to verify

**Troubleshooting Channels**:
- Check bot is admin: Channel info → Administrators
- Check permissions: Bot must have "Post Messages" enabled
- Check logs: `docker-compose logs backend | grep "publish"`
- For private channels: Use chat_id (e.g., `-1001234567890`) instead of `@username`

## API Endpoints

Base: `/api/v1/`

**Health**: `/health`, `/health/detailed`, `/ping`

**Users**: CRUD + `/users/telegram/{telegram_id}`

**Resumes**: CRUD + `/resumes/search?q=keyword`, `/resumes/{id}/publish`, `/resumes/{id}/archive`

**Vacancies**: CRUD + `/vacancies/search?q=keyword`, `/vacancies/{id}/publish`, `/vacancies/{id}/pause`, `/vacancies/{id}/analytics`

**Responses**:
- `POST /responses` - Create application
- `POST /responses/invitation` - Invite candidate
- `GET /responses/vacancy/{vacancy_id}` - Applications for vacancy
- `GET /responses/applicant/{applicant_id}` - User's applications
- `PATCH /responses/{id}/status` - Update status (triggers notification)

**Analytics**:
- `GET /analytics/my-statistics` - User overview (views, responses, conversions)
- `GET /analytics/vacancy/{vacancy_id}` - Detailed vacancy metrics
- `GET /analytics/resume/{resume_id}` - Detailed resume metrics
- `GET /analytics/trending-positions?limit=10` - Market trends

**Recommendations**:
- `GET /recommendations/vacancies-for-resume/{resume_id}?limit=10&min_score=40`
- `GET /recommendations/resumes-for-vacancy/{vacancy_id}?limit=10&min_score=40`
- `GET /recommendations/match-score/{resume_id}/{vacancy_id}` - Calculate compatibility

**Docs**: http://localhost:8000/docs (Swagger UI)

## Common Development Tasks

### Adding a New Position Category
1. Add to `PositionCategory` enum in `shared/constants/positions.py`
2. Add position list (e.g., `NEW_CATEGORY_POSITIONS`)
3. Update `ALL_POSITIONS` dict
4. Add channel variables to `config/settings.py`
5. Update `TelegramPublisher.get_channel_for_position()` in `backend/services/telegram_publisher.py`
6. Add keyboard in `bot/keyboards/positions.py`
7. Update `.env` with new channel names

### Adding a New Bot Handler
1. Create handler file in appropriate directory (applicant/employer/common)
2. Define router: `router = Router(name="handler_name")`
3. For FSM: Define states in `bot/states/`
4. Register router in `bot/main.py` (order matters - specific before general)
5. Test with Telegram bot

### Adding a New API Endpoint
1. Create route function in `backend/api/routes/`
2. Use Beanie models for MongoDB operations
3. Add route to router in same file
4. Include router in `backend/main.py` if new file
5. Test with `pytest` and check `/docs`

### Modifying Publication Formatting
1. Edit `TelegramPublisher.format_vacancy_message()` or `format_resume_message()` in `backend/services/telegram_publisher.py`
2. Use HTML formatting: `<b>bold</b>`, `<i>italic</i>`, `<code>code</code>`
3. Character limits: Telegram messages max 4096 chars
4. Test by publishing a resume/vacancy

## Troubleshooting

**Bot not responding**:
- Check: `docker-compose ps` - bot should be "Up"
- Check logs: `docker-compose logs bot`
- Verify BOT_TOKEN in `.env`

**API errors**:
- Check MongoDB: `docker-compose ps mongodb`
- Test health: `curl http://localhost:8000/api/v1/health/detailed`
- Check logs: `docker-compose logs backend`

**Publications failing**:
- Verify bot is admin in channels with "Post Messages" permission
- Check logs: `docker-compose logs backend | grep "Failed to publish"`
- Test channel access: Send test message manually from bot
- For private channels: Ensure chat_id is correct (use @getmyid_bot)

**FSM state issues**:
- Check Redis: `docker-compose ps redis`
- Clear state: Restart bot or use `/cancel` command
- Verify `redis_url` in settings

**Database connection issues**:
- Check: `docker-compose logs mongodb`
- Verify MONGODB_URL in `.env`
- Connection string format: `mongodb://host:port` (no database name in URL)

## Code Style

- **Async/await**: All database operations and API calls are async
- **Type hints**: Use for all function parameters and returns
- **Docstrings**: Required for all public functions (Google style)
- **Logging**: Use `loguru` logger (imported as `from loguru import logger`)
- **Error handling**: Try-except with specific exceptions, log errors before raising
- **Formatting**: Black (line length 120), isort for imports
- **Models**: Pydantic V2 for validation, Beanie for MongoDB ODM

## Dependencies

**Backend**:
- fastapi - Web framework
- beanie - MongoDB ODM (built on Pydantic V2)
- motor - Async MongoDB driver
- aiogram - Telegram Bot API (for notification service)

**Bot**:
- aiogram 3.x - Telegram Bot framework
- aiohttp - Async HTTP client for backend API calls

**Shared**:
- redis - FSM storage
- celery - Background tasks (planned)
- loguru - Logging

## Additional Documentation

- `docs/SETUP.md` - Comprehensive setup guide
- `docs/TESTING.md` - Telegram channel testing guide
- `docs/CHANNELS_QUICK_SETUP.md` - Quick channel setup (3 steps)
- `scripts/README.md` - Automation scripts documentation
