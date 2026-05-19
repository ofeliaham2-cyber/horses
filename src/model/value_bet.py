"""
SIPH-Antigravity - Lógica de Valor Implícito (Value Bet)
Agente 4: Detección de Fugas de Valor
"""
import pandas as pd

def detect_value_leaks(predictions_df: pd.DataFrame, results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compara la probabilidad proyectada por nuestro ensamble IA contra la probabilidad 
    implícita del mercado (1 / dividendo_final). 
    Detecta Fugas de Valor para retroalimentar los tensores XGBoost.
    
    Args:
        predictions_df (pd.DataFrame): Dataframe con predicciones ['ejemplar_id', 'nombre', 'probabilidad_modelo']
        results_df (pd.DataFrame): Dataframe con dividendos finales ['ejemplar_id', 'dividendo_final']
        
    Returns:
        pd.DataFrame: Dataframe filtrado con las apuestas de valor (edge > 0)
    """
    print("[*] Cruzando probabilidades del modelo con mercado consolidado...")
    
    df = pd.merge(predictions_df, results_df, on='ejemplar_id')
    
    # Calcular probabilidad implícita (1 / Dividendo), manejando división por cero
    df['probabilidad_implicita'] = df['dividendo_final'].apply(lambda x: 1/x if x > 0 else 0)
    
    # Detectar fuga de valor: Nuestro modelo da MAYOR probabilidad que el mercado
    df['fuga_de_valor'] = df['probabilidad_modelo'] > df['probabilidad_implicita']
    
    # Margen de valor (Edge)
    df['edge'] = df['probabilidad_modelo'] - df['probabilidad_implicita']
    
    # Filtrar solo fugas de valor válidas donde hay un dividendo válido pagado al ganador
    value_bets = df[(df['fuga_de_valor'] == True) & (df['dividendo_final'] > 0)].copy()
    
    # Ordenar por el mayor Edge de ganancia a largo plazo
    value_bets.sort_values(by='edge', ascending=False, inplace=True)
    
    print(f"[+] Detectadas {len(value_bets)} fugas de valor.")
    return value_bets

if __name__ == "__main__":
    # Test Standalone
    preds = pd.DataFrame([
        {"ejemplar_id": 11, "nombre": "Modelo Del Salto", "probabilidad_modelo": 0.40}, # 40% (Ours)
        {"ejemplar_id": 3, "nombre": "Afirmate Gato", "probabilidad_modelo": 0.15},     # 15% (Ours)
    ])
    
    res = pd.DataFrame([
        {"ejemplar_id": 11, "dividendo_final": 5.00}, # 1/5 = 0.20 (20% Implied)
        {"ejemplar_id": 3, "dividendo_final": 2.50},  # 1/2.5 = 0.40 (40% Implied)
    ])
    
    fugas = detect_value_leaks(preds, res)
    print("\n[ 🚨 FUGAS DE VALOR DETECTADAS (POST-MORTEM) ]")
    print(fugas[['nombre', 'probabilidad_modelo', 'probabilidad_implicita', 'dividendo_final', 'edge']])
