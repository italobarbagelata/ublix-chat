import requests
import logging

def create_api_function(api_json):
    def generate_docstring(headers, params, body):
        docstring = f"Executes a {api_json['api_request_type']} request to {api_json['api_name']} API.\n\n"
        docstring += f"{api_json['api_description']}\n\n"
        docstring += "Parameters:\n"
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

    def generate_function_body(headers, params, body):
        function_body = ""

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
    for item in api_json['api_parameters'] + api_json['api_body']:
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
    # Combine non-default and default arguments in the correct order
    signature += ", ".join(non_default_args + default_args) + "):"

    # Generate the complete function
    function_str = signature + "\n"
    function_str += '    """' + generate_docstring(api_json['api_headers'], api_json['api_parameters'], api_json['api_body']) + '    """' + "\n"
    function_str += generate_function_body(api_json['api_headers'], api_json['api_parameters'], api_json['api_body'])
    logging.info("function_str signature")
    logging.info(signature)
    # Create the function object
    exec_globals = {'requests': requests}
    exec(function_str, exec_globals)
    created_function = exec_globals[function_name]

    return created_function
