import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
import pandas as pd
from datetime import datetime
from src.features.engine import HorsePredictorEngine
from src.model.predictor import MonteCarloPredictor
import numpy as np

engine = HorsePredictorEngine()
fecha_str = datetime.now().strftime("%Y-%m-%d")
f_min = f"{fecha_str}T00:00:00-04:00"
f_max = f"{fecha_str}T23:59:59-04:00"

ranking_data = engine.generate_ranking(
    hipodromo_codigo="CHC",
    fecha_hora_min=f_min,
    fecha_hora_max=f_max,
    numero_carrera=1
)

if not ranking_data:
    print("No data for CHC Carrera 1 today. Trying VSC Carrera 1...")
    ranking_data = engine.generate_ranking(
        hipodromo_codigo="VSC",
        fecha_hora_min=f_min,
        fecha_hora_max=f_max,
        numero_carrera=1
    )

if ranking_data:
    df_ranking = pd.DataFrame(ranking_data)
    df_ranking.columns = df_ranking.columns.str.lower()
    df_ranking = df_ranking.rename(columns={
        'mandil': 'number',
        'ejemplar': 'name',
        'sinergia': 'synergy',
    })
    
    predictor = MonteCarloPredictor(n_simulations=10)
    field_data = df_ranking.to_dict('records')
    box_selection = df_ranking['number'].tolist()[:4]
    print(f"Box selection: {box_selection}")

    n_simulations = 10
    box_hits = 0
    horses = []
    for horse in field_data:
        base_score = predictor._mock_xgboost_score(horse['irp'], horse['fcc'], horse.get('synergy', 0.0))
        horses.append({
            'number': str(horse['number']).strip(),
            'score': base_score,
            'sigma': float(horse['sigma'])
        })
    print("Horses:", horses)
    base_scores = np.array([h['score'] for h in horses])
    sigmas = np.array([h['sigma'] for h in horses]) * 1.5
    horse_numbers = np.array([h['number'] for h in horses])
    print("Base Scores:", base_scores)
    print("Sigmas:", sigmas)

    box_numbers_str = [str(x).strip() for x in box_selection]
    noise = np.random.normal(loc=0.0, scale=sigmas, size=(n_simulations, len(horses)))
    
    for i in range(n_simulations):
        sim_scores = base_scores + noise[i]
        top2_indices = np.argsort(sim_scores)[-2:]
        top2_numbers = horse_numbers[top2_indices]
        top2_numbers_str = [str(num).strip() for num in top2_numbers]
        print(f"Sim {i} top 2: {top2_numbers_str}")
        if all(num in box_numbers_str for num in top2_numbers_str):
            box_hits += 1
            
    confidence = (box_hits / n_simulations) * 100.0
    print(f"Confidence: {confidence}%")
else:
    print("No data found at all to test.")
