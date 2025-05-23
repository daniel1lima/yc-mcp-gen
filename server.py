from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yaml
import os
from dotenv import load_dotenv
from utils.gumloop_util import start_gumloop_flow, FlowConfig, PipelineInput, get_flow_run_details
import uvicorn

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
            "flowType": "single-tool-raw",
            "pipelineInputs": [
                {"inputName": "input", "value": "{"type": "string", "description": "The raw OpenAPI specification to parse"}"}
            ]
        }
        {
            "flowType": "ai-search",
            "pipelineInputs": [
                {"inputName": "input", "value": "I want an MCP server for Spotify to search for music and add a song to a playlist"}
            ]
        }
        {
            "flowType": "single-tool-url",
            "pipelineInputs": [
                {"inputName": "input", "value": "https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/api_reference/api_reference.yaml"}
            ]
        }

    Returns:
        A dictionary containing the start details, final result, and outputs.
    """
    try:
        body = await request.json()
        print(body)
        
        # Define flow type to saved item ID mapping
        flow_type_to_id = {
            "single-tool-raw": GUMLOOP_SINGLE_TOOL_SPEC_TO_TOOL_ID,
            "ai-search": GUMLOOP_AI_SEARCH_TO_TOOL_ID,
            "single-tool-url": GUMLOOP_SINGLE_TOOL_SPEC_URL_TO_TOOL_ID
        }

        print("96")
        
        # Get flow type from request body
        flow_type = body.get("flowType")
        if not flow_type or flow_type not in flow_type_to_id:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid flow type. Must be one of: {', '.join(flow_type_to_id.keys())}"
            )
        
        print("97")
            
        # Get the appropriate saved item ID
        saved_item_id = flow_type_to_id[flow_type]
        if not saved_item_id:
            raise HTTPException(
                status_code=500,
                detail=f"Saved item ID not configured for flow type: {flow_type}"
            )
        
        print("98")
        
        # Create FlowConfig from environment variables and request body
        flow_config = FlowConfig(
            auth_token=GUMLOOP_API_KEY,
            user_id=GUMLOOP_USER_ID,
            saved_item_id=saved_item_id,
            pipeline_inputs=[PipelineInput(**input) for input in body.get("pipelineInputs", [])],
            polling_interval_ms=body.get("pollingIntervalMs", 2000),
            timeout_ms=body.get("timeoutMs", 300000)
        )

        print("99")

        result = await start_gumloop_flow(flow_config)

        run_id = result.get('run_id')
        if not run_id:
            raise HTTPException(status_code=500, detail="Run ID not found")
        
        print("REACHEDF!")
        
        return JSONResponse(content={
            "success": True,
            "runId": run_id,
        })
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/get-flow-run-details")
async def get_flow_run_details_endpoint(run_id: str):
    """
    Get the details of a flow run in Gumloop.

    Args:
        run_id: The ID of the flow run to get the details of.

    Returns:
    1. If the flow has completed, returns the tools in the format:
    {
        "tools": [
            <Tool 1>,
            <Tool 2>,
            <Tool 3>
        ]
    }

    2. If the flow is still running, returns the status of the flow in the format:
    {
        "status": <Status>,
        "runId": <Run ID>
    }
    """
    try:
        result = await get_flow_run_details(GUMLOOP_API_KEY, run_id, GUMLOOP_USER_ID)
        
        # If the flow has completed, return just the outputs
        if result.get("state") == "DONE" and "outputs" in result:
            res = result["outputs"].get("output")
            return JSONResponse(content={"tools": str(res).replace('\\n', '\n')})
        
        # Otherwise return the full result so frontend can continue polling
        return JSONResponse(content={"status": result.get("state"), "runId": run_id})
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
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port) 