PREFIX_DATA_PROVIDED = """You are provided with the following data:"""
PREFIX_TASK_NEW_FEATURES = """Your task is to format this data into a structured text format that includes a """
PREFIX_TASK_FILL_CELLS = """Your task is to format this data into a structured text format and need to detect and fill empty data ('') of each fields: """

TEMPLATE_BUILD_NEW_FEATURES_FAQ= """Each entry should be clearly sectioned and include the whole question and 
the whole answer pair under the appropriate headers. 
Use the category to derive the title, keywords, and label. Also, generate a 
brief description relevant to the category, and include
creation metadata. Assume only today's date for metadata.
The language for all field should be spanish (for name field use english).
[WARNING] It is important to store the whole answer and question in their respectives fields, 
so you should create the json with the whole texts [WARNING]"""

TEMPLATE_BUILD_NEW_FEATURE_GEN_INFO = """Each entry should be clearly sectioned and include the whole content data under the appropiate header.
Use the content to derive the title, keywords, and label. 
Also, generate a brief description relevant to the category and content, and include
creation metadata. Assume only today's date for metadata.
The language for all field should be spanish (for name field use english).
[WARNING] It is important to store the whole content in their respectives fields, 
so you should create the json with the whole texts [WARNING]"""

TEMPLATE_FILL_CELLS= """Some fields will have values filled (which you must keep exactly) and others will be empty. 
You must intelligently detect fields with '' (wich means empty data) and fill using the information
from the other provided fields, you need to check avoiding redundancy and following the provided structure.
Assume today's date for metadata.
The language for all field should be spanish (for name field use english).
[WARNING] It is important to store the whole fields in their respectives fields, 
so you should create the json with the whole texts [WARNING]"""

TEMPLATE_RAW_DATA = """Here's the raw data:            
Date:{date}
desired structure output: \n{format_instructions}
data_shared: \n{raw_obj}"""

SYSTEM_PROMPT_VISION_MODEL = """Eres un sistema especializado en OCR (Reconocimiento Óptico de Caracteres). Tu tarea es:

1. Analizar la imagen proporcionada y extraer TODO el texto visible, incluyendo:
   - Títulos y encabezados
   - Texto del cuerpo
   - Tablas (convertir a texto estructurado)
   - Listas y viñetas
   - Cualquier otro elemento de texto

2. IMPORTANTE:
   - Extrae el texto EXACTAMENTE como aparece en la imagen
   - NO agregues ningún texto explicativo o comentarios
   - NO omitas ningún texto, incluso si parece poco importante
   - Si encuentras tablas, conviértelas a un formato de texto legible manteniendo la estructura de datos

3. Formato de salida:
   - Devuelve SOLO el texto extraído
   - NO incluyas ningún comentario o explicación
   - Mantén el idioma original del texto
   - Preserva los saltos de línea y la estructura original"""