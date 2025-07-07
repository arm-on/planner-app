from datetime import datetime, timezone
import pytz

# Default timezone configuration
DEFAULT_TIMEZONE = "Asia/Tehran"  # Tehran timezone as default
default_timezone = pytz.timezone(DEFAULT_TIMEZONE)

def get_current_time_in_timezone(timezone_str: str = DEFAULT_TIMEZONE) -> datetime:
    """Get current time in the specified timezone"""
    tz = pytz.timezone(timezone_str)
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(tz)

def convert_to_timezone(dt: datetime, timezone_str: str = DEFAULT_TIMEZONE) -> datetime:
    """Convert a datetime to the specified timezone"""
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=timezone.utc)
    tz = pytz.timezone(timezone_str)
    return dt.astimezone(tz)

def convert_from_timezone(dt: datetime, timezone_str: str = DEFAULT_TIMEZONE) -> datetime:
    """Convert a datetime from specified timezone to UTC for storage"""
    if dt.tzinfo is None:
        # Assume UTC if no timezone info (frontend sends UTC)
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo == timezone.utc:
        # Already UTC, return as is
        return dt
    else:
        # Convert from specified timezone to UTC
        return dt.astimezone(timezone.utc)
    return dt

# Backward compatibility functions
def get_current_time_in_app_timezone() -> datetime:
    """Get current time in the app's configured timezone (backward compatibility)"""
    return get_current_time_in_timezone()

def convert_to_app_timezone(dt: datetime) -> datetime:
    """Convert a datetime to the app's timezone (backward compatibility)"""
    return convert_to_timezone(dt)

def convert_from_app_timezone(dt: datetime) -> datetime:
    """Convert a datetime from app timezone to UTC for storage (backward compatibility)"""
    return convert_from_timezone(dt)

