import requests
import logging
import time
import json


def generate_docstring(api_json):
    """ Builds the docstring for the API function if longer than 1024, the chatbot will crash"""

    headers = api_json['api_headers']
    params = api_json['api_parameters']
    body = api_json['api_body']

    docstring = f"Executes a {api_json['api_request_type']} request to {api_json['api_name']} API.\n\n"
    docstring += f"{api_json['api_description']}\n\n"
    docstring += "Parameters:\n"
    for item in headers + params + body:
        if 'description' in item:
            if item['description'] != "":
                param_name = item['key'].replace("-", "_")
                description = item['description']
                if 'value' in item and item["value"] != "":
                    description += f" (default value: {item['value']})"
                docstring += f"    {param_name}: {description}\n"
            else:
                continue

    return '    """ ' + docstring + '    """'


def generate_function_body(api_json):

    headers = api_json['api_headers']
    params = api_json['api_parameters']
    body = api_json['api_body']

    function_body = ""

    if body:
        function_body += "    data = {\n"
        for item in body:
            if 'description' in item or ('value' not in item and 'description' not in item):
                function_body += f"        '{item['key']}': {item['key'].replace('-', '_')},\n"
            elif 'value' in item and 'description' not in item:
                function_body += f"        '{item['key']}': {item['key'].replace('-', '_')},\n"
        function_body += "    }\n\n"
    else:
        function_body += "    data = None\n\n"

    if headers:
        function_body += "    headers = {\n"
        for item in headers:
            function_body += f"        '{item['key']}': {item['key'].replace('-', '_')},\n"
        function_body += "    }\n\n"
    else:
        function_body += "    headers = None\n\n"

    if params:
        function_body += "    params = {\n"
        for item in params:
            if 'description' in item or ('value' not in item and 'description' not in item):
                function_body += f"        '{item['key']}': {item['key'].replace('-', '_')},\n"
            elif 'value' in item and 'description' not in item:
                function_body += f"        '{item['key']}': {item['key'].replace('-', '_')},\n"
        function_body += "    }\n\n"
    else:
        function_body += "    params = None\n\n"

    urlenc_present = any(
        header.get('value') == 'application/x-www-form-urlencoded'
        for header in headers
    )

    data_key = 'data' if urlenc_present else 'json'

    function_body += "    kwargs = {}\n"
    function_body += "    if data:\n"
    function_body += f"        kwargs['{data_key}'] = data\n"
    function_body += "    if headers:\n"
    function_body += "        kwargs['headers'] = headers\n"
    function_body += "    if params:\n"
    function_body += "        kwargs['params'] = params\n\n"

    VERB = api_json['api_request_type'].lower()
    ENDPOINT = api_json['api_endpoint']
    CONTENTS = "**kwargs"

    # Agregar logging simplificado para mostrar solo los datos enviados
    function_body += f"    # Log de datos enviados al API\n"
    function_body += f"    logging.info(f'🚀 API {api_json['api_name']}: {{data}}')\n"
    function_body += f"    \n"
    function_body += f"    start_time = time.time()\n"
    function_body += f"    \n"
    function_body += f"    try:\n"
    function_body += f"        response = requests.{VERB}('{ENDPOINT}',{CONTENTS}, timeout=30)\n"
    function_body += f"        execution_time = time.time() - start_time\n"
    function_body += f"        \n"
    function_body += f"        if response.status_code >= 200 and response.status_code < 300:\n"
    function_body += f"            logging.info(f'✅ API {api_json['api_name']} ejecutada exitosamente en {{execution_time:.2f}}s')\n"
    function_body += f"            try:\n"
    function_body += f"                response_json = response.json()\n"
    function_body += f"                return response_json\n"
    function_body += f"            except ValueError as json_error:\n"
    function_body += f"                response_text = response.text\n"
    function_body += f"                return response_text\n"
    function_body += f"        else:\n"
    function_body += f"            error_text = response.text\n"
    function_body += f"            logging.error(f'❌ API {api_json['api_name']} Error: Status {{response.status_code}}, Response: {{error_text}}')\n"
    function_body += f"            return {{'error': f'HTTP {{response.status_code}}: {{error_text}}', 'status_code': response.status_code}}\n"
    function_body += f"            \n"
    function_body += f"    except requests.exceptions.Timeout as timeout_error:\n"
    function_body += f"        logging.error(f'❌ API {api_json['api_name']} Timeout después de 30s')\n"
    function_body += f"        return {{'error': 'Timeout: La API no respondió en 30 segundos', 'timeout': True}}\n"
    function_body += f"        \n"
    function_body += f"    except requests.exceptions.ConnectionError as conn_error:\n"
    function_body += f"        logging.error(f'❌ API {api_json['api_name']} Connection Error: {{str(conn_error)}}')\n"
    function_body += f"        return {{'error': f'Error de conexión: {{str(conn_error)}}', 'connection_error': True}}\n"
    function_body += f"        \n"
    function_body += f"    except Exception as general_error:\n"
    function_body += f"        execution_time = time.time() - start_time\n"
    function_body += f"        logging.error(f'❌ API {api_json['api_name']} Error después de {{execution_time:.2f}}s: {{str(general_error)}}')\n"
    function_body += f"        return {{'error': f'Error general: {{str(general_error)}}', 'error_type': type(general_error).__name__}}\n"

    return function_body


def create_api_function(api_json):

    function_name = f'{api_json["api_name"].replace(" ", "_").lower()}_api'

    signature = f"def {function_name}("

    CONTENTS_LIST = (api_json['api_headers']
                     + api_json['api_parameters']
                     + api_json['api_body']
                     )

    non_default_args = []
    default_args = []

    for item in CONTENTS_LIST:
        key = item['key'].replace("-", "_")
        if 'description' in item or ('value' not in item and 'description' not in item):
            if 'value' in item:
                value = item['value']
                if value == "" or value == "''":
                    non_default_args.append(key)
                else:
                    default_args.append(f"{key}={repr(value)}")
            else:
                non_default_args.append(key)

    signature += ", ".join(non_default_args + default_args) + "):"

    function_str = signature + "\n"
    function_str += generate_docstring(api_json) + "\n"
    function_str += generate_function_body(api_json)

    exec_globals = {'requests': requests, 'logging': logging, 'time': time, 'json': json}
    exec(function_str, exec_globals)
    created_function = exec_globals[function_name]

    return created_function
