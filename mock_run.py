import numpy as np
import pandas as pd

participaciones = [
    {"numero_mandil":1,"ejemplar":"Fast Shadow","jinete":"J. Perez","preparador":"P. Ruz", "jinete_id": 1, "preparador_id": 1},
    {"numero_mandil":2,"ejemplar":"Golden Star","jinete":"A. Silva","preparador":"M. Gonzalez", "jinete_id": 2, "preparador_id": 2},
    {"numero_mandil":3,"ejemplar":"Silent Storm","jinete":"C. Martinez","preparador":"L. Sanchez", "jinete_id": 3, "preparador_id": 3},
    {"numero_mandil":4,"ejemplar":"Brave Heart","jinete":"D. Gomez","preparador":"E. Cruz", "jinete_id": 4, "preparador_id": 4}
]

results = []
for p in participaciones:
    mandil = p['numero_mandil']
    np.random.seed(mandil * 42)
    dummy_pos = np.random.randint(1, 10, size=5)
    dummy_cuerpos = dummy_pos * 1.5 + np.random.normal(0, 1, 5)
    dummy_tiempos = 65.0 + dummy_pos * 0.2 + np.random.normal(0, mandil*0.3, 5)
    
    irp = float(np.average((15 - dummy_pos) * 5, weights=np.exp(-np.arange(5) / 3.0)))
    fcc = float(np.mean([max(1.0, 1.0 + c*0.1) for c in dummy_cuerpos]))
    sinergia = len([x for x in dummy_pos if x <= 3]) / 5
    sigma = float(np.std(dummy_tiempos))
    score = (irp * (sinergia + 0.1)) / (fcc * (sigma + 0.1))
    
    results.append({
        'mandil': mandil,
        'ejemplar': p['ejemplar'],
        'jinete': p['jinete'],
        'preparador': p['preparador'],
        'IRP': round(irp, 2),
        'FCC': round(fcc, 2),
        'Sinergia': round(sinergia, 3),
        'Sigma (Varianza)': round(sigma, 3),
        'Score': round(score, 2)
    })

df_results = pd.DataFrame(results)
df_results = df_results.sort_values(by=['Sigma (Varianza)', 'Score'], ascending=[True, False])

print("="*60)
print("🔮 SIPH: GENERADOR DE PRONÓSTICOS QUINELA BOX (MIN SIGMA)")
print("="*60)
print("\n🏆 RANKING GENERAL (Ordenado por Min Sigma):")
print(df_results.to_string(index=False))

print("\n🎯 RECOMENDACIÓN QUINELA BOX (TOP 4):")
top_4 = df_results.head(4)
for _, row in top_4.iterrows():
    print(f"[{row['mandil']}] {row['ejemplar']} (Sigma: {row['Sigma (Varianza)']}) - Jinete: {row['jinete']}")
