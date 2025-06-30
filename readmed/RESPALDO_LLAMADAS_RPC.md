# 📡 RESPALDO DE LLAMADAS RPC EN UBLIX-CHAT

## 🎯 **OBJETIVO**
Documentar todas las llamadas RPC existentes en el código Python para facilitar mantenimiento y debug.

---

## 📋 **FUNCIONES RPC UTILIZADAS EN EL CÓDIGO**

### 🔍 **1. BÚSQUEDA Y MATCHING**

#### `search_all_content_unified`
**Archivo:** `app/controler/chat/core/tools/unified_search_tool.py`
```python
response = supabase_client.rpc(
    'search_all_content_unified',
    {
        'query_embedding': embedding_array,
        'query_text': query,
        'project_id_filter': project_id,
        'content_types': content_types,
        'match_count': limit,
        'similarity_threshold': 0.3
    }
).execute()
```

#### `match_documents_v20`
**Archivo:** `app/controler/chat/core/tools/retriever_tool.py`
```python
response = supabase_client.rpc(
    'match_documents_v20',
    {
        'query_embedding': embedding_array,
        'match_count': limit,
        'project_id_filter': project_id
    }
).execute()
```

**Archivo:** `app/resources/vectorstore.py`
```python
rpc_response = self.supabase.rpc(
    'match_documents_v20',
    {
        'query_embedding': query_embedding,
        'match_count': k,
        'project_id_filter': project_id
    }
).execute()
```

#### `match_documents_hybrid`
**Archivo:** `app/controler/chat/core/tools/products_fallback_tool.py`
```python
search_result = db.supabase.rpc(
    'match_documents_hybrid',
    {
        'query_embedding': embedding_array,
        'query_text': query,
        'match_count': 10,
        'project_id_filter': project_id,
        'type_filter': 'product',
        'category_filter': None,
        'similarity_threshold': 0.3
    }
).execute()
```

**Archivo:** `app/resources/productstore.py`
```python
rpc_response = self.supabase.rpc(
    'match_documents_hybrid',
    {
        'query_embedding': query_embedding,
        'query_text': query_text,
        'match_count': k,
        'project_id_filter': project_id,
        'type_filter': 'product',
        'category_filter': category_filter,
        'similarity_threshold': similarity_threshold
    }
).execute()
```

### ❓ **2. FAQ**

#### `search_faqs_semantic`
**Archivo:** `app/controler/chat/core/tools/faq_retriever_tool.py`
```python
response = supabase_client.rpc(
    'search_faqs_semantic',
    {
        'query_embedding': str(embedding_array),
        'project_id_param': project_id,
        'similarity_threshold': 0.7,
        'limit_param': limit,
        'offset_param': 0
    }
).execute()
```

### 👤 **3. CONTACTOS**

#### `get_contact_field_config`
**Archivo:** `app/controler/chat/services/contact_service.py`
```python
response = self.client.client.rpc(
    'get_contact_field_config', 
    {'project_uuid': project_id}
).execute()
```

---

## 🗺️ **MAPEO DE USO POR HERRAMIENTA**

| **Herramienta** | **RPC Utilizado** | **Propósito** |
|---|---|---|
| `unified_search_tool` | `search_all_content_unified` | Búsqueda híbrida en documentos, FAQs y productos |
| `retriever_tool` | `match_documents_v20` | Búsqueda semántica en documentos |
| `faq_retriever_tool` | `search_faqs_semantic` | Búsqueda específica en FAQs |
| `products_fallback_tool` | `match_documents_hybrid` | Búsqueda híbrida en productos |
| `agente_producto` | `match_documents_hybrid` | Búsqueda de productos con filtros |
| `contact_service` | `get_contact_field_config` | Configuración de campos dinámicos |
| `vectorstore` | `match_documents_v20` | Búsqueda vectorial general |
| `productstore` | `match_documents_hybrid` | Búsqueda de productos avanzada |

---

## 🔧 **PARÁMETROS COMUNES**

### **Parámetros de Búsqueda Vectorial:**
- `query_embedding`: Vector de embedding (array o string)
- `match_count`/`limit_param`: Número máximo de resultados
- `project_id_filter`/`project_id_param`: Filtro por proyecto
- `similarity_threshold`: Umbral mínimo de similitud

### **Parámetros de Búsqueda Híbrida:**
- `query_text`: Texto de búsqueda adicional
- `type_filter`: Filtro por tipo ('product', 'document', 'faq')
- `category_filter`: Filtro por categoría
- `content_types`: Array de tipos de contenido a buscar

### **Parámetros de Contactos:**
- `project_uuid`: UUID del proyecto para configuración

---

## 🚨 **ERRORES COMUNES Y SOLUCIONES**

### **Error: Function not found**
```sql
-- Verificar que la función existe
SELECT proname FROM pg_proc WHERE proname = 'nombre_funcion';
```

### **Error: Parameter type mismatch**
```python
# Convertir embedding a formato correcto
embedding_array = [float(x) for x in embedding]  # Para array
# O
embedding_str = str(embedding)  # Para string en FAQs
```

### **Error: Project ID filter**
```python
# Asegurar que project_id sea UUID válido
import uuid
project_id = str(uuid.UUID(project_id))
```

---

## 📈 **ESTADÍSTICAS DE USO**

- **Total RPC únicos:** 4 funciones principales
- **Archivos que usan RPC:** 8 archivos
- **Herramientas que dependen de RPC:** 6 herramientas
- **Función más usada:** `match_documents_v20` (3 archivos)
- **Función más compleja:** `search_all_content_unified` (más parámetros)

---

## 🔄 **DEPENDENCIAS ENTRE RPC**

1. **search_all_content_unified** → Depende de tabla `search_items`
2. **match_documents_v20** → Depende de tabla `search_items` 
3. **get_contact_field_config** → Depende de tabla `contact_field_configs`
4. **search_faqs_semantic** → Depende de tabla `search_items` (type='faq')

---

## 📝 **NOTAS DE MANTENIMIENTO**

### **Al agregar nueva RPC:**
1. Añadir al archivo `RESPALDO_FUNCIONES_RPC.sql`
2. Documentar en este archivo
3. Actualizar tests si aplica
4. Verificar permisos en Supabase

### **Al modificar RPC existente:**
1. Verificar impacto en todos los archivos que la usan
2. Actualizar documentación
3. Probar en desarrollo antes de producción

### **Backup recomendado:**
- Ejecutar respaldo mensual de todas las funciones
- Versionar cambios en funciones críticas
- Documentar dependencias externas

---

**Última actualización:** 2025-01-28  
**Total de llamadas RPC documentadas:** 11 instancias 