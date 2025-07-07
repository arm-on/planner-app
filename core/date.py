from pydantic import BaseModel
from datetime import datetime

class DateResponse(BaseModel):
    formatted_date: str
    language: str
    original_date: str
    
def format_persian_date(input_date):
    """
    Convert Gregorian date to Persian Solar Hijri date
    """
    persian_months = [
        "Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
        "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand"
    ]
    
    gy, gm, gd = input_date.year, input_date.month, input_date.day
    
    if gm > 3 or (gm == 3 and gd >= 21):
        py = gy - 621
    else:
        py = gy - 622
    
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0):
        days_in_month[1] = 29
    
    day_of_year = sum(days_in_month[:gm-1]) + gd
    
    if gm > 3 or (gm == 3 and gd >= 21):
        persian_day_of_year = day_of_year - 79
    else:
        persian_day_of_year = day_of_year + 286
    
    persian_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    
    pm = 1
    remaining_days = persian_day_of_year
    
    for i, days in enumerate(persian_days_in_month):
        if remaining_days <= days:
            pm = i + 1
            pd = remaining_days
            break
        remaining_days -= days
    
    return f"{persian_months[pm-1]} {pd}, {py}"

def format_date_helper(input_date, language='english'):
    """Helper function to format date"""
    if language.lower() == 'persian':
        return format_persian_date(input_date)
    else:
        return input_date.strftime("%B %d, %Y")

