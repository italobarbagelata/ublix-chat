#!/usr/bin/env python3
"""
Script para debuggear cómo se procesa "a las 2" en el sistema
"""

import sys
import os
sys.path.append('/Users/italo/ublix/ublix-chat')

import re
from datetime import datetime, timedelta
import pytz
import dateparser

def test_dateparser_behavior():
    """Prueba cómo dateparser maneja diferentes formatos de tiempo"""
    print("=== PRUEBA DE DATEPARSER ===")
    
    chile_tz = pytz.timezone('America/Santiago')
    now = datetime.now(chile_tz)
    
    test_cases = [
        "a las 2",
        "a las 2:00", 
        "a las 14:00",
        "a las 02:00",
        "a las 2 PM",
        "a las 2 AM",
        "reunión a las 2",
        "cita a las 2"
    ]
    
    for test in test_cases:
        print(f"\nInput: '{test}'")
        
        # Parsear con dateparser
        result = dateparser.parse(
            test,
            languages=['es'],
            settings={'TIMEZONE': 'America/Santiago'}
        )
        
        if result:
            print(f"  Dateparser result: {result.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Hour: {result.hour}")
            print(f"  As ISO: {result.isoformat()}")
        else:
            print("  Dateparser: No se pudo parsear")

def test_regex_extraction():
    """Prueba la extracción de hora con regex del calendar_tool"""
    print("\n=== PRUEBA DE REGEX EXTRACTION ===")
    
    def detect_time_preference_from_title(title):
        if not title:
            return False, None, None
        
        title_lower = title.lower()
        
        # Patrones del sistema actual
        time_patterns = [
            r'a las (\d{1,2}):?(\d{0,2})',  # "a las 14:00" o "a las 14"
            r'(\d{1,2}):(\d{2})\s*h',       # "14:00h"
            r'(\d{1,2})\s*horas?',          # "14 horas"
            r'las (\d{1,2}):?(\d{0,2})',    # "las 14:00"
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, title_lower)
            if match:
                try:
                    hour = int(match.group(1))
                    minute = int(match.group(2)) if match.group(2) else 0
                    
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        return True, hour, minute
                except (ValueError, IndexError):
                    continue
        
        return False, None, None
    
    test_cases = [
        "reunión a las 2",
        "cita a las 2:00",
        "reunión a las 14:00",
        "cita a las 02:00",
        "reunión las 2",
        "cita las 14"
    ]
    
    for test in test_cases:
        print(f"\nInput: '{test}'")
        found, hour, minute = detect_time_preference_from_title(test)
        
        if found:
            print(f"  Regex extraction: {hour}:{minute:02d}")
            
            # Simular lógica del sistema
            default_start_hour = 9
            default_end_hour = 18
            
            print(f"  Horario laboral: {default_start_hour}:00 - {default_end_hour}:00")
            
            if default_start_hour <= hour <= default_end_hour:
                print(f"  ✅ Hora {hour}:00 está en horario laboral")
            else:
                print(f"  ❌ Hora {hour}:00 FUERA del horario laboral")
                
                # Verificar si sería viable convertir a PM
                if hour < 12:
                    pm_hour = hour + 12
                    if default_start_hour <= pm_hour <= default_end_hour:
                        print(f"  💡 Posible conversión: {hour}:00 → {pm_hour}:00")
                    else:
                        print(f"  ❌ Conversión {hour}:00 → {pm_hour}:00 también fuera del horario")
        else:
            print("  No se detectó hora específica")

def test_combined_behavior():
    """Prueba el comportamiento combinado del sistema"""
    print("\n=== PRUEBA DE COMPORTAMIENTO COMBINADO ===")
    
    # Simular entrada del usuario
    user_input = "reunión a las 2"
    
    print(f"Usuario dice: '{user_input}'")
    
    # 1. Dateparser
    parsed_date = dateparser.parse(
        user_input,
        languages=['es'],
        settings={'TIMEZONE': 'America/Santiago'}
    )
    
    if parsed_date:
        print(f"1. Dateparser: {parsed_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   ISO: {parsed_date.isoformat()}")
    else:
        print("1. Dateparser: No pudo parsear")
    
    # 2. Regex extraction
    def extract_specific_time(text):
        if not text:
            return None, None
        
        patterns = [r'a las (\d{1,2}):?(\d{0,2})']
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    hour = int(match.group(1))
                    minute = int(match.group(2)) if match.group(2) else 0
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        return hour, minute
                except (ValueError, IndexError):
                    continue
        return None, None
    
    hour, minute = extract_specific_time(user_input)
    if hour is not None:
        print(f"2. Regex extraction: {hour}:{minute:02d}")
        
        # 3. Aplicar lógica del sistema
        default_start_hour = 9
        default_end_hour = 18
        
        print(f"3. Horario laboral: {default_start_hour}:00 - {default_end_hour}:00")
        
        if default_start_hour <= hour <= default_end_hour:
            print(f"   ✅ Sistema buscaría a las {hour}:00")
        else:
            print(f"   ❌ Sistema NO buscaría a las {hour}:00")
            print(f"   📋 Sistema buscaría solo en rango {default_start_hour}:00 - {default_end_hour}:00")
    else:
        print("2. Regex extraction: No se detectó hora específica")

if __name__ == "__main__":
    test_dateparser_behavior()
    test_regex_extraction()
    test_combined_behavior()