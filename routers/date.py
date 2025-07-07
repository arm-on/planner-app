from fastapi import APIRouter
from core.date import DateResponse, format_date_helper
from datetime import date
from typing import Optional
from fastapi import HTTPException, Query

router = APIRouter()
# define app router

@router.get("/format-date", response_model=DateResponse)
async def format_date(
    language: str = Query(default="english", description="Language for date format: 'english' or 'persian'"),
    year: Optional[int] = Query(default=None, description="Year (optional, uses current date if not provided)"),
    month: Optional[int] = Query(default=None, description="Month (1-12)"),
    day: Optional[int] = Query(default=None, description="Day of month")
):
    """
    Format a date in English or Persian format
    
    - **language**: 'english' for "June 13, 2025" format or 'persian' for "Khordad 13, 1404" format
    - **year**: Year (optional)
    - **month**: Month (1-12, optional) 
    - **day**: Day of month (optional)
    
    If no date parameters are provided, uses current date.
    """
    try:
        # Determine the date to use
        if year and month and day:
            input_date = date(year, month, day)
        elif any([year, month, day]):
            # If some but not all date parts are provided, raise an error
            raise HTTPException(
                status_code=400, 
                detail="If providing date components, all three (year, month, day) must be provided"
            )
        else:
            input_date = date.today()
        
        # Validate language parameter
        if language.lower() not in ['english', 'persian']:
            raise HTTPException(
                status_code=400,
                detail="Language must be 'english' or 'persian'"
            )
        
        # Format the date
        formatted_date = format_date_helper(input_date, language)
        
        return DateResponse(
            formatted_date=formatted_date,
            language=language.lower(),
            original_date=input_date.strftime("%Y-%m-%d")
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

