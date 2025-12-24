"""
DeepSeek AI Service for Trading Decision Making
"""
import httpx
from typing import Optional, Dict, Any, List
from app.core.logging_config import logger


class DeepSeekService:
    """Service for interacting with DeepSeek API for trading analysis"""
    
    BASE_URL = "https://api.deepseek.com/v1/chat/completions"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def analyze_trading_opportunity(
        self,
        symbol: str,
        current_price: float,
        indicators: Dict[str, Any],
        recent_trades: List[Dict],
        market_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analiza una oportunidad de trading usando DeepSeek AI
        
        Args:
            symbol: Símbolo del par (ej: BTCUSDT)
            current_price: Precio actual
            indicators: Indicadores técnicos (RSI, MACD, Bollinger, etc.)
            recent_trades: Lista de trades recientes del usuario
            market_context: Contexto del mercado (volumen, tendencia, etc.)
        
        Returns:
            Dict con:
            - recommendation: "BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL"
            - confidence: 0.0-1.0
            - reasoning: Explicación del razonamiento
            - risk_assessment: "LOW", "MEDIUM", "HIGH"
            - suggested_entry: Precio sugerido de entrada
            - suggested_stop_loss: Stop loss sugerido
            - suggested_take_profit: Take profit sugerido
        """
        
        # Construir prompt con toda la información relevante
        prompt = self._build_analysis_prompt(
            symbol=symbol,
            current_price=current_price,
            indicators=indicators,
            recent_trades=recent_trades,
            market_context=market_context
        )
        
        try:
            response = await self.client.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": self._get_system_prompt()
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,  # Bajo para decisiones más consistentes
                    "max_tokens": 1000
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extraer respuesta del modelo
            ai_response = data["choices"][0]["message"]["content"]
            
            # Parsear respuesta estructurada
            return self._parse_ai_response(ai_response)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"DeepSeek API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"DeepSeek API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {e}")
            raise
    
    def _get_system_prompt(self) -> str:
        """Prompt del sistema que define el rol del AI"""
        return """Eres un experto analista de trading de criptomonedas con años de experiencia. 
Tu trabajo es analizar oportunidades de trading basándote en:
1. Indicadores técnicos (RSI, MACD, Bollinger Bands, EMA)
2. Contexto del mercado (volumen, tendencia, volatilidad)
3. Historial reciente de trades del usuario
4. Gestión de riesgo

Debes responder SIEMPRE en formato JSON con esta estructura exacta:
{
    "recommendation": "BUY|SELL|HOLD|STRONG_BUY|STRONG_SELL",
    "confidence": 0.0-1.0,
    "reasoning": "Explicación clara y concisa de tu análisis",
    "risk_assessment": "LOW|MEDIUM|HIGH",
    "suggested_entry": precio_sugerido,
    "suggested_stop_loss": precio_stop_loss,
    "suggested_take_profit": precio_take_profit
}

Sé conservador y prioriza la gestión de riesgo sobre ganancias rápidas."""
    
    def _build_analysis_prompt(
        self,
        symbol: str,
        current_price: float,
        indicators: Dict[str, Any],
        recent_trades: List[Dict],
        market_context: Dict[str, Any]
    ) -> str:
        """Construye el prompt de análisis con toda la información"""
        
        # Formatear indicadores
        rsi_info = f"RSI: {indicators.get('rsi', {}).get('value', 'N/A'):.2f} ({'Oversold' if indicators.get('rsi', {}).get('oversold') else 'Overbought' if indicators.get('rsi', {}).get('overbought') else 'Neutral'})"
        
        macd_info = f"MACD: {indicators.get('macd', {}).get('trend', 'N/A')}, Histogram: {indicators.get('macd', {}).get('histogram', 0):.4f}"
        
        bb_info = f"Bollinger: Precio {indicators.get('bollinger_bands', {}).get('position', 'N/A')}, Upper: {indicators.get('bollinger_bands', {}).get('upper_band', 0):.2f}, Lower: {indicators.get('bollinger_bands', {}).get('lower_band', 0):.2f}"
        
        # Formatear trades recientes
        trades_summary = ""
        if recent_trades:
            winning = sum(1 for t in recent_trades if t.get('profit_loss', 0) > 0)
            losing = sum(1 for t in recent_trades if t.get('profit_loss', 0) < 0)
            trades_summary = f"\nTrades recientes: {len(recent_trades)} totales ({winning} ganadores, {losing} perdedores)"
        
        prompt = f"""Analiza esta oportunidad de trading:

Símbolo: {symbol}
Precio actual: ${current_price:,.2f}

Indicadores técnicos:
- {rsi_info}
- {macd_info}
- {bb_info}
- EMA Signal: {indicators.get('ema', {}).get('signal', 'N/A')}

Contexto del mercado:
- Volumen 24h: {market_context.get('volume_24h', 'N/A')}
- Tendencia: {market_context.get('trend', 'N/A')}
- Volatilidad: {market_context.get('volatility', 'N/A')}
{trades_summary}

¿Cuál es tu recomendación? Considera:
1. ¿Los indicadores técnicos son consistentes?
2. ¿El contexto del mercado es favorable?
3. ¿El riesgo es aceptable?
4. ¿Hay suficiente confianza para ejecutar?

Responde en formato JSON como se especificó."""
        
        return prompt
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """Parsea la respuesta del AI a un formato estructurado"""
        import json
        import re
        
        try:
            # Intentar extraer JSON de la respuesta
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                
                # Validar y normalizar
                return {
                    "recommendation": parsed.get("recommendation", "HOLD").upper(),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "reasoning": parsed.get("reasoning", "No reasoning provided"),
                    "risk_assessment": parsed.get("risk_assessment", "MEDIUM").upper(),
                    "suggested_entry": float(parsed.get("suggested_entry", 0)),
                    "suggested_stop_loss": float(parsed.get("suggested_stop_loss", 0)),
                    "suggested_take_profit": float(parsed.get("suggested_take_profit", 0))
                }
            else:
                # Si no hay JSON, intentar parsear texto libre
                return self._parse_text_response(response_text)
                
        except Exception as e:
            logger.warning(f"Error parsing AI response: {e}, using fallback")
            return self._parse_text_response(response_text)
    
    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """Fallback: parsea respuesta de texto libre"""
        import re
        text_upper = text.upper()
        
        recommendation = "HOLD"
        if "STRONG BUY" in text_upper or "FUERTE COMPRA" in text_upper:
            recommendation = "STRONG_BUY"
        elif "BUY" in text_upper or "COMPRA" in text_upper:
            recommendation = "BUY"
        elif "STRONG SELL" in text_upper or "FUERTE VENTA" in text_upper:
            recommendation = "STRONG_SELL"
        elif "SELL" in text_upper or "VENTA" in text_upper:
            recommendation = "SELL"
        
        # Extraer confianza si está mencionada
        confidence = 0.5
        confidence_match = re.search(r'(\d+(?:\.\d+)?)%', text)
        if confidence_match:
            confidence = float(confidence_match.group(1)) / 100
        
        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "reasoning": text[:500],  # Primeros 500 caracteres
            "risk_assessment": "MEDIUM",
            "suggested_entry": 0,
            "suggested_stop_loss": 0,
            "suggested_take_profit": 0
        }
    
    async def test_connection(self) -> bool:
        """Prueba la conexión con DeepSeek API"""
        try:
            response = await self.client.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "user",
                            "content": "Responde solo con 'OK' si puedes leer esto."
                        }
                    ],
                    "max_tokens": 10
                }
            )
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"DeepSeek connection test failed: {e}")
            return False
    
    async def close(self):
        """Cierra la conexión HTTP"""
        await self.client.aclose()

