from fastapi.templating import Jinja2Templates
import markdown2
import re

def markdown_with_imgclass(text):
    html = markdown2.markdown(text or "")
    # Add class="timeline-img" to all <img> tags
    html = re.sub(r'<img(.*?)>', r'<img\1 class="timeline-img">', html)
    return html

templates = Jinja2Templates(directory="templates")
templates.env.filters['markdown'] = lambda text: markdown2.markdown(text or "")
templates.env.filters['markdown_with_imgclass'] = markdown_with_imgclass 