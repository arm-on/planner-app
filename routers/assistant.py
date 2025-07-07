from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
import httpx
import json
from pydantic import BaseModel
from core.database import get_db
from sqlalchemy.orm import Session
from models.models import Model
from models.user import User
from models.keys import Key
from datetime import datetime

router = APIRouter()

class AssistantQuery(BaseModel):
    model_api_key: str
    system_prompt: str
    user_prompt: str

def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from API key in header"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Check if key exists and is not expired
    key_record = db.query(Key).filter(
        Key.key == x_api_key,
        Key.expires_at > datetime.utcnow()
    ).first()
    
    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    
    return key_record.owner_user

@router.post("/query")
async def query_assistant(
    query: AssistantQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a query to the AI assistant"""
    try:
        print(f"DEBUG: Received query for user {current_user.id}")
        print(f"DEBUG: Model API key: {query.model_api_key}")
        
        # Get the selected model (only if owned by current user)
        model = db.query(Model).filter(
            Model.api_key == query.model_api_key,
            Model.owner == current_user.id
        ).first()
        
        print(f"DEBUG: Found model: {model}")
        
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")

        # Prepare the request payload based on the model type
        if "openai" in model.base_url.lower() or "api.openai.com" in model.base_url:
            # OpenAI-compatible API
            payload = {
                "model": model.name,
                "messages": [
                    {"role": "system", "content": query.system_prompt},
                    {"role": "user", "content": query.user_prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.7
            }
        elif "anthropic" in model.base_url.lower() or "claude" in model.name.lower():
            # Anthropic Claude API
            payload = {
                "model": model.name,
                "max_tokens": 2000,
                "temperature": 0.7,
                "messages": [
                    {"role": "user", "content": f"{query.system_prompt}\n\n{query.user_prompt}"}
                ]
            }
        else:
            # Generic OpenAI-compatible format
            payload = {
                "model": model.name,
                "messages": [
                    {"role": "system", "content": query.system_prompt},
                    {"role": "user", "content": query.user_prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.7
            }

        # Make the API request
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {model.api_key}",
                "Content-Type": "application/json"
            }
            
            response = await client.post(
                f"{model.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )

            print(f"DEBUG: API Response Status: {response.status_code}")
            print(f"DEBUG: API Response Headers: {response.headers}")
            print(f"DEBUG: API Response Text: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"DEBUG: API Response JSON: {result}")
                
                # Extract the response text based on the API format
                if "choices" in result and len(result["choices"]) > 0:
                    response_text = result["choices"][0]["message"]["content"]
                elif "content" in result:
                    response_text = result["content"]
                else:
                    response_text = str(result)
                
                return {"response": response_text}
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get("message", error_detail)
                except:
                    pass
                
                print(f"DEBUG: API Error: {error_detail}")
                return {"error": f"AI API error: {error_detail}"}

    except httpx.RequestError as e:
        print(f"DEBUG: Network error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        print(f"DEBUG: Internal error: {str(e)}")
        print(f"DEBUG: Error type: {type(e)}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") 