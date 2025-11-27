# Government Schemes Matcher - Webapp Module

A Flask-based web application for matching eligible government schemes to users based on their user details.

## Project Overview

This application scrapes government scheme websites, uses Regex to parse rules, and compares user profiles against these rules to determine scheme eligibility. The system supports multiple user roles (guests, registered users, admins).
---

## Directory Structure & File Organization

### Core Application Files

#### **`app.py`** - Main Flask Application ⭐
**Significance**: Web application.
- Initializes Flask app and database connections
- Defines all main routes for user flows (login, signup, profile, matching, scheme details)
- Manages user authentication 
- Renders HTML templates for user-facing features

---

#### **`models.py`** - SQLAlchemy ORM Models 🗄️
**Significance**: Defines database schema.
- `Scheme` - Government scheme definitions with titles, descriptions, states
- `SchemeRule` - Eligibility rules in JSON format
- `UserProfile` - User accounts with details for matching. 
- `MatchResult`  

---

#### **`db.py`** - Database Configuration
**Significance**: Initializes SQLAlchemy connection to PostgreSQL.
- Reads `DATABASE_URL` from environment (.env file)
- Auto-creates tables on first run

**Note**: Requires `.env` file with `DATABASE_URL="postgresql://user:pass@host/dbname"`

---

#### **`routes.py`** - Alternative Route Definitions ⚙️
**Significance**: Contains additional API endpoints 
- `/api/match` - RESTful endpoint for profile matching
- `/api/scheme/<id>` - Get scheme details as JSON
- `/admin/*` - Admin verification endpoints for rule management

---

### Data Pipeline

#### **`fetcher.py`** - Web Scraper 🕷️
**Significance**: Collects government scheme information from a list of  websites.
- Uses Playwright (headless Chrome) for JavaScript-heavy sites
- Read seed URLs from alist we provide.
- Saves rendered HTML to `output/raw_html/`

---

#### **`parser.py`** - HTML Parser 📄
**Significance**: Extracts structured data from scraped HTML.
- Identifies eligibility sections using keyword 
- Detects geographic state from eligibility text
- Outputs `output/sample_schemes.py` with parsed data

**Extraction Logic**:
1. Try heading-based extraction (looks for "eligibility" headings)
2. Fall back to keyword search (income, age, resident, etc.)
3. Detect state from text patterns

**Output Format**: Python module with `SAMPLE_SCHEMES` list

---

#### **`runner.py`** - Pipeline Orchestrator 🚀
**Significance**: Coordinates the complete data ingestion pipeline.
- Runs `fetcher.py` → `parser.py` in sequence
- Single entry point for updating scheme database

### Directory Structure Expected
```
webapp/
├── seedurls.csv          # Input: URLs to scrape
├── output/
│   ├── raw_html/         # Scraped HTML files
│   └── sample_schemes.py # Parsed scheme data
└── [app files here]
```
## Getting Started

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Setup .env file** with database credentials
3. **Create database**: `createdb govt_schemes`
5. **Add seed URLs**: Edit `seedurls.csv`
6. **Fetch & parse**: `python runner.py`
7. **Start app**: `python app.py`
8. **Open browser**: `http://127.0.0.1:5000`

---
