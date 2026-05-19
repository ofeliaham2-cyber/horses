import numpy as np

# Mock df_ranking to simulate the exact data structure
field_data = [
    {'number': 1, 'name': 'A', 'irp': 60.0, 'fcc': 1.0, 'synergy': 0.1, 'sigma': 0.0},
    {'number': 2, 'name': 'B', 'irp': 55.0, 'fcc': 2.0, 'synergy': 0.5, 'sigma': 0.5},
    {'number': 3, 'name': 'C', 'irp': 40.0, 'fcc': 3.0, 'synergy': 0.2, 'sigma': 1.0},
    {'number': 4, 'name': 'D', 'irp': 30.0, 'fcc': 4.0, 'synergy': 0.0, 'sigma': 2.0},
    {'number': 5, 'name': 'E', 'irp': 90.0, 'fcc': 1.0, 'synergy': 0.9, 'sigma': 5.0},  # Highest IRP but worst Sigma
]

# This simulates what st.multiselect does with df_ranking['number'].tolist()[:4]
# Notice horse 5 is not in the box!
box_selection = [1, 2, 3, 4]

# Mock predictor logic
def _mock_xgboost_score(irp, fcc, synergy):
    if float(synergy) == 0.0:
        synergy = 0.05
    w_irp, w_fcc, w_syn = 0.75, 0.15, 0.10
    return (irp * w_irp) + (fcc * w_fcc) + (synergy * w_syn)

n_simulations = 10000
box_hits = 0

horses = []
for horse in field_data:
    base_score = _mock_xgboost_score(horse['irp'], horse['fcc'], horse.get('synergy', 0.0))
    horses.append({
        'number': str(horse['number']).strip(),
        'score': base_score,
        'sigma': float(horse['sigma'])
    })

base_scores = np.array([h['score'] for h in horses])
sigmas = np.array([h['sigma'] for h in horses]) * 1.5
horse_numbers = np.array([h['number'] for h in horses])

box_numbers_str = [str(x).strip() for x in box_selection]

noise = np.random.normal(loc=0.0, scale=sigmas, size=(n_simulations, len(horses)))

print("Caballos mapeados para simular:", horses)
print("Base Scores:", base_scores)
print("Sigmas:", sigmas)
print("Set Box Usuario:", box_numbers_str)

for i in range(10): # Just print first 10 for debug
    sim_scores = base_scores + noise[i]
    top2_indices = np.argsort(sim_scores)[-2:]
    top2_numbers = horse_numbers[top2_indices]
    top2_numbers_str = [str(num).strip() for num in top2_numbers]
    print(f"Iter {i} Top 2: {top2_numbers_str}")

for i in range(n_simulations):
    sim_scores = base_scores + noise[i]
    top2_indices = np.argsort(sim_scores)[-2:]
    top2_numbers = horse_numbers[top2_indices]
    top2_numbers_str = [str(num).strip() for num in top2_numbers]
    
    if all(num in box_numbers_str for num in top2_numbers_str):
        box_hits += 1
        
confidence = (box_hits / n_simulations) * 100.0
print(f"Confidence: {confidence:.2f}%")
