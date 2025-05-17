# Gumloop FastAPI Integration

This is a FastAPI implementation of the Gumloop API integration, providing async endpoints for managing Gumloop flows and OpenAPI specifications.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (create a `.env` file):
```env
GUMLOOP_API_KEY=your_api_key
GUMLOOP_USER_ID=your_user_id
GUMLOOP_SAVED_ITEM_ID=your_saved_item_id
```

## Running the Server

Start the FastAPI server:
```bash
uvicorn src.server:app --reload
```

The server will be available at `http://localhost:8000`

## API Endpoints

### Health Check
```http
GET /health
```

### Start Flow
```http
POST /flow/start
```

Request body:
```json
{
    "pipelineInputs": [
        {
            "input_name": "input",
            "value": "your input value"
        }
    ],
    "pollingIntervalMs": 2000,
    "timeoutMs": 300000
}
```

### Fetch GitHub Raw Content
```http
GET /api/fetch-github-raw?url={raw_github_url}
```

### Process Full OpenAPI Specification
```http
POST /api/full-spec
```

Request body: OpenAPI specification in JSON or YAML format

## Features

- Async/await support for better performance
- Automatic API documentation with Swagger UI and ReDoc
- Type safety with Pydantic models
- YAML and JSON request body support
- CORS middleware enabled
- Comprehensive error handling
- Environment variable management

## API Documentation

Once the server is running, you can access:
- Interactive API docs (Swagger UI): `http://localhost:8000/docs`
- Alternative API docs (ReDoc): `http://localhost:8000/redoc` 