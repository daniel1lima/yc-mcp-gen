from typing import Optional, List, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from datetime import datetime

app = FastAPI()

class PipelineInput(BaseModel):
    input_name: str
    value: str

class FlowConfig(BaseModel):
    auth_token: str
    user_id: str
    saved_item_id: str
    project_id: Optional[str] = None
    pipeline_inputs: List[PipelineInput] = []
    polling_interval_ms: int = 2000
    timeout_ms: int = 300000

async def get_flow_run_details(
    auth_token: str,
    run_id: str,
    user_id: str,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    params = {
        "run_id": run_id,
        "user_id": user_id
    }
    if project_id:
        params["project_id"] = project_id

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.gumloop.com/api/v1/get_pl_run",
            params=params,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        if not response.is_success:
            raise HTTPException(status_code=response.status_code, detail=f"HTTP error! status: {response.json()}")
        
        return response.json()

async def poll_flow_run_until_complete(
    auth_token: str,
    run_id: str,
    user_id: str,
    project_id: Optional[str] = None,
    polling_interval_ms: int = 2000,
    timeout_ms: int = 300000
) -> Dict[str, Any]:
    start_time = datetime.now().timestamp() * 1000

    while True:
        run_details = await get_flow_run_details(
            auth_token=auth_token,
            run_id=run_id,
            user_id=user_id,
            project_id=project_id
        )

        if run_details["state"] == "DONE":
            return run_details

        if run_details["state"] in ["FAILED", "TERMINATED"]:
            raise HTTPException(
                status_code=400,
                detail=f"Flow failed with state: {run_details['state']}"
            )

        if datetime.now().timestamp() * 1000 - start_time > timeout_ms:
            raise HTTPException(
                status_code=408,
                detail="Polling timeout exceeded"
            )

        await asyncio.sleep(polling_interval_ms / 1000)

async def start_gumloop_flow(flowConfig: FlowConfig) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.gumloop.com/api/v1/start_pipeline",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {flowConfig.auth_token}"
            },
            json={
                "user_id": flowConfig.user_id,
                "saved_item_id": flowConfig.saved_item_id,
                "project_id": flowConfig.project_id or None,
                "pipeline_inputs": [input.dict() for input in flowConfig.pipeline_inputs]
            }
        )

        if not response.is_success:
            raise HTTPException(status_code=response.status_code, detail=f"HTTP error! status: {response.json()}")

        return response.json()

@app.post("/start-and-wait-flow")
async def start_and_wait_for_flow(config: FlowConfig) -> Dict[str, Any]:
    try:
        # Start the flow
        flow_start = await start_gumloop_flow(
            auth_token=config.auth_token,
            user_id=config.user_id,
            saved_item_id=config.saved_item_id,
            project_id=config.project_id,
            pipeline_inputs=config.pipeline_inputs
        )

        # Poll until completion
        final_result = await poll_flow_run_until_complete(
            auth_token=config.auth_token,
            run_id=flow_start["run_id"],
            user_id=config.user_id,
            project_id=config.project_id,
            polling_interval_ms=config.polling_interval_ms,
            timeout_ms=config.timeout_ms
        )

        return {
            "start_details": flow_start,
            "final_result": final_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/flow-run-details/{run_id}")
async def get_flow_run_details_endpoint(
    run_id: str,
    auth_token: str,
    user_id: str,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    try:
        return await get_flow_run_details(
            auth_token=auth_token,
            run_id=run_id,
            user_id=user_id,
            project_id=project_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 