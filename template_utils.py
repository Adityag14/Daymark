from inspect import signature
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse


def render_template(
    templates: Jinja2Templates,
    request: Request,
    name: str,
    context: dict[str, Any],
    status_code: int = 200,
) -> HTMLResponse:
    template_response = templates.TemplateResponse
    template_context = {**context, "request": request}
    parameters = signature(template_response).parameters

    if parameters and next(iter(parameters)) == "request":
        return template_response(
            request=request,
            name=name,
            context=template_context,
            status_code=status_code,
        )
    return template_response(name, template_context, status_code=status_code)
