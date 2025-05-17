from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import yaml
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
from utils.gumloop_util import start_gumloop_flow, FlowConfig, PipelineInput
import uvicorn
from openapi_parser import parse

# Load environment variables
load_dotenv()

# Get Gumloop API key
GUMLOOP_API_KEY = os.getenv("GUMLOOP_API_KEY")
if not GUMLOOP_API_KEY:
    raise ValueError("GUMLOOP_API_KEY environment variable is not set")
GUMLOOP_USER_ID = os.getenv("GUMLOOP_USER_ID")
if not GUMLOOP_USER_ID:
    raise ValueError("GUMLOOP_USER_ID environment variable is not set")

GUMLOOP_AI_SEARCH_TO_TOOL_ID = "8cAwbUxMdbWMUJdQQAxuLE"
GUMLOOP_SINGLE_TOOL_SPEC_TO_TOOL_ID = "nxNBzbhXkF2dVHM968rfRh"
GUMLOOP_SINGLE_TOOL_SPEC_URL_TO_TOOL_ID = "mawn5QYkuhJqYfaMBW5DsK"


app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware for YAML handling
@app.middleware("http")
async def yaml_middleware(request: Request, call_next):
    content_type = request.headers.get("content-type", "")
    
    if content_type in ["application/x-yaml", "text/yaml"]:
        body = await request.body()
        try:
            request._body = yaml.safe_load(body.decode())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    
    return await call_next(request)

@app.get("/health")
async def health_check():
    return "hi!"

@app.post("/api/flow-start")
async def start_flow(request: Request):
    """
    Start a flow in Gumloop.

    Args:
        request: The request object containing the flow type and pipeline inputs.
        Examples: 
        {
            "flowType": "full-spec",
            "pipelineInputs": [
                {"inputName": "url", "value": "https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/api_reference/api_reference.yaml"}
            ]
        }
        {
            "flowType": "ai-search",
            "pipelineInputs": [
                {"inputName": "input", "value": "I want an MCP server for Spotify to search for music and add a song to a playlist"}
            ]
        }

    Returns:
        A dictionary containing the start details, final result, and outputs.
    """
    try:
        body = await request.json()
        
        # Define flow type to saved item ID mapping
        flow_type_to_id = {
            "full-spec": GUMLOOP_SINGLE_TOOL_SPEC_TO_TOOL_ID,
            "ai-search": GUMLOOP_AI_SEARCH_TO_TOOL_ID,
            "single-tool": GUMLOOP_SINGLE_TOOL_SPEC_URL_TO_TOOL_ID
        }
        
        # Get flow type from request body
        flow_type = body.get("flowType")
        if not flow_type or flow_type not in flow_type_to_id:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid flow type. Must be one of: {', '.join(flow_type_to_id.keys())}"
            )
            
        # Get the appropriate saved item ID
        saved_item_id = flow_type_to_id[flow_type]
        if not saved_item_id:
            raise HTTPException(
                status_code=500,
                detail=f"Saved item ID not configured for flow type: {flow_type}"
            )
        
        # Create FlowConfig from environment variables and request body
        flow_config = FlowConfig(
            auth_token=GUMLOOP_API_KEY,
            user_id=GUMLOOP_USER_ID,
            saved_item_id=saved_item_id,
            pipeline_inputs=[PipelineInput(**input) for input in body.get("pipelineInputs", [])],
            polling_interval_ms=body.get("pollingIntervalMs", 2000),
            timeout_ms=body.get("timeoutMs", 300000)
        )

        result = await start_gumloop_flow(flow_config)

        run_id = result.get('run_id')
        if not run_id:
            raise HTTPException(status_code=500, detail="Run ID not found")
        
        return JSONResponse(content={
            "success": True,
            "runId": run_id,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-github-raw")
async def fetch_github_raw(url: str):
    try:
        if not url:
            raise HTTPException(status_code=400, detail="URL parameter is required")
        
        if not url.startswith("https://raw.githubusercontent.com/"):
            raise HTTPException(status_code=400, detail="URL must be a raw GitHub URL")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            
            if not response.is_success:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch content: {response.status_code}"
                )
            
            text = response.text
            
            try:
                # Parse the OpenAPI specification
                api = yaml.safe_load(text)
                return {"data": api}
            except Exception as parse_error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse OpenAPI specification: {str(parse_error)}"
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content: {str(e)}")

@app.post("/api/full-spec")
async def process_full_spec(request: Request):
    try:
        content_type = request.headers.get("content-type", "")
        body = await request.body()
        
        if not body:
            raise HTTPException(status_code=400, detail="OpenAPI specification is required")
        
        # Parse based on content type
        try:
            if content_type in ["application/x-yaml", "text/yaml"]:
                api = yaml.safe_load(body.decode())
            else:  # Default to JSON
                api = yaml.safe_load(yaml.dump(await request.json()))
            
            
            return {
                "success": True,
                "api": api
            }
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid OpenAPI specification: {str(e)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Something went wrong!",
            "message": str(exc)
        }
    )

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True) 