"""
Configuración global de timezone para el sistema de agenda y calendario.
Esta constante permite controlar qué timezone usa todo el sistema.
"""

# TIMEZONE GLOBAL DEL SISTEMA
# Cambiar este valor para modificar el timezone de toda la aplicación
SISTEMA_TIMEZONE = "-04:00"  # Horario de invierno de Chile (julio = invierno)
# SISTEMA_TIMEZONE = "-03:00"  # Horario de verano de Chile (cambio temporal para solucionar inconsistencia)

def get_sistema_timezone() -> str:
    """
    Obtiene el timezone configurado para todo el sistema.
    
    Returns:
        str: Timezone en formato ISO (ej: "-03:00")
    """
    return SISTEMA_TIMEZONE

def get_sistema_timezone_offset() -> int:
    """
    Obtiene el offset del timezone del sistema en horas.
    
    Returns:
        int: Offset en horas (ej: -3 para -03:00)
    """
    return int(SISTEMA_TIMEZONE.split(":")[0])