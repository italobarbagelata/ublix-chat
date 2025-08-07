# 📱 Ejemplo de Uso - Obtener Información de Usuario de Instagram

## 1. Script de Prueba Directa

Ejecuta el script `test_ig_api_direct.py` para probar directamente la API:

```bash
python3 test_ig_api_direct.py
```

Necesitarás:
- **ID de usuario de Instagram**: El ID del usuario (ej: `17841401234567890`)
- **Access Token**: Tu token de acceso de Instagram

## 2. Script de Prueba con tu Sistema

Ejecuta el script `test_instagram_user.py` para probar la función integrada:

```bash
python3 test_instagram_user.py
```

Necesitarás:
- **ID de usuario de Instagram**: El ID del usuario
- **Project ID**: El ID de tu proyecto en la base de datos

## 3. Información que Obtendrás

La función `get_instagram_user_info` retornará un diccionario con:

```python
{
    "id": "17841401234567890",
    "name": "Juan Pérez",
    "username": "juanperez"
}
```

## 4. Cómo se Usa en el Webhook

Cuando llega un mensaje de Instagram, automáticamente:

1. Se extrae el `sender_id` del mensaje
2. Se llama a `get_instagram_user_info(sender_id, project_id)`
3. Se obtiene el nombre real del usuario
4. Se usa ese nombre en la conversación con el chatbot

## 5. Verificar en los Logs

Cuando proceses un mensaje, verás en los logs algo como:

```
INFO - Obteniendo información del usuario de Instagram: 17841401234567890
INFO - Información del usuario obtenida: Juan Pérez (@juanperez)
INFO - Procesando contenido del mensaje - Tipo: text, Usuario: 17841401234567890
```

## 6. Probar con un Webhook Real

Para probar con un mensaje real de Instagram:

1. Envía un mensaje a tu cuenta de Instagram Business
2. Revisa los logs del servidor
3. Verifica que aparezca el nombre real del usuario

## 7. Debugging

Si no funciona, verifica:

1. **Token válido**: El token debe tener permisos para leer información de usuarios
2. **Configuración en BD**: Debe existir la configuración en `integration_instagram`
3. **Project ID correcto**: El project_id debe coincidir con tu configuración

## 8. Ejemplo de Prueba Manual con cURL

```bash
# Obtener información de un usuario específico
curl -X GET \
  "https://graph.instagram.com/v23.0/{USER_ID}?fields=id,username,name&access_token={ACCESS_TOKEN}"

# Verificar tu token
curl -X GET \
  "https://graph.instagram.com/v23.0/me?fields=id,username,name&access_token={ACCESS_TOKEN}"
```

## Notas Importantes

- La información se cachea por 7 días para reducir llamadas a la API
- Si falla la API, se usa un nombre genérico
- El username de Instagram se muestra en el chat como el nombre del usuario