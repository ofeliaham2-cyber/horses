"""
SIPH-Antigravity - Módulo de Modelado y Simulación Monte Carlo
Implementa un ensamble inicial híbrido (heurística/XGBoost-mock) y
simulación estocástica para predicción de Quinela Box con confianza >85%.
"""

import numpy as np
import time
from typing import List, Dict

class MonteCarloPredictor:
    def __init__(self, n_simulations: int = 10000):
        self.n_simulations = n_simulations
        
    def _mock_xgboost_score(self, irp: float, fcc: float, synergy: float) -> float:
        """
        Simula la salida de un modelo XGBoost utilizando pesos heurísticos.
        """
        # Suavizado básico: si la sinergia es 0 absoluto, aplicamos un piso mínimo
        if float(synergy) == 0.0:
            synergy = 0.05

        # Pesos heurísticos: Ponderamos con mayor fuerza el IRP
        w_irp, w_fcc, w_syn = 0.75, 0.15, 0.10
        
        # Base score: Mayor es mejor (probabilidad / performance index)
        score = (irp * w_irp) + (fcc * w_fcc) + (synergy * w_syn)
        return score

    def run_simulation(self, field_data: List[Dict], box_numbers: List[int]) -> float:
        """
        Ejecuta simulación Monte Carlo introduciendo ruido gaussiano.
        Calcula la probabilidad de que los lugares 1° y 2° sean ocupados 
        por cualquiera de los caballos en 'box_numbers'.
        """
        print(f"[*] Iniciando Simulación Monte Carlo ({self.n_simulations} ejecuciones)...")
        start_time = time.time()
        
        horses = []
        for horse in field_data:
            base_score = self._mock_xgboost_score(horse['irp'], horse['fcc'], horse.get('synergy', 0.0))
            horses.append({
                'number': horse['number'],
                'name': horse['name'],
                'score': base_score,
                'sigma': horse['sigma']
            })
            
        # Optimización mediante vectorización con NumPy
        n_horses = len(horses)
        base_scores = np.array([h['score'] for h in horses])
        
        # Amplificamos el Sigma para darle un mayor peso relativo (penaliza/beneficia la varianza)
        sigmas = np.array([h['sigma'] for h in horses]) * 1.5
        
        horse_numbers = np.array([h['number'] for h in horses])
        
        # Generar ruido gaussiano para todas las simulaciones y caballos
        # Matriz [n_simulations, n_horses]
        noise = np.random.normal(loc=0.0, scale=sigmas, size=(self.n_simulations, n_horses))

        
        # Resultados simulados
        simulated_scores = base_scores + noise
        
        # Encontramos los top 2 para cada simulación (mayor score = mejor posición)
        # argpartition es más eficiente que argsort para encontrar los Top K
        # Negamos los scores porque argpartition ordena de menor a mayor
        top_2_indices = np.argpartition(-simulated_scores, 2, axis=1)[:, :2]
        
        box_hits = 0
        box_set = set(box_numbers)
        
        # Contamos cuántas veces los caballos en las posiciones 1 y 2 están en nuestro Box
        for i in range(self.n_simulations):
            pos1_idx = top_2_indices[i, 0]
            pos2_idx = top_2_indices[i, 1]
            
            num1 = horse_numbers[pos1_idx]
            num2 = horse_numbers[pos2_idx]
            
            if num1 in box_set and num2 in box_set:
                box_hits += 1
                
        confidence = (box_hits / self.n_simulations) * 100
        elapsed = time.time() - start_time
        
        print(f"[+] Simulación completada en {elapsed:.4f} segundos.")
        return confidence

if __name__ == "__main__":
    # Mock del tensor del Agente 2 para la Carrera 1
    # Cuarteto óptimo (min varianza): [11] Modelo Del Salto, [3] Afirmate Gato, [5] Sasuke, [2] Justinsito Crack
    
    mock_field = [
        # Nuestro Box (Alta probabilidad base, baja varianza)
        {"number": 11, "name": "Modelo Del Salto", "irp": 0.92, "fcc": 0.88, "synergy": 0.90, "sigma": 0.02},
        {"number": 3, "name": "Afirmate Gato", "irp": 0.89, "fcc": 0.85, "synergy": 0.88, "sigma": 0.03},
        {"number": 5, "name": "Sasuke", "irp": 0.87, "fcc": 0.86, "synergy": 0.84, "sigma": 0.035},
        {"number": 2, "name": "Justinsito Crack", "irp": 0.85, "fcc": 0.82, "synergy": 0.86, "sigma": 0.04},
        
        # Resto del field (Menor probabilidad base, mayor varianza/ruido)
        {"number": 1, "name": "Caballo 1", "irp": 0.70, "fcc": 0.65, "synergy": 0.70, "sigma": 0.15},
        {"number": 4, "name": "Caballo 4", "irp": 0.68, "fcc": 0.60, "synergy": 0.65, "sigma": 0.12},
        {"number": 6, "name": "Caballo 6", "irp": 0.75, "fcc": 0.70, "synergy": 0.68, "sigma": 0.10},
        {"number": 7, "name": "Caballo 7", "irp": 0.60, "fcc": 0.55, "synergy": 0.50, "sigma": 0.20},
        {"number": 8, "name": "Caballo 8", "irp": 0.65, "fcc": 0.62, "synergy": 0.60, "sigma": 0.18},
        {"number": 9, "name": "Caballo 9", "irp": 0.72, "fcc": 0.68, "synergy": 0.71, "sigma": 0.14},
        {"number": 10, "name": "Caballo 10", "irp": 0.55, "fcc": 0.50, "synergy": 0.52, "sigma": 0.25},
        {"number": 12, "name": "Caballo 12", "irp": 0.78, "fcc": 0.75, "synergy": 0.70, "sigma": 0.11},
    ]
    
    box_selection = [11, 3, 5, 2]
    
    print("="*60)
    print("🏇 SIPH-ANTIGRAVITY: AGENTE 3 (MODELADO IA Y MONTE CARLO)")
    print("="*60)
    print(f"[*] Analizando Carrera 1 - Cuarteto Óptimo: {box_selection}")
    
    predictor = MonteCarloPredictor(n_simulations=10000)
    confidence = predictor.run_simulation(mock_field, box_selection)
    
    print("-" * 60)
    print(f"🎯 CONFIANZA PROYECTADA QUINELA BOX (TOP 2 entre {box_selection}):")
    print(f"🚀 {confidence:.2f}%")
    print("-" * 60)
    
    if confidence > 85.0:
        print("[!] ALERTA: Confianza > 85% alcanzada. Luz verde para inversión (PLAY).")
    else:
        print("[!] AVISO: Confianza insuficiente para Quinela Box (< 85%). NO BET.")
    print("="*60)
