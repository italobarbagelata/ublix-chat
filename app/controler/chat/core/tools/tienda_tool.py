from langchain.tools import tool
from typing import Dict, List, Any, Optional
import json
import asyncio
from datetime import datetime
import re
import logging
from supabase import create_client, Client

# Configuración de la tienda y Supabase
TIENDA_INFO = {
    "nombre": "TiendaModa.cl",
    "whatsapp": "+56 9 9824-4847",
    "email_ventas": "ventas@tiendamoda.cl",
    "ubicacion": "Plaza Quilicura, Santiago, Chile",
    "envio_gratis_desde": 50000,
    "dias_devolucion": 30
}

SUPABASE_CONFIG = {
    "url": "https://zzfrftcxksmurdeufjwu.supabase.co",
    "anon_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp6ZnJmdGN4a3NtdXJkZXVmand1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkxMzc4MjcsImV4cCI6MjA2NDcxMzgyN30.NMI9Y0euAutP4yKa85j6MqFv1VUHypZQoQ1SohHBzt0"
}

# Inicializar cliente Supabase
supabase: Client = create_client(SUPABASE_CONFIG["url"], SUPABASE_CONFIG["anon_key"])

class CarritoManager:
    def __init__(self):
        self.carrito_session = {}
        self.user_id = None
        self.session_id = None
    
    async def obtener_o_crear_carrito(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene o crea un carrito en Supabase"""
        try:
            # Generar session_id si no existe
            if not session_id:
                session_id = f'session_{int(datetime.now().timestamp())}_{hash(str(datetime.now()))}'
            
            # Buscar carrito existente
            query = supabase.table('carritos').select('*,items:items_carrito(*,variante:variantes_producto(*,producto:productos(*)))')
            
            if user_id:
                query = query.eq('usuario_id', user_id)
            else:
                query = query.eq('session_id', session_id)
            
            query = query.order('fecha_creacion', desc=True).limit(1)
            result = query.execute()
            
            # Si no existe carrito, crear uno nuevo
            if not result.data:
                nuevo_carrito = {
                    'usuario_id': user_id,
                    'session_id': session_id,
                    'total': 0,
                    'fecha_creacion': datetime.now().isoformat()
                }
                
                result = supabase.table('carritos').insert(nuevo_carrito).execute()
            
            self.user_id = user_id
            self.session_id = session_id
            return result.data[0]
            
        except Exception as e:
            logging.error(f"Error al obtener/crear carrito: {str(e)}")
            return None
    
    async def agregar_producto(self, producto_id: str, cantidad: int = 1, talla: Optional[str] = None, color: Optional[str] = None) -> Dict[str, Any]:
        """Agrega producto al carrito usando Supabase"""
        try:
            # 1. Obtener información del producto
            producto_result = supabase.table('productos').select('''
                id, nombre, descripcion, precio_regular, precio_oferta,
                categoria_id, activo, stock,
                categorias(nombre, slug),
                imagenes_producto(url, es_principal),
                variantes_producto(id, color, talla, precio_regular, precio_oferta, inventario:inventario(cantidad_disponible)),
                usuarios(nombre, apellido)
            ''').eq('id', producto_id).eq('activo', True).execute()
            
            if not producto_result.data:
                return {
                    "success": False,
                    "error": "Producto no encontrado o no disponible"
                }
            
            producto = producto_result.data[0]
            
            # 2. Buscar variante específica
            variante = None
            if producto.get('variantes_producto'):
                for v in producto['variantes_producto']:
                    if (not talla or v['talla'] == talla) and (not color or v['color'] == color):
                        variante = v
                        break
                
                if not variante and producto['variantes_producto']:
                    variante = producto['variantes_producto'][0]
            
            if not variante:
                return {
                    "success": False,
                    "error": "No se encontró la variante del producto"
                }
            
            # 3. Verificar stock
            stock_disponible = variante.get('inventario', [{}])[0].get('cantidad_disponible', 0)
            if stock_disponible < cantidad:
                return {
                    "success": False,
                    "error": f"Solo hay {stock_disponible} unidades disponibles"
                }
            
            # 4. Obtener o crear carrito
            carrito = await self.obtener_o_crear_carrito(self.user_id, self.session_id)
            if not carrito:
                return {
                    "success": False,
                    "error": "No se pudo obtener o crear el carrito"
                }
            
            # 5. Verificar si el producto ya está en el carrito
            items_existentes = supabase.table('items_carrito').select('*').eq('carrito_id', carrito['id']).eq('variante_producto_id', variante['id']).execute()
            
            if items_existentes.data:
                # Actualizar cantidad existente
                item = items_existentes.data[0]
                nueva_cantidad = item['cantidad'] + cantidad
                
                supabase.table('items_carrito').update({
                    'cantidad': nueva_cantidad,
                    'fecha_actualizacion': datetime.now().isoformat()
                }).eq('id', item['id']).execute()
            else:
                # Agregar nuevo item
                precio_unitario = variante.get('precio_oferta') or variante.get('precio_regular') or producto.get('precio_oferta') or producto.get('precio_regular')
                
                nuevo_item = {
                    'carrito_id': carrito['id'],
                    'variante_producto_id': variante['id'],
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'fecha_creacion': datetime.now().isoformat()
                }
                
                supabase.table('items_carrito').insert(nuevo_item).execute()
            
            # 6. Actualizar total del carrito
            await self.actualizar_total_carrito(carrito['id'])
            
            # 7. Obtener carrito actualizado
            carrito_actualizado = await self.obtener_carrito_completo(carrito['id'])
            
            return {
                "success": True,
                "mensaje": f"✅ {producto['nombre']} agregado al carrito",
                "carrito": carrito_actualizado
            }
            
        except Exception as e:
            logging.error(f"Error al agregar producto al carrito: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def actualizar_total_carrito(self, carrito_id: str) -> float:
        """Actualiza el total del carrito en Supabase"""
        try:
            # Obtener todos los items del carrito
            items = supabase.table('items_carrito').select('*').eq('carrito_id', carrito_id).execute()
            
            # Calcular total
            total = sum(item['cantidad'] * item['precio_unitario'] for item in items.data)
            
            # Actualizar total en carrito
            supabase.table('carritos').update({
                'total': total,
                'fecha_actualizacion': datetime.now().isoformat()
            }).eq('id', carrito_id).execute()
            
            return total
            
        except Exception as e:
            logging.error(f"Error al actualizar total del carrito: {str(e)}")
            return 0
    
    async def obtener_carrito_completo(self, carrito_id: str) -> Dict[str, Any]:
        """Obtiene el carrito completo con todos sus items"""
        try:
            carrito = supabase.table('carritos').select('''
                *,
                items:items_carrito(
                    *,
                    variante:variantes_producto(
                        *,
                        producto:productos(*)
                    )
                )
            ''').eq('id', carrito_id).execute()
            
            if not carrito.data:
                return None
            
            return carrito.data[0]
            
        except Exception as e:
            logging.error(f"Error al obtener carrito completo: {str(e)}")
            return None
    
    async def ver_carrito(self) -> Dict[str, Any]:
        """Muestra contenido del carrito"""
        try:
            carrito = await self.obtener_o_crear_carrito(self.user_id, self.session_id)
            if not carrito:
                return {
                    "vacio": True,
                    "mensaje": "Tu carrito está vacío 🛒\n\n¿Te gustaría ver nuestros productos destacados?"
                }
            
            carrito_completo = await self.obtener_carrito_completo(carrito['id'])
            if not carrito_completo or not carrito_completo.get('items'):
                return {
                    "vacio": True,
                    "mensaje": "Tu carrito está vacío 🛒\n\n¿Te gustaría ver nuestros productos destacados?"
                }
            
            total = carrito_completo['total']
            envio = 0 if total >= TIENDA_INFO["envio_gratis_desde"] else 3990
            
            texto = "🛒 **Tu carrito actual:**\n\n"
            for item in carrito_completo['items']:
                producto = item['variante']['producto']
                variante = item['variante']
                subtotal = item['cantidad'] * item['precio_unitario']
                
                texto += f"• {producto['nombre']}\n"
                texto += f"  {variante['color']} | {variante['talla']}\n"
                texto += f"  Cantidad: {item['cantidad']} × ${item['precio_unitario']:,} = ${subtotal:,}\n\n"
            
            texto += f"**Subtotal:** ${total:,} CLP\n"
            if envio > 0:
                texto += f"**Envío:** ${envio:,} CLP\n"
            else:
                texto += f"**Envío:** GRATIS 🎉\n"
            texto += f"**Total:** ${total + envio:,} CLP\n\n"
            texto += "¿Quieres proceder al checkout o seguir comprando? 🚀"
            
            return {
                "vacio": False,
                "items": carrito_completo['items'],
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
    
    async def eliminar_del_carrito(self, item_id: str) -> Dict[str, Any]:
        """Elimina un item del carrito"""
        try:
            # Obtener información del item antes de eliminarlo
            item = supabase.table('items_carrito').select('*,variante:variantes_producto(producto:productos(nombre))').eq('id', item_id).execute()
            
            if not item.data:
                return {
                    "success": False,
                    "error": "Item no encontrado en el carrito"
                }
            
            # Eliminar item
            supabase.table('items_carrito').delete().eq('id', item_id).execute()
            
            # Actualizar total del carrito
            carrito_id = item.data[0]['carrito_id']
            await self.actualizar_total_carrito(carrito_id)
            
            return {
                "success": True,
                "mensaje": f"❌ {item.data[0]['variante']['producto']['nombre']} eliminado del carrito"
            }
            
        except Exception as e:
            logging.error(f"Error al eliminar del carrito: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def aplicar_cupon(self, codigo_cupon: str) -> Dict[str, Any]:
        """Aplica un cupón de descuento al carrito"""
        try:
            # 1. Validar cupón
            fecha_actual = datetime.now().isoformat()
            cupon = supabase.table('cupones').select('*').eq('codigo', codigo_cupon).eq('activo', True).lte('fecha_inicio', fecha_actual).gte('fecha_fin', fecha_actual).execute()
            
            if not cupon.data:
                return {
                    "success": False,
                    "error": "Cupón no válido o expirado"
                }
            
            cupon = cupon.data[0]
            
            # 2. Obtener carrito actual
            carrito = await self.obtener_o_crear_carrito(self.user_id, self.session_id)
            if not carrito:
                return {
                    "success": False,
                    "error": "No se pudo obtener el carrito"
                }
            
            # 3. Verificar monto mínimo
            if cupon.get('monto_minimo_compra') and carrito['total'] < cupon['monto_minimo_compra']:
                return {
                    "success": False,
                    "error": f"Monto mínimo requerido: ${cupon['monto_minimo_compra']:,}"
                }
            
            # 4. Calcular descuento
            descuento = 0
            if cupon['tipo_descuento'] == 'porcentaje':
                descuento = carrito['total'] * (cupon['valor_descuento'] / 100)
            else:  # monto_fijo
                descuento = cupon['valor_descuento']
            
            # 5. Aplicar descuento
            nuevo_total = max(0, carrito['total'] - descuento)
            
            supabase.table('carritos').update({
                'total': nuevo_total,
                'descuento': descuento,
                'cupon_id': cupon['id'],
                'fecha_actualizacion': datetime.now().isoformat()
            }).eq('id', carrito['id']).execute()
            
            return {
                "success": True,
                "mensaje": f"✅ Cupón aplicado: {cupon['nombre']}",
                "descuento": descuento,
                "nuevo_total": nuevo_total
            }
            
        except Exception as e:
            logging.error(f"Error al aplicar cupón: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def calcular_envio(self, codigo_postal: str, region: str = 'RM') -> Dict[str, Any]:
        """Calcula el costo de envío para el carrito actual"""
        try:
            # 1. Obtener carrito actual
            carrito = await self.obtener_o_crear_carrito(self.user_id, self.session_id)
            if not carrito:
                return {
                    "success": False,
                    "error": "No se pudo obtener el carrito"
                }
            
            # 2. Obtener métodos de envío disponibles
            metodos = supabase.table('metodos_envio').select('*,tarifas:tarifas_envio(*)').eq('activo', True).execute()
            
            if not metodos.data:
                return {
                    "success": False,
                    "error": "No hay métodos de envío disponibles"
                }
            
            # 3. Calcular costos de envío
            opciones_envio = []
            for metodo in metodos.data:
                costo = metodo.get('precio', 0)
                
                # Envío gratis si supera el monto mínimo
                if metodo.get('gratis_desde_monto') and carrito['total'] >= metodo['gratis_desde_monto']:
                    costo = 0
                
                opciones_envio.append({
                    'id': metodo['id'],
                    'nombre': metodo['nombre'],
                    'descripcion': metodo['descripcion'],
                    'costo': costo,
                    'tiempo_estimado': f"{metodo.get('tiempo_estimado_min', 1)}-{metodo.get('tiempo_estimado_max', 3)} días",
                    'gratis': costo == 0
                })
            
            return {
                "success": True,
                "opciones": opciones_envio,
                "envio_gratis_desde": TIENDA_INFO["envio_gratis_desde"]
            }
            
        except Exception as e:
            logging.error(f"Error al calcular envío: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# Instancia global del carrito
carrito_manager = CarritoManager()

@tool
async def buscar_productos_tienda(query: str) -> str:
    """
    Busca productos en la tienda basado en una consulta en lenguaje natural.
    
    Args:
        query: Consulta en lenguaje natural (ej: "jeans talla 28 azules")
    
    Returns:
        str: Lista formateada de productos encontrados
    """
    try:
        # Extraer criterios de búsqueda
        criterios = {}
        query_lower = query.lower()
        
        # Buscar términos de productos
        productos_comunes = ["jean", "jeans", "blusa", "vestido", "zapatos", "zapatillas", "polera", "pantalón"]
        for producto in productos_comunes:
            if producto in query_lower:
                criterios["termino"] = producto
                break
        
        # Buscar tallas
        tallas_regex = r'\b(talla\s*)?(\d{1,2}|xs|s|m|l|xl|xxl)\b'
        match = re.search(tallas_regex, query_lower)
        if match:
            criterios["talla"] = match.group(2).upper()
        
        # Buscar colores
        colores = ["negro", "blanco", "azul", "rojo", "verde", "amarillo", "rosa", "gris"]
        for color in colores:
            if color in query_lower:
                criterios["color"] = color
                break
        
        # Construir consulta Supabase
        query_supabase = supabase.table('productos').select('''
            id, nombre, descripcion, precio_regular, precio_oferta,
            categoria_id, activo, stock,
            categorias(nombre, slug),
            imagenes_producto(url, es_principal),
            variantes_producto(color, talla, precio_regular, precio_oferta),
            usuarios(nombre, apellido)
        ''').eq('activo', True)
        
        # Aplicar filtros
        if criterios.get('termino'):
            query_supabase = query_supabase.ilike('nombre', f"%{criterios['termino']}%")
        
        if criterios.get('categoria'):
            query_supabase = query_supabase.eq('categorias.slug', criterios['categoria'])
        
        # Ejecutar consulta
        result = query_supabase.execute()
        productos = result.data
        
        if not productos:
            return "No encontré productos que coincidan con tu búsqueda. 😔\n\n¿Te gustaría probar con otros términos o ver nuestras categorías principales?"
        
        texto = f"Encontré {len(productos)} producto{'s' if len(productos) > 1 else ''} para ti:\n\n"
        
        for i, producto in enumerate(productos, 1):
            precio_mostrar = producto.get("precio_oferta") or producto.get("precio_regular")
            precio_original = producto.get("precio_regular")
            
            texto += f"{i}. 👗 **{producto['nombre']}**\n"
            
            if producto.get("precio_oferta") and precio_original != precio_mostrar:
                texto += f"   💰 ~~${precio_original:,}~~ **${precio_mostrar:,}** CLP\n"
            else:
                texto += f"   💰 **${precio_mostrar:,}** CLP\n"
            
            # Obtener variantes
            variantes = producto.get('variantes_producto', [])
            if variantes:
                variante = variantes[0]  # Tomar la primera variante por ahora
                texto += f"   📦 Condición: {producto.get('condicion', 'Nuevo')}\n"
                texto += f"   📏 Talla: {variante.get('talla', 'N/A')} | 🎨 Color: {variante.get('color', 'N/A')}\n"
            
            # Obtener vendedor
            vendedor = producto.get('usuarios', {})
            if vendedor:
                texto += f"   👤 Vendedora: {vendedor.get('nombre', '')} {vendedor.get('apellido', '')}\n"
            
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

@tool
async def gestionar_carrito(accion: str, producto_id: Optional[str] = None, cantidad: Optional[int] = 1, talla: Optional[str] = None, color: Optional[str] = None, codigo_cupon: Optional[str] = None) -> str:
    """
    Gestiona el carrito de compras.
    
    Args:
        accion: Acción a realizar (ver, agregar, eliminar, aplicar_cupon, calcular_envio)
        producto_id: ID del producto o nombre/descripción del producto (opcional, necesario para agregar/eliminar)
        cantidad: Cantidad a agregar (opcional, por defecto 1)
        talla: Talla del producto (opcional)
        color: Color del producto (opcional)
        codigo_cupon: Código del cupón a aplicar (opcional)
    
    Returns:
        str: Resultado de la operación en el carrito
    """
    try:
        if accion == "ver":
            return (await carrito_manager.ver_carrito())["mensaje"]
            
        elif accion == "agregar" and producto_id:
            # Si el producto_id no es un UUID válido, intentar buscar el producto por nombre
            if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', producto_id):
                # Buscar el producto por nombre
                query_supabase = supabase.table('productos').select('''
                    id, nombre, descripcion, precio_regular, precio_oferta,
                    categoria_id, activo, stock,
                    categorias(nombre, slug),
                    imagenes_producto(url, es_principal),
                    variantes_producto(color, talla, precio_regular, precio_oferta),
                    usuarios(nombre, apellido)
                ''').eq('activo', True).ilike('nombre', f"%{producto_id}%").limit(1).execute()
                
                if not query_supabase.data:
                    return f"❌ No encontré ningún producto que coincida con '{producto_id}'"
                
                # Usar el ID del producto encontrado
                producto_id = query_supabase.data[0]['id']
            
            resultado = await carrito_manager.agregar_producto(producto_id, cantidad, talla, color)
            if resultado["success"]:
                carrito_info = await carrito_manager.ver_carrito()
                return f"{resultado['mensaje']}\n\n{carrito_info['mensaje']}"
            else:
                return f"❌ Error: {resultado.get('error', 'No se pudo agregar el producto')}"
                
        elif accion == "eliminar" and producto_id:
            resultado = await carrito_manager.eliminar_del_carrito(producto_id)
            if resultado["success"]:
                carrito_info = await carrito_manager.ver_carrito()
                return f"{resultado['mensaje']}\n\n{carrito_info['mensaje']}"
            else:
                return f"❌ Error: {resultado.get('error', 'No se pudo eliminar el producto')}"
                
        elif accion == "aplicar_cupon" and codigo_cupon:
            resultado = await carrito_manager.aplicar_cupon(codigo_cupon)
            if resultado["success"]:
                carrito_info = await carrito_manager.ver_carrito()
                return f"{resultado['mensaje']}\n\n{carrito_info['mensaje']}"
            else:
                return f"❌ Error: {resultado.get('error', 'No se pudo aplicar el cupón')}"
                
        elif accion == "calcular_envio":
            resultado = await carrito_manager.calcular_envio("1234567")  # TODO: Obtener código postal real
            if resultado["success"]:
                texto = "🚚 **Opciones de envío disponibles:**\n\n"
                for opcion in resultado["opciones"]:
                    texto += f"• {opcion['nombre']}\n"
                    texto += f"  {opcion['descripcion']}\n"
                    if opcion['gratis']:
                        texto += f"  💰 GRATIS 🎉\n"
                    else:
                        texto += f"  💰 ${opcion['costo']:,} CLP\n"
                    texto += f"  ⏱️ {opcion['tiempo_estimado']}\n\n"
                
                texto += f"🎉 **ENVÍO GRATIS** en compras sobre ${resultado['envio_gratis_desde']:,} CLP"
                return texto
            else:
                return f"❌ Error: {resultado.get('error', 'No se pudieron calcular las opciones de envío')}"
                
        else:
            return "❌ Acción no válida o falta información necesaria"
            
    except Exception as e:
        logging.error(f"Error en gestión del carrito: {str(e)}")
        return "❌ Lo siento, tuve un problema con el carrito. ¿Podrías intentar de nuevo?" 