from fastapi import Request


class ValidationException(Exception):
    """
    This class is used to raise exceptions when a validation fails.
    """

    pass


def validate_required_query_param(request: Request, param_name: str) -> str:
    """This function validates if a required query parameter is present in the request.
        e.g: https://www.example.com/test?id=14 in this case id=14 is a QueryParam

    Args:
        param_name (str): field to search in the url

    Raises:
        ValidationException: Missing query parameter in the url

    Returns:
        str: value of the parameter
    """
    param_value = request.query_params.get(param_name)
    if not param_value:
        raise ValidationException(f"URL is missing '{str(param_name)}' param.")
    return param_value


def validate_required_route_param(request: Request, param_name: str) -> str:
    """This function validates if a required route parameter is present in the request.
        https://www.example.com/test/14 in this case 14 is the RouteParam the key is configured in the route

    Args:
        param_name (str): field to search

    Raises:
        ValidationException: Missing route parameter in the url

    Returns:
        str: value of the route param
    """
    param_value = request.path_params.get(param_name)
    if not param_value:
        raise ValidationException(f"URL is missing '{str(param_name)}'.")
    return param_value


async def validate_required_body_param(req_body: dict, param_name: str) -> str:
    """This function validates if a required body parameter is present in the request.
    e.g: The request has a body, { "id": 14 } in this case id is the body param

    Args:
        req_body (dict): request body
        param_name (str): body key to search

    Raises:
        ValidationException: if the body is missing the required parameter

    Returns:
        str: body parameter value
    """
    param_value = req_body.get(param_name)
    if not param_value:
        raise ValidationException(f"Parameter '{str(param_name)}' is required.")
    return param_value


async def validate_json_body(request: Request) -> dict:
    """Checks if the request body is a valid JSON, if not raises a ValidationException

    Args:
        request (Request): FastAPI request

    Raises:
        ValidationException: if the body is not a valid JSON

    Returns:
        dict: object containing the request body
    """
    try:
        req_body = await request.json()
        if req_body is None:
            raise ValidationException("Invalid JSON body")
        return req_body
    except ValueError:
        raise ValidationException("Invalid JSON body")
