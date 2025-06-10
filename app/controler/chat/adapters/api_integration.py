import requests
import logging
import re
import json

def create_api_function(api_json):
    def extract_placeholders_from_json(json_string):
        """Extrae placeholders {{variable}} de un string JSON"""
        if not isinstance(json_string, str):
            return []
        
        # Buscar placeholders con formato {{variable_name}}
        placeholders = re.findall(r'\{\{(\w+)\}\}', json_string)
        return list(set(placeholders))  # Eliminar duplicados
    
    def generate_docstring(headers, params, body, json_placeholders=None):
        # Asegurar que todos los parámetros sean listas
        headers = headers if isinstance(headers, list) else []
        params = params if isinstance(params, list) else []
        body = body if isinstance(body, list) else []
        json_placeholders = json_placeholders or []
        
        docstring = f"Executes a {api_json['api_request_type']} request to {api_json['api_name']} API.\n\n"
        docstring += f"{api_json['api_description']}\n\n"
        docstring += "Parameters:\n"
        
        # Agregar placeholders del JSON como parámetros
        for placeholder in json_placeholders:
            docstring += f"    {placeholder}: Variable para reemplazar en el cuerpo JSON\n"
        
        for item in headers+params+body:
            if 'description' in item:
                if item['description'] != "":
                    param_name = item['key']
                    description = item['description']
                    if 'value' in item and item["value"] != "":
                        description += f" (default value: {item['value']})"
                    docstring += f"    {param_name}: {description}\n"
                else:
                    continue
        
        return docstring

    def generate_function_body(headers, params, body, raw_body=None, json_placeholders=None):
        # Asegurar que todos los parámetros sean listas
        headers = headers if isinstance(headers, list) else []
        params = params if isinstance(params, list) else []
        body = body if isinstance(body, list) else []
        json_placeholders = json_placeholders or []
        
        function_body = ""

        # Si hay un raw_body (JSON string), usarlo directamente
        if raw_body and isinstance(raw_body, str):
            try:
                # Verificar que sea JSON válido (con placeholders reemplazados temporalmente)
                temp_body = raw_body
                for placeholder in json_placeholders:
                    temp_body = temp_body.replace(f"{{{{{placeholder}}}}}", "placeholder_value")
                json.loads(temp_body)
                
                # Generar código para reemplazar placeholders dinámicamente
                if json_placeholders:
                    function_body += "    # Preparar el cuerpo JSON con variables\n"
                    function_body += "    import json\n"
                    function_body += f"    json_template = {repr(raw_body)}\n"
                    for placeholder in json_placeholders:
                        function_body += f"    json_template = json_template.replace('{{{{{placeholder}}}}}', str({placeholder}))\n"
                    function_body += "    data = json.loads(json_template)\n\n"
                else:
                    function_body += f"    data = {raw_body}\n\n"
                logging.info(f"Usando raw_body como JSON con {len(json_placeholders)} placeholders: {raw_body[:100]}...")
            except json.JSONDecodeError:
                logging.warning(f"raw_body no es JSON válido, usando body lista: {raw_body[:100]}...")
                function_body += "    data = {\n"
                for item in body:
                    if 'description' in item or ('value' not in item and 'description' not in item):
                        function_body += f"        '{item['key']}': {item['key']},\n"
                    elif 'value' in item and 'description' not in item:
                        function_body += f"        '{item['key']}': {item['key']},\n"
                function_body += "    }\n\n"
        else:
            function_body += "    data = {\n"
            for item in body:
                if 'description' in item or ('value' not in item and 'description' not in item):
                    function_body += f"        '{item['key']}': {item['key']},\n"
                elif 'value' in item and 'description' not in item:
                    function_body += f"        '{item['key']}': {item['key']},\n"
            function_body += "    }\n\n"

        # Prepare headers
        if headers:
            function_body += "    headers = {\n"
            for item in headers:
                function_body += f"        '{item['key']}':'{item['value']}',\n"
            function_body += "    }\n\n"
        else:
            function_body += "    headers = {}\n\n"

        # Prepare params
        if params:
            function_body += "    params = {\n"
            for item in params:
                if 'description' in item or ('value' not in item and 'description' not in item):
                    function_body += f"        '{item['key']}': {item['key']},\n"
                elif 'value' in item and 'description' not in item:
                    function_body += f"        '{item['key']}': {item['key']},\n"
            function_body += "    }\n\n"
                 
        else:
            function_body += "    params = {}\n\n"

        # Make the request with error handling
        function_body += f"    response = requests.{api_json['api_request_type'].lower()}('{api_json['api_endpoint']}', json=data, headers=headers, params=params)\n"
        function_body += "    try:\n"
        function_body += "        # Check content type to handle different response formats\n"
        function_body += "        content_type = response.headers.get('content-type', '').lower()\n"
        function_body += "        if 'application/json' in content_type:\n"
        function_body += "            # JSON response\n"
        function_body += "            if response.text.strip():\n"
        function_body += "                return response.json()\n"
        function_body += "            else:\n"
        function_body += "                return {'status': response.status_code, 'message': 'Empty JSON response'}\n"
        function_body += "        elif 'text/plain' in content_type:\n"
        function_body += "            # Plain text response\n"
        function_body += "            return {'status': response.status_code, 'message': 'Text response received', 'content': response.text}\n"
        function_body += "        else:\n"
        function_body += "            # Other content types\n"
        function_body += "            if response.text.strip():\n"
        function_body += "                try:\n"
        function_body += "                    return response.json()\n"
        function_body += "                except ValueError:\n"
        function_body += "                    return {'status': response.status_code, 'message': f'Non-JSON response with content-type: {content_type}', 'content': response.text}\n"
        function_body += "            else:\n"
        function_body += "                return {'status': response.status_code, 'message': 'Empty response with content-type: ' + content_type}\n"
        function_body += "    except ValueError as e:\n"
        function_body += "        return {'status': response.status_code, 'message': f'Invalid JSON response: {str(e)}', 'content': response.text}\n"

        return function_body

    function_name = f'{api_json["api_name"].replace(" ","_").lower()}_api'

    # Generate the function signature
    signature = f"def {function_name}("
    non_default_args = []
    default_args = []
    
    # Asegurar que api_parameters y api_body sean listas
    api_parameters = api_json.get('api_parameters', [])
    raw_api_body = api_json.get('api_body', [])
    api_body = []
    
    if not isinstance(api_parameters, list):
        logging.warning(f"api_parameters no es una lista: {type(api_parameters)}, convirtiendo a lista vacía")
        api_parameters = []
    
    # Manejar api_body - puede ser lista o string JSON
    json_placeholders = []
    if isinstance(raw_api_body, list):
        api_body = raw_api_body
        raw_api_body = None
    elif isinstance(raw_api_body, str):
        logging.info(f"api_body es string JSON, lo mantendré para usar directamente")
        # Extraer placeholders del JSON
        json_placeholders = extract_placeholders_from_json(raw_api_body)
        if json_placeholders:
            logging.info(f"Placeholders encontrados en api_body: {json_placeholders}")
        api_body = []  # Lista vacía para parámetros, pero usaré raw_api_body para el cuerpo
    else:
        logging.warning(f"api_body no es lista ni string: {type(raw_api_body)}, convirtiendo a lista vacía")
        api_body = []
        raw_api_body = None
    
    # Combinar parámetros tradicionales con placeholders del JSON
    all_params = api_parameters + api_body
    for item in all_params:
        if 'description' in item or ('value' not in item and 'description' not in item):
            if 'value' in item:
                value = item['value']
                if value == "" or value == "''":
                    # Treat empty strings as non-default arguments
                    non_default_args.append(item['key'])
                else:
                    # Parameter has a default value
                    default_args.append(f"{item['key']}={repr(value)}")
            else:
                # No default value provided
                non_default_args.append(item['key'])
    
    # Agregar placeholders del JSON como parámetros obligatorios
    for placeholder in json_placeholders:
        non_default_args.append(placeholder)
    
    # Combine non-default and default arguments in the correct order
    signature += ", ".join(non_default_args + default_args) + "):"

    # Asegurar que api_headers también sea una lista
    api_headers = api_json.get('api_headers', [])
    if not isinstance(api_headers, list):
        logging.warning(f"api_headers no es una lista: {type(api_headers)}, convirtiendo a lista vacía")
        api_headers = []
    
    # Generate the complete function
    function_str = signature + "\n"
    function_str += '    """' + generate_docstring(api_headers, api_parameters, api_body, json_placeholders) + '    """' + "\n"
    function_str += generate_function_body(api_headers, api_parameters, api_body, raw_api_body, json_placeholders)
    logging.info("function_str signature")
    logging.info(signature)
    # Create the function object
    exec_globals = {'requests': requests}
    exec(function_str, exec_globals)
    created_function = exec_globals[function_name]

    return created_function
