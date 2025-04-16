import tiktoken

# Encoder global para evitar cargarlo múltiples veces
TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")

class TokenCounter:
    def __init__(self):
        self._cache = {}  # Cache para almacenar conteos de tokens

    def count_tokens(self, text):
        if not text:
            return 0
        
        # Si no es string, convertirlo
        if not isinstance(text, str):
            text = str(text)
        
        # Usar el texto como clave del cache
        cache_key = text
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        tokens = TOKEN_ENCODER.encode(text)
        token_count = len(tokens)
        
        # Guardar en cache
        self._cache[cache_key] = token_count
        return token_count

    def count_message_tokens(self, message):
        """Cuenta tokens de un mensaje incluyendo su rol y contenido"""
        if not message:
            return 0
        
        # Obtener el contenido del mensaje
        if isinstance(message, str):
            content = message
            role = 'user'
        else:
            content = message.content if hasattr(message, 'content') else str(message)
            role = message.type if hasattr(message, 'type') else 'user'
        
        # Contar tokens de metadatos si existen
        metadata_tokens = 0
        if hasattr(message, 'id') and message.id:
            metadata_tokens += self.count_tokens(str(message.id))
        if hasattr(message, 'timestamp') and message.timestamp:
            metadata_tokens += self.count_tokens(str(message.timestamp))
        if hasattr(message, 'conversation_id') and message.conversation_id:
            metadata_tokens += self.count_tokens(str(message.conversation_id))
        
        # Formato del mensaje como lo espera el modelo
        formatted_message = f"{role}: {content}"
        content_tokens = self.count_tokens(formatted_message)
        
        return content_tokens + metadata_tokens

    def count_system_prompt_tokens(self, prompt):
        """Cuenta tokens del prompt del sistema"""
        if not prompt:
            return 0
        formatted_prompt = f"system: {prompt}"
        return self.count_tokens(formatted_prompt)

    def count_conversation_tokens(self, messages):
        """Cuenta tokens de una conversación completa"""
        total_tokens = 0
        for msg in messages:
            total_tokens += self.count_message_tokens(msg)
        return total_tokens
        
    def count_tool_tokens(self, tool, separate=False):
        """
        Cuenta tokens de una herramienta
        
        Args:
            tool: La herramienta para contar tokens
            separate (bool): Si es True, devuelve un diccionario con input y output separados
            
        Returns:
            int o dict: Total de tokens o diccionario con input y output
        """
        if not tool:
            return 0 if not separate else {"input": 0, "output": 0}
            
        input_tokens = 0
        output_tokens = 0
        
        # Obtener entrada de la herramienta
        if hasattr(tool, 'input') and tool.input:
            input_tokens = self.count_tokens(str(tool.input))
        elif hasattr(tool, 'name') and tool.name:
            # Si no hay input explícito pero hay nombre, contar el nombre
            input_tokens = self.count_tokens(str(tool.name))
            # Si hay argumentos, contarlos también
            if hasattr(tool, 'args') and tool.args:
                input_tokens += self.count_tokens(str(tool.args))
                
        # Obtener salida de la herramienta
        if hasattr(tool, 'output') and tool.output:
            output_tokens = self.count_tokens(str(tool.output))
        elif hasattr(tool, 'result') and tool.result:
            output_tokens = self.count_tokens(str(tool.result))
            
        # Si no se ha podido separar, contar toda la herramienta
        if input_tokens == 0 and output_tokens == 0:
            total = self.count_tokens(str(tool))
            # Distribución estimada: 30% entrada, 70% salida
            input_tokens = int(total * 0.3)
            output_tokens = total - input_tokens
            
        if separate:
            return {"input": input_tokens, "output": output_tokens}
        else:
            return input_tokens + output_tokens
            
    def count_tools_tokens(self, tools, separate=False):
        """
        Cuenta tokens de una lista de herramientas
        
        Args:
            tools (list): Lista de herramientas
            separate (bool): Si es True, devuelve un diccionario con input y output separados
            
        Returns:
            int o dict: Total de tokens o diccionario con input y output
        """
        if not tools:
            return 0 if not separate else {"input": 0, "output": 0}
            
        total_input = 0
        total_output = 0
        
        for tool in tools:
            result = self.count_tool_tokens(tool, separate=True)
            total_input += result["input"]
            total_output += result["output"]
            
        if separate:
            return {"input": total_input, "output": total_output}
        else:
            return total_input + total_output
