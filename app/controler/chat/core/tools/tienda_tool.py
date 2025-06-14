from langchain.tools import tool
from typing import Dict, List, Any, Optional
import json
import asyncio
from datetime import datetime
import re
import logging

# Configuración de la tienda
TIENDA_INFO = {
    "nombre": "TiendaModa.cl",
    "whatsapp": "+56 9 9824-4847",
    "email_ventas": "ventas@tiendamoda.cl",
    "ubicacion": "Plaza Quilicura, Santiago, Chile",
    "envio_gratis_desde": 50000,
    "dias_devolucion": 30
}

class CarritoManager:
    def __init__(self):
        self.carrito_session = {}
    
    def agregar_producto(self, producto_id: str, producto_info: Dict) -> Dict[str, Any]:
        """Agrega producto al carrito"""
        try:
            if producto_id in self.carrito_session:
                self.carrito_session[producto_id]["quantity"] += 1
            else:
                self.carrito_session[producto_id] = {
                    "name": producto_info["nombre"],
                    "price": producto_info.get("precio_oferta") or producto_info["precio_regular"],
                    "quantity": 1,
                    "condition": producto_info["condicion"],
                    "variants": f"{producto_info.get('color', '')} | {producto_info.get('talla', '')}"
                }
            
            return {
                "success": True,
                "mensaje": f"✅ {producto_info['nombre']} agregado al carrito"
            }
        except Exception as e:
            logging.error(f"Error al agregar producto al carrito: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def ver_carrito(self) -> Dict[str, Any]:
        """Muestra contenido del carrito"""
        try:
            if not self.carrito_session:
                return {
                    "vacio": True,
                    "mensaje": "Tu carrito está vacío 🛒\n\n¿Te gustaría ver nuestros productos destacados?"
                }
            
            total = sum(item["price"] * item["quantity"] for item in self.carrito_session.values())
            envio = 0 if total >= TIENDA_INFO["envio_gratis_desde"] else 3990
            
            texto = "🛒 **Tu carrito actual:**\n\n"
            for item_id, item in self.carrito_session.items():
                subtotal = item["price"] * item["quantity"]
                texto += f"• {item['name']}\n"
                texto += f"  {item['variants']} | {item['condition']}\n"
                texto += f"  Cantidad: {item['quantity']} × ${item['price']:,} = ${subtotal:,}\n\n"
            
            texto += f"**Subtotal:** ${total:,} CLP\n"
            if envio > 0:
                texto += f"**Envío:** ${envio:,} CLP\n"
            else:
                texto += f"**Envío:** GRATIS 🎉\n"
            texto += f"**Total:** ${total + envio:,} CLP\n\n"
            texto += "¿Quieres proceder al checkout o seguir comprando? 🚀"
            
            return {
                "vacio": False,
                "items": self.carrito_session,
                "subtotal": total,
                "envio": envio,
                "total": total + envio,
                "mensaje": texto
            }
        except Exception as e:
            logging.error(f"Error al ver carrito: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

@tool
def buscar_productos_tienda(query: str) -> str:
    """
    Busca productos en la tienda basado en una consulta en lenguaje natural.
    
    Args:
        query: Consulta en lenguaje natural (ej: "jeans talla 28 azules")
    
    Returns:
        str: Lista formateada de productos encontrados
    """
    try:
        # Aquí iría la lógica real de búsqueda en la base de datos
        # Por ahora usamos datos de ejemplo
        productos_ejemplo = [
            {
                "id": "prod_001",
                "nombre": "Jean Skinny Azul",
                "precio_regular": 25990,
                "precio_oferta": None,
                "condicion": "Seminuevo",
                "categoria": "Jeans",
                "talla": "28",
                "color": "Azul",
                "stock": 1,
                "vendedor": "María González"
            },
            {
                "id": "prod_002", 
                "nombre": "Jean Mom Fit Negro",
                "precio_regular": 32990,
                "precio_oferta": 28990,
                "condicion": "Nuevo",
                "categoria": "Jeans",
                "talla": "28",
                "color": "Negro",
                "stock": 2,
                "vendedor": "Ana Pérez"
            }
        ]
        
        if not productos_ejemplo:
            return "No encontré productos que coincidan con tu búsqueda. 😔\n\n¿Te gustaría probar con otros términos o ver nuestras categorías principales?"
        
        texto = f"Encontré {len(productos_ejemplo)} producto{'s' if len(productos_ejemplo) > 1 else ''} para ti:\n\n"
        
        for i, producto in enumerate(productos_ejemplo, 1):
            precio_mostrar = producto.get("precio_oferta") or producto.get("precio_regular")
            precio_original = producto.get("precio_regular")
            
            texto += f"{i}. 👗 **{producto['nombre']}**\n"
            
            if producto.get("precio_oferta") and precio_original != precio_mostrar:
                texto += f"   💰 ~~${precio_original:,}~~ **${precio_mostrar:,}** CLP\n"
            else:
                texto += f"   💰 **${precio_mostrar:,}** CLP\n"
                
            texto += f"   📦 Condición: {producto['condicion']}\n"
            texto += f"   📏 Talla: {producto['talla']} | 🎨 Color: {producto['color']}\n"
            texto += f"   👤 Vendedora: {producto['vendedor']}\n"
            texto += f"   📦 Stock: {producto['stock']} disponible{'s' if producto['stock'] > 1 else ''}\n\n"
        
        texto += "¿Te gustaría ver detalles de alguno o que agregue algún producto a tu carrito? 🛒"
        return texto
        
    except Exception as e:
        logging.error(f"Error en búsqueda de productos: {str(e)}")
        return "❌ Lo siento, tuve un problema buscando productos. ¿Podrías intentar de nuevo?"

@tool
def consultar_info_tienda(tipo_consulta: str) -> str:
    """
    Proporciona información general sobre la tienda.
    
    Args:
        tipo_consulta: Tipo de consulta (contacto, devoluciones, envio, general)
    
    Returns:
        str: Información formateada sobre el tema consultado
    """
    try:
        respuestas = {
            "contacto": f"""
📞 **Información de Contacto:**

• **WhatsApp:** {TIENDA_INFO['whatsapp']}
• **Email Ventas:** {TIENDA_INFO['email_ventas']}
• **Ubicación:** {TIENDA_INFO['ubicacion']}

¿En qué más puedo ayudarte? 😊
            """,
            
            "devoluciones": f"""
🔄 **Política de Devoluciones:**

• ✅ **{TIENDA_INFO['dias_devolucion']} días** para devolver
• 🆓 **Devolución GRATUITA** para productos elegibles
• ⚡ **48 horas** para reportar problemas
• 💰 **Reembolso en 5-7 días hábiles**

**Requisitos:**
- Producto sin usar y con etiquetas
- Empaque original
- Comprobante de compra

¿Necesitas ayuda con alguna devolución específica?
            """,
            
            "envio": f"""
🚚 **Información de Envío:**

• 🎉 **ENVÍO GRATIS** en compras sobre ${TIENDA_INFO['envio_gratis_desde']:,}
• 🏠 **A domicilio** en todo Chile
• 🚇 **Metro Quilicura** (retiro gratuito)
• 📮 **Sucursal Correos** (retiro en oficina postal)

**Tiempos de entrega:**
- Santiago: 1-3 días hábiles
- Regiones: 3-7 días hábiles

¿Tienes alguna pregunta sobre tu envío?
            """,
            
            "general": f"""
¡Hola! 👋 Soy Sofía, tu asistente en {TIENDA_INFO['nombre']}.

Somos una plataforma de **moda circular** que ofrece:
• 🆕 **Productos NUEVOS**: Temporadas anteriores, sin uso
• ✨ **SEMINUEVOS**: Casi nuevos, usados máximo 1-2 veces  
• 💎 **SEGUNDA MANO**: Con historia, excelente estado

**Nuestra misión:** Promover moda sostenible y economía circular 🌱

¿Te gustaría ver nuestros productos o tienes alguna pregunta específica?
            """
        }
        
        return respuestas.get(tipo_consulta, respuestas["general"])
        
    except Exception as e:
        logging.error(f"Error en consulta de información: {str(e)}")
        return "❌ Lo siento, tuve un problema procesando tu consulta. ¿Podrías intentar de nuevo?"

# Instancia global del carrito
carrito_manager = CarritoManager()

@tool
def gestionar_carrito(accion: str, producto_id: Optional[str] = None) -> str:
    """
    Gestiona el carrito de compras.
    
    Args:
        accion: Acción a realizar (ver, agregar, eliminar)
        producto_id: ID del producto (opcional, necesario para agregar/eliminar)
    
    Returns:
        str: Resultado de la operación en el carrito
    """
    try:
        if accion == "ver":
            return carrito_manager.ver_carrito()["mensaje"]
            
        elif accion == "agregar" and producto_id:
            # Aquí iría la lógica real para obtener el producto de la base de datos
            producto_ejemplo = {
                "id": producto_id,
                "nombre": "Jean Skinny Azul",
                "precio_regular": 25990,
                "condicion": "Seminuevo",
                "talla": "28",
                "color": "Azul"
            }
            
            resultado = carrito_manager.agregar_producto(producto_id, producto_ejemplo)
            if resultado["success"]:
                carrito_info = carrito_manager.ver_carrito()
                return f"{resultado['mensaje']}\n\n{carrito_info['mensaje']}"
            else:
                return f"❌ Error: {resultado.get('error', 'No se pudo agregar el producto')}"
                
        elif accion == "eliminar" and producto_id:
            if producto_id in carrito_manager.carrito_session:
                producto_eliminado = carrito_manager.carrito_session.pop(producto_id)
                return f"❌ {producto_eliminado['name']} eliminado del carrito"
            else:
                return "❌ Producto no encontrado en el carrito"
                
        else:
            return "❌ Acción no válida o falta información necesaria"
            
    except Exception as e:
        logging.error(f"Error en gestión del carrito: {str(e)}")
        return "❌ Lo siento, tuve un problema con el carrito. ¿Podrías intentar de nuevo?" 