# List of timezones by country and city for the frontend
TIMEZONE_COUNTRIES = {
    "Germany": [
        {"city": "Berlin", "value": "Europe/Berlin", "label": "Berlin (UTC+1/UTC+2)"},
        {"city": "Munich", "value": "Europe/Berlin", "label": "Munich (UTC+1/UTC+2)"},
        {"city": "Frankfurt", "value": "Europe/Berlin", "label": "Frankfurt (UTC+1/UTC+2)"},
        {"city": "Hamburg", "value": "Europe/Berlin", "label": "Hamburg (UTC+1/UTC+2)"},
        {"city": "Cologne", "value": "Europe/Berlin", "label": "Cologne (UTC+1/UTC+2)"},
        {"city": "Stuttgart", "value": "Europe/Berlin", "label": "Stuttgart (UTC+1/UTC+2)"},
        {"city": "Düsseldorf", "value": "Europe/Berlin", "label": "Düsseldorf (UTC+1/UTC+2)"},
        {"city": "Dortmund", "value": "Europe/Berlin", "label": "Dortmund (UTC+1/UTC+2)"},
        {"city": "Essen", "value": "Europe/Berlin", "label": "Essen (UTC+1/UTC+2)"},
        {"city": "Leipzig", "value": "Europe/Berlin", "label": "Leipzig (UTC+1/UTC+2)"},
    ],
    "Austria": [
        {"city": "Vienna", "value": "Europe/Vienna", "label": "Vienna (UTC+1/UTC+2)"},
        {"city": "Salzburg", "value": "Europe/Vienna", "label": "Salzburg (UTC+1/UTC+2)"},
        {"city": "Graz", "value": "Europe/Vienna", "label": "Graz (UTC+1/UTC+2)"},
        {"city": "Linz", "value": "Europe/Vienna", "label": "Linz (UTC+1/UTC+2)"},
        {"city": "Innsbruck", "value": "Europe/Vienna", "label": "Innsbruck (UTC+1/UTC+2)"},
        {"city": "Klagenfurt", "value": "Europe/Vienna", "label": "Klagenfurt (UTC+1/UTC+2)"},
        {"city": "Villach", "value": "Europe/Vienna", "label": "Villach (UTC+1/UTC+2)"},
        {"city": "Wels", "value": "Europe/Vienna", "label": "Wels (UTC+1/UTC+2)"},
        {"city": "Sankt Pölten", "value": "Europe/Vienna", "label": "Sankt Pölten (UTC+1/UTC+2)"},
        {"city": "Dornbirn", "value": "Europe/Vienna", "label": "Dornbirn (UTC+1/UTC+2)"},
    ],
    "England": [
        {"city": "London", "value": "Europe/London", "label": "London (UTC+0/UTC+1)"},
        {"city": "Birmingham", "value": "Europe/London", "label": "Birmingham (UTC+0/UTC+1)"},
        {"city": "Manchester", "value": "Europe/London", "label": "Manchester (UTC+0/UTC+1)"},
        {"city": "Leeds", "value": "Europe/London", "label": "Leeds (UTC+0/UTC+1)"},
        {"city": "Liverpool", "value": "Europe/London", "label": "Liverpool (UTC+0/UTC+1)"},
        {"city": "Sheffield", "value": "Europe/London", "label": "Sheffield (UTC+0/UTC+1)"},
        {"city": "Bristol", "value": "Europe/London", "label": "Bristol (UTC+0/UTC+1)"},
        {"city": "Glasgow", "value": "Europe/London", "label": "Glasgow (UTC+0/UTC+1)"},
        {"city": "Edinburgh", "value": "Europe/London", "label": "Edinburgh (UTC+0/UTC+1)"},
        {"city": "Leicester", "value": "Europe/London", "label": "Leicester (UTC+0/UTC+1)"},
    ],
    "Spain": [
        {"city": "Madrid", "value": "Europe/Madrid", "label": "Madrid (UTC+1/UTC+2)"},
        {"city": "Barcelona", "value": "Europe/Madrid", "label": "Barcelona (UTC+1/UTC+2)"},
        {"city": "Valencia", "value": "Europe/Madrid", "label": "Valencia (UTC+1/UTC+2)"},
        {"city": "Seville", "value": "Europe/Madrid", "label": "Seville (UTC+1/UTC+2)"},
        {"city": "Zaragoza", "value": "Europe/Madrid", "label": "Zaragoza (UTC+1/UTC+2)"},
        {"city": "Málaga", "value": "Europe/Madrid", "label": "Málaga (UTC+1/UTC+2)"},
        {"city": "Murcia", "value": "Europe/Madrid", "label": "Murcia (UTC+1/UTC+2)"},
        {"city": "Palma", "value": "Europe/Madrid", "label": "Palma (UTC+1/UTC+2)"},
        {"city": "Las Palmas", "value": "Europe/Madrid", "label": "Las Palmas (UTC+0/UTC+1)"},
        {"city": "Bilbao", "value": "Europe/Madrid", "label": "Bilbao (UTC+1/UTC+2)"},
    ],
    "Italy": [
        {"city": "Rome", "value": "Europe/Rome", "label": "Rome (UTC+1/UTC+2)"},
        {"city": "Milan", "value": "Europe/Rome", "label": "Milan (UTC+1/UTC+2)"},
        {"city": "Naples", "value": "Europe/Rome", "label": "Naples (UTC+1/UTC+2)"},
        {"city": "Turin", "value": "Europe/Rome", "label": "Turin (UTC+1/UTC+2)"},
        {"city": "Palermo", "value": "Europe/Rome", "label": "Palermo (UTC+1/UTC+2)"},
        {"city": "Genoa", "value": "Europe/Rome", "label": "Genoa (UTC+1/UTC+2)"},
        {"city": "Bologna", "value": "Europe/Rome", "label": "Bologna (UTC+1/UTC+2)"},
        {"city": "Florence", "value": "Europe/Rome", "label": "Florence (UTC+1/UTC+2)"},
        {"city": "Bari", "value": "Europe/Rome", "label": "Bari (UTC+1/UTC+2)"},
        {"city": "Catania", "value": "Europe/Rome", "label": "Catania (UTC+1/UTC+2)"},
    ],
    "France": [
        {"city": "Paris", "value": "Europe/Paris", "label": "Paris (UTC+1/UTC+2)"},
        {"city": "Marseille", "value": "Europe/Paris", "label": "Marseille (UTC+1/UTC+2)"},
        {"city": "Lyon", "value": "Europe/Paris", "label": "Lyon (UTC+1/UTC+2)"},
        {"city": "Toulouse", "value": "Europe/Paris", "label": "Toulouse (UTC+1/UTC+2)"},
        {"city": "Nice", "value": "Europe/Paris", "label": "Nice (UTC+1/UTC+2)"},
        {"city": "Nantes", "value": "Europe/Paris", "label": "Nantes (UTC+1/UTC+2)"},
        {"city": "Strasbourg", "value": "Europe/Paris", "label": "Strasbourg (UTC+1/UTC+2)"},
        {"city": "Montpellier", "value": "Europe/Paris", "label": "Montpellier (UTC+1/UTC+2)"},
        {"city": "Bordeaux", "value": "Europe/Paris", "label": "Bordeaux (UTC+1/UTC+2)"},
        {"city": "Lille", "value": "Europe/Paris", "label": "Lille (UTC+1/UTC+2)"},
    ],
    "USA": [
        {"city": "New York", "value": "America/New_York", "label": "New York (UTC-5/UTC-4)"},
        {"city": "Los Angeles", "value": "America/Los_Angeles", "label": "Los Angeles (UTC-8/UTC-7)"},
        {"city": "Chicago", "value": "America/Chicago", "label": "Chicago (UTC-6/UTC-5)"},
        {"city": "Houston", "value": "America/Chicago", "label": "Houston (UTC-6/UTC-5)"},
        {"city": "Phoenix", "value": "America/Phoenix", "label": "Phoenix (UTC-7)"},
        {"city": "Philadelphia", "value": "America/New_York", "label": "Philadelphia (UTC-5/UTC-4)"},
        {"city": "San Antonio", "value": "America/Chicago", "label": "San Antonio (UTC-6/UTC-5)"},
        {"city": "San Diego", "value": "America/Los_Angeles", "label": "San Diego (UTC-8/UTC-7)"},
        {"city": "Dallas", "value": "America/Chicago", "label": "Dallas (UTC-6/UTC-5)"},
        {"city": "San Jose", "value": "America/Los_Angeles", "label": "San Jose (UTC-8/UTC-7)"},
    ],
    "Canada": [
        {"city": "Toronto", "value": "America/Toronto", "label": "Toronto (UTC-5/UTC-4)"},
        {"city": "Montreal", "value": "America/Montreal", "label": "Montreal (UTC-5/UTC-4)"},
        {"city": "Vancouver", "value": "America/Vancouver", "label": "Vancouver (UTC-8/UTC-7)"},
        {"city": "Calgary", "value": "America/Edmonton", "label": "Calgary (UTC-7/UTC-6)"},
        {"city": "Edmonton", "value": "America/Edmonton", "label": "Edmonton (UTC-7/UTC-6)"},
        {"city": "Ottawa", "value": "America/Toronto", "label": "Ottawa (UTC-5/UTC-4)"},
        {"city": "Winnipeg", "value": "America/Winnipeg", "label": "Winnipeg (UTC-6/UTC-5)"},
        {"city": "Quebec City", "value": "America/Montreal", "label": "Quebec City (UTC-5/UTC-4)"},
        {"city": "Hamilton", "value": "America/Toronto", "label": "Hamilton (UTC-5/UTC-4)"},
        {"city": "Kitchener", "value": "America/Toronto", "label": "Kitchener (UTC-5/UTC-4)"},
    ],
    "Iran": [
        {"city": "Tehran", "value": "Asia/Tehran", "label": "Tehran (UTC+3:30)"},
        {"city": "Mashhad", "value": "Asia/Tehran", "label": "Mashhad (UTC+3:30)"},
        {"city": "Isfahan", "value": "Asia/Tehran", "label": "Isfahan (UTC+3:30)"},
        {"city": "Tabriz", "value": "Asia/Tehran", "label": "Tabriz (UTC+3:30)"},
        {"city": "Shiraz", "value": "Asia/Tehran", "label": "Shiraz (UTC+3:30)"},
        {"city": "Kerman", "value": "Asia/Tehran", "label": "Kerman (UTC+3:30)"},
        {"city": "Yazd", "value": "Asia/Tehran", "label": "Yazd (UTC+3:30)"},
        {"city": "Qom", "value": "Asia/Tehran", "label": "Qom (UTC+3:30)"},
        {"city": "Kermanshah", "value": "Asia/Tehran", "label": "Kermanshah (UTC+3:30)"},
        {"city": "Urmia", "value": "Asia/Tehran", "label": "Urmia (UTC+3:30)"},
    ],
    "South Korea": [
        {"city": "Seoul", "value": "Asia/Seoul", "label": "Seoul (UTC+9)"},
        {"city": "Busan", "value": "Asia/Seoul", "label": "Busan (UTC+9)"},
        {"city": "Incheon", "value": "Asia/Seoul", "label": "Incheon (UTC+9)"},
        {"city": "Daegu", "value": "Asia/Seoul", "label": "Daegu (UTC+9)"},
        {"city": "Daejeon", "value": "Asia/Seoul", "label": "Daejeon (UTC+9)"},
        {"city": "Gwangju", "value": "Asia/Seoul", "label": "Gwangju (UTC+9)"},
        {"city": "Suwon", "value": "Asia/Seoul", "label": "Suwon (UTC+9)"},
        {"city": "Ulsan", "value": "Asia/Seoul", "label": "Ulsan (UTC+9)"},
        {"city": "Changwon", "value": "Asia/Seoul", "label": "Changwon (UTC+9)"},
        {"city": "Seongnam", "value": "Asia/Seoul", "label": "Seongnam (UTC+9)"},
    ],
    "Japan": [
        {"city": "Tokyo", "value": "Asia/Tokyo", "label": "Tokyo (UTC+9)"},
        {"city": "Yokohama", "value": "Asia/Tokyo", "label": "Yokohama (UTC+9)"},
        {"city": "Osaka", "value": "Asia/Tokyo", "label": "Osaka (UTC+9)"},
        {"city": "Nagoya", "value": "Asia/Tokyo", "label": "Nagoya (UTC+9)"},
        {"city": "Sapporo", "value": "Asia/Tokyo", "label": "Sapporo (UTC+9)"},
        {"city": "Fukuoka", "value": "Asia/Tokyo", "label": "Fukuoka (UTC+9)"},
        {"city": "Kobe", "value": "Asia/Tokyo", "label": "Kobe (UTC+9)"},
        {"city": "Kyoto", "value": "Asia/Tokyo", "label": "Kyoto (UTC+9)"},
        {"city": "Kawasaki", "value": "Asia/Tokyo", "label": "Kawasaki (UTC+9)"},
        {"city": "Saitama", "value": "Asia/Tokyo", "label": "Saitama (UTC+9)"},
    ],
    "Saudi Arabia": [
        {"city": "Riyadh", "value": "Asia/Riyadh", "label": "Riyadh (UTC+3)"},
        {"city": "Jeddah", "value": "Asia/Riyadh", "label": "Jeddah (UTC+3)"},
        {"city": "Mecca", "value": "Asia/Riyadh", "label": "Mecca (UTC+3)"},
        {"city": "Medina", "value": "Asia/Riyadh", "label": "Medina (UTC+3)"},
        {"city": "Dammam", "value": "Asia/Riyadh", "label": "Dammam (UTC+3)"},
        {"city": "Taif", "value": "Asia/Riyadh", "label": "Taif (UTC+3)"},
        {"city": "Tabuk", "value": "Asia/Riyadh", "label": "Tabuk (UTC+3)"},
        {"city": "Buraydah", "value": "Asia/Riyadh", "label": "Buraydah (UTC+3)"},
        {"city": "Khamis Mushait", "value": "Asia/Riyadh", "label": "Khamis Mushait (UTC+3)"},
        {"city": "Hail", "value": "Asia/Riyadh", "label": "Hail (UTC+3)"},
    ],
    "UAE": [
        {"city": "Dubai", "value": "Asia/Dubai", "label": "Dubai (UTC+4)"},
        {"city": "Abu Dhabi", "value": "Asia/Dubai", "label": "Abu Dhabi (UTC+4)"},
        {"city": "Sharjah", "value": "Asia/Dubai", "label": "Sharjah (UTC+4)"},
        {"city": "Al Ain", "value": "Asia/Dubai", "label": "Al Ain (UTC+4)"},
        {"city": "Ajman", "value": "Asia/Dubai", "label": "Ajman (UTC+4)"},
        {"city": "Ras Al Khaimah", "value": "Asia/Dubai", "label": "Ras Al Khaimah (UTC+4)"},
        {"city": "Fujairah", "value": "Asia/Dubai", "label": "Fujairah (UTC+4)"},
        {"city": "Umm Al Quwain", "value": "Asia/Dubai", "label": "Umm Al Quwain (UTC+4)"},
        {"city": "Khalifa City", "value": "Asia/Dubai", "label": "Khalifa City (UTC+4)"},
        {"city": "Al Gharbia", "value": "Asia/Dubai", "label": "Al Gharbia (UTC+4)"},
    ],
    "Qatar": [
        {"city": "Doha", "value": "Asia/Qatar", "label": "Doha (UTC+3)"},
        {"city": "Al Wakrah", "value": "Asia/Qatar", "label": "Al Wakrah (UTC+3)"},
        {"city": "Al Khor", "value": "Asia/Qatar", "label": "Al Khor (UTC+3)"},
        {"city": "Lusail", "value": "Asia/Qatar", "label": "Lusail (UTC+3)"},
        {"city": "Al Rayyan", "value": "Asia/Qatar", "label": "Al Rayyan (UTC+3)"},
        {"city": "Umm Salal", "value": "Asia/Qatar", "label": "Umm Salal (UTC+3)"},
        {"city": "Al Daayen", "value": "Asia/Qatar", "label": "Al Daayen (UTC+3)"},
        {"city": "Al Shamal", "value": "Asia/Qatar", "label": "Al Shamal (UTC+3)"},
        {"city": "Al Gharafa", "value": "Asia/Qatar", "label": "Al Gharafa (UTC+3)"},
        {"city": "Al Aziziya", "value": "Asia/Qatar", "label": "Al Aziziya (UTC+3)"},
    ],
    "Kuwait": [
        {"city": "Kuwait City", "value": "Asia/Kuwait", "label": "Kuwait City (UTC+3)"},
        {"city": "Salmiya", "value": "Asia/Kuwait", "label": "Salmiya (UTC+3)"},
        {"city": "Hawalli", "value": "Asia/Kuwait", "label": "Hawalli (UTC+3)"},
        {"city": "Jahra", "value": "Asia/Kuwait", "label": "Jahra (UTC+3)"},
        {"city": "Farwaniya", "value": "Asia/Kuwait", "label": "Farwaniya (UTC+3)"},
        {"city": "Mubarak Al-Kabeer", "value": "Asia/Kuwait", "label": "Mubarak Al-Kabeer (UTC+3)"},
        {"city": "Ahmadi", "value": "Asia/Kuwait", "label": "Ahmadi (UTC+3)"},
        {"city": "Al Jahra", "value": "Asia/Kuwait", "label": "Al Jahra (UTC+3)"},
        {"city": "Al Farwaniyah", "value": "Asia/Kuwait", "label": "Al Farwaniyah (UTC+3)"},
        {"city": "Al Ahmadi", "value": "Asia/Kuwait", "label": "Al Ahmadi (UTC+3)"},
    ],
    "Lebanon": [
        {"city": "Beirut", "value": "Asia/Beirut", "label": "Beirut (UTC+2/UTC+3)"},
        {"city": "Tripoli", "value": "Asia/Beirut", "label": "Tripoli (UTC+2/UTC+3)"},
        {"city": "Sidon", "value": "Asia/Beirut", "label": "Sidon (UTC+2/UTC+3)"},
        {"city": "Tyre", "value": "Asia/Beirut", "label": "Tyre (UTC+2/UTC+3)"},
        {"city": "Nabatieh", "value": "Asia/Beirut", "label": "Nabatieh (UTC+2/UTC+3)"},
        {"city": "Zahle", "value": "Asia/Beirut", "label": "Zahle (UTC+2/UTC+3)"},
        {"city": "Baalbek", "value": "Asia/Beirut", "label": "Baalbek (UTC+2/UTC+3)"},
        {"city": "Jounieh", "value": "Asia/Beirut", "label": "Jounieh (UTC+2/UTC+3)"},
        {"city": "Byblos", "value": "Asia/Beirut", "label": "Byblos (UTC+2/UTC+3)"},
        {"city": "Batroun", "value": "Asia/Beirut", "label": "Batroun (UTC+2/UTC+3)"},
    ],
}

def get_timezones_by_country():
    """Return the timezone structure for all supported countries/cities."""
    return TIMEZONE_COUNTRIES 