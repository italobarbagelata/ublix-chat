"""
Sistema avanzado de detección de intenciones para el Router Inteligente.
Mejora la precisión de detección incluso con errores tipográficos y contexto ambiguo.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class IntentCategory(Enum):
    """Categorías de intenciones mejoradas."""
    BOOKING = "booking"
    SCHEDULE_INQUIRY = "schedule_inquiry"  # Solo consultar horarios
    SCHEDULE_CONFIRM = "schedule_confirm"  # Confirmar agendamiento
    CONTACT_UPDATE = "contact_update"
    GENERAL_INQUIRY = "general_inquiry"
    SUPPORT = "support"
    UNKNOWN = "unknown"

@dataclass
class IntentMatch:
    """Resultado de detección de intención."""
    category: IntentCategory
    confidence: float
    keywords_matched: List[str]
    patterns_matched: List[str]
    context_factors: Dict[str, float]
    is_typo_corrected: bool = False
    original_phrase: str = ""
    corrected_phrase: str = ""

class FuzzyIntentDetector:
    """
    Detector de intenciones con corrección de errores tipográficos y análisis contextual.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Palabras clave para cada intención con corrección de errores
        self.intent_keywords = {
            IntentCategory.BOOKING: {
                'primary': [
                    'agendar', 'reservar', 'cita', 'agenda', 'book', 'schedule',
                    'appointment', 'reserve', 'confirmar', 'confirmo'
                ],
                'secondary': [
                    'horario', 'disponible', 'libre', 'available', 'time',
                    'hora', 'cuando', 'puedo', 'puede', 'podemos'
                ],
                'temporal': [
                    'mañana', 'hoy', 'lunes', 'martes', 'miércoles', 'jueves',
                    'viernes', 'sábado', 'domingo', 'today', 'tomorrow'
                ]
            },
            IntentCategory.SCHEDULE_INQUIRY: {
                'primary': [
                    'horarios', 'disponibilidad', 'libres', 'available',
                    'qué horarios', 'que horarios', 'tienes disponible'
                ],
                'question_words': [
                    'qué', 'que', 'cuáles', 'cuales', 'when', 'what', 'which'
                ]
            },
            IntentCategory.SCHEDULE_CONFIRM: {
                'primary': [
                    'decidí', 'decidi', 'elijo', 'quiero', 'vamos', 'perfecto',
                    'está bien', 'esta bien', 'confirmo', 'yes', 'sí', 'si'
                ],
                'temporal_decision': [
                    'para el', 'a las', 'at', 'on', 'el', 'este', 'esa'
                ]
            }
        }
        
        # Patrones regex robustos
        self.intent_patterns = {
            IntentCategory.BOOKING: [
                r'\b(agendar|reservar|cita|agenda)\b.*\b(para|el|a las)\b',
                r'\b(quiero|necesito|puedo)\b.*\b(agendar|cita|reunión)\b',
                r'\b(agenda|schedule|book)\b.*\b(appointment|meeting|cita)\b',
                r'\b(decidí|decidi|elijo)\b.*\b(para el|a las)\b'
            ],
            IntentCategory.SCHEDULE_INQUIRY: [
                r'\b(qué|que|cuáles|cuales)\b.*\b(horarios|disponibles|libres)\b',
                r'\b(tienes|hay|están)\b.*\b(disponible|libre|horarios)\b',
                r'\b(para el|para)\b.*\b(qué horarios|que horarios)\b'
            ],
            IntentCategory.SCHEDULE_CONFIRM: [
                r'\b(ya\s+)?(decidí|decidi|elijo|quiero)\b.*\b(para|el|a las)\b',
                r'\b(vamos|dale|perfecto|está bien|esta bien)\b.*\b(para|el|a las)\b',
                r'\b(confirmo|confirm|yes|sí|si)\b.*\b(para|el|a las)\b'
            ]
        }
        
        # Corrector de errores tipográficos común
        self.typo_corrections = {
            'decici': 'decidí',
            'pouedes': 'puedes',
            'pouede': 'puede',
            'cira': 'cita',
            'agendar': 'agendar',
            'orarios': 'horarios',
            'dispnible': 'disponible',
            'miercoles': 'miércoles',
            'madrtes': 'martes',
            'luns': 'lunes'
        }
    
    def detect_intent(self, text: str, conversation_context: Optional[List[str]] = None) -> IntentMatch:
        """
        Detecta la intención principal del texto con corrección de errores.
        
        Args:
            text: Texto del usuario
            conversation_context: Mensajes previos para contexto
            
        Returns:
            IntentMatch con la detección más probable
        """
        if not text:
            return IntentMatch(
                category=IntentCategory.UNKNOWN,
                confidence=0.0,
                keywords_matched=[],
                patterns_matched=[],
                context_factors={}
            )
        
        # Preprocesar texto
        original_text = text
        corrected_text, typos_found = self._correct_typos(text.lower())
        
        # Analizar contexto conversacional
        context_factors = self._analyze_conversation_context(conversation_context or [])
        
        # Detectar intenciones con múltiples métodos
        keyword_results = self._analyze_keywords(corrected_text, context_factors)
        pattern_results = self._analyze_patterns(corrected_text)
        contextual_boost = self._apply_contextual_boost(keyword_results, pattern_results, context_factors)
        
        # Combinar resultados
        final_result = self._combine_detection_methods(
            keyword_results, pattern_results, contextual_boost
        )
        
        # Agregar información de corrección de errores
        final_result.is_typo_corrected = len(typos_found) > 0
        final_result.original_phrase = original_text
        final_result.corrected_phrase = corrected_text if len(typos_found) > 0 else original_text
        
        self.logger.info(f"🎯 Intent detectado: {final_result.category.value} (confianza: {final_result.confidence:.2f})")
        if typos_found:
            self.logger.info(f"🔧 Errores corregidos: {typos_found}")
        
        return final_result
    
    def _correct_typos(self, text: str) -> Tuple[str, List[str]]:
        """Corrige errores tipográficos comunes."""
        corrected_text = text
        typos_found = []
        
        # Correcciones directas
        for typo, correction in self.typo_corrections.items():
            if typo in corrected_text:
                corrected_text = corrected_text.replace(typo, correction)
                typos_found.append(f"{typo} → {correction}")
        
        # Corrección difusa para palabras clave importantes
        words = corrected_text.split()
        corrected_words = []
        
        for word in words:
            best_match = self._find_fuzzy_match(word)
            if best_match and best_match != word:
                corrected_words.append(best_match)
                typos_found.append(f"{word} → {best_match}")
            else:
                corrected_words.append(word)
        
        corrected_text = ' '.join(corrected_words)
        return corrected_text, typos_found
    
    def _find_fuzzy_match(self, word: str) -> Optional[str]:
        """Encuentra coincidencia difusa para palabras clave importantes."""
        if len(word) < 4:  # Skip palabras muy cortas
            return None
        
        # Lista de palabras importantes para fuzzy matching
        important_words = []
        for category_keywords in self.intent_keywords.values():
            for keyword_list in category_keywords.values():
                important_words.extend(keyword_list)
        
        best_match = None
        best_ratio = 0.7  # Umbral mínimo de similitud
        
        for important_word in important_words:
            ratio = SequenceMatcher(None, word, important_word).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = important_word
        
        return best_match
    
    def _analyze_keywords(self, text: str, context_factors: Dict[str, float]) -> Dict[IntentCategory, float]:
        """Analiza palabras clave para detectar intenciones."""
        scores = {category: 0.0 for category in IntentCategory}
        
        for category, keyword_groups in self.intent_keywords.items():
            category_score = 0.0
            
            for group_name, keywords in keyword_groups.items():
                group_weight = {
                    'primary': 1.0,
                    'secondary': 0.6,
                    'temporal': 0.4,
                    'question_words': 0.5,
                    'temporal_decision': 0.8
                }.get(group_name, 0.5)
                
                matches = sum(1 for keyword in keywords if keyword in text)
                group_score = matches * group_weight
                category_score += group_score
            
            # Aplicar boost contextual
            if 'recent_scheduling' in context_factors:
                if category in [IntentCategory.BOOKING, IntentCategory.SCHEDULE_CONFIRM]:
                    category_score *= (1 + context_factors['recent_scheduling'])
            
            scores[category] = min(category_score, 1.0)  # Cap at 1.0
        
        return scores
    
    def _analyze_patterns(self, text: str) -> Dict[IntentCategory, float]:
        """Analiza patrones regex para detectar intenciones."""
        scores = {category: 0.0 for category in IntentCategory}
        
        for category, patterns in self.intent_patterns.items():
            pattern_matches = 0
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    pattern_matches += 1
            
            # Normalizar score
            if patterns:
                scores[category] = min(pattern_matches / len(patterns), 1.0)
        
        return scores
    
    def _analyze_conversation_context(self, conversation_history: List[str]) -> Dict[str, float]:
        """Analiza el contexto conversacional para mejorar detección."""
        context_factors = {}
        
        if not conversation_history:
            return context_factors
        
        # Analizar mensajes recientes (últimos 3)
        recent_messages = conversation_history[-3:]
        all_text = ' '.join(recent_messages).lower()
        
        # Factor: conversación reciente sobre agendamiento
        scheduling_keywords = ['horario', 'disponible', 'cita', 'agenda', 'lunes', 'martes', 'miércoles']
        scheduling_mentions = sum(1 for keyword in scheduling_keywords if keyword in all_text)
        context_factors['recent_scheduling'] = min(scheduling_mentions / 5.0, 0.5)
        
        # Factor: preguntas pendientes
        question_pattern = r'\?|qué|que|cuál|cual|cuándo|cuando'
        if re.search(question_pattern, all_text):
            context_factors['pending_question'] = 0.3
        
        return context_factors
    
    def _apply_contextual_boost(self, keyword_scores: Dict[IntentCategory, float], 
                              pattern_scores: Dict[IntentCategory, float],
                              context_factors: Dict[str, float]) -> Dict[IntentCategory, float]:
        """Aplica boost contextual a los scores."""
        boosted_scores = {}
        
        for category in IntentCategory:
            base_score = max(keyword_scores[category], pattern_scores[category])
            boost = 0.0
            
            # Boost para agendamiento si hay contexto previo
            if category in [IntentCategory.BOOKING, IntentCategory.SCHEDULE_CONFIRM]:
                boost += context_factors.get('recent_scheduling', 0.0)
                boost += context_factors.get('pending_question', 0.0)
            
            boosted_scores[category] = min(base_score + boost, 1.0)
        
        return boosted_scores
    
    def _combine_detection_methods(self, keyword_scores: Dict[IntentCategory, float],
                                 pattern_scores: Dict[IntentCategory, float],
                                 contextual_scores: Dict[IntentCategory, float]) -> IntentMatch:
        """Combina todos los métodos de detección para resultado final."""
        
        # Combinar scores con pesos
        final_scores = {}
        keywords_matched = []
        patterns_matched = []
        
        for category in IntentCategory:
            # Weighted combination
            final_score = (
                keyword_scores[category] * 0.4 +
                pattern_scores[category] * 0.4 +
                contextual_scores[category] * 0.2
            )
            final_scores[category] = final_score
        
        # Encontrar la mejor categoría
        best_category = max(final_scores.keys(), key=lambda x: final_scores[x])
        best_confidence = final_scores[best_category]
        
        # Si la confianza es muy baja, marcar como UNKNOWN
        if best_confidence < 0.3:
            best_category = IntentCategory.UNKNOWN
            best_confidence = 0.0
        
        return IntentMatch(
            category=best_category,
            confidence=best_confidence,
            keywords_matched=keywords_matched,
            patterns_matched=patterns_matched,
            context_factors=contextual_scores
        )
    
    def get_required_tools(self, intent_match: IntentMatch) -> List[str]:
        """Determina qué herramientas se requieren para la intención detectada."""
        tool_mapping = {
            IntentCategory.BOOKING: ['agenda_tool', 'save_contact_tool'],
            IntentCategory.SCHEDULE_INQUIRY: ['agenda_tool'],
            IntentCategory.SCHEDULE_CONFIRM: ['agenda_tool', 'save_contact_tool'],
            IntentCategory.CONTACT_UPDATE: ['save_contact_tool'],
            IntentCategory.GENERAL_INQUIRY: ['current_datetime_tool'],
            IntentCategory.SUPPORT: ['current_datetime_tool'],
            IntentCategory.UNKNOWN: ['current_datetime_tool']
        }
        
        return tool_mapping.get(intent_match.category, ['current_datetime_tool'])

# Instancia global del detector
fuzzy_intent_detector = FuzzyIntentDetector()