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

_original_template_response = templates.TemplateResponse


def compat_template_response(*args, **kwargs):
    """
    Keep compatibility with legacy call sites:
      TemplateResponse("name.html", {"request": request, ...})
    while running against Starlette>=1 where signature is:
      TemplateResponse(request, "name.html", context)
    """
    if args and isinstance(args[0], str):
        name = args[0]
        context = args[1] if len(args) > 1 else kwargs.pop("context", {}) or {}
        request = context.get("request")
        if request is None:
            raise ValueError("Template context must include 'request'.")
        remaining = args[2:]
        return _original_template_response(request, name, context, *remaining, **kwargs)
    return _original_template_response(*args, **kwargs)


templates.TemplateResponse = compat_template_response
