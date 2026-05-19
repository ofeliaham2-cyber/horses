import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# 1. Obtener hipodromo_id para CHS
h_resp = supabase.table("hipodromos").select("id").eq("codigo", "CHS").execute()
h_id = h_resp.data[0]['id']

# 2. Obtener carreras de hoy para CHS
c_resp = supabase.table("carreras").select("id, numero_carrera").eq("hipodromo_id", h_id).gte("fecha_hora", "2026-05-18T00:00:00-04:00").lte("fecha_hora", "2026-05-18T23:59:59-04:00").execute()

carreras = [c for c in c_resp.data if 4 <= c['numero_carrera'] <= 18]
carreras.sort(key=lambda x: x['numero_carrera'])

for c in carreras:
    c_id = c['id']
    num_c = c['numero_carrera']
    
    p_resp = supabase.table("participaciones").select("numero_mandil, score, irp, ejemplares(nombre)").eq("carrera_id", c_id).execute()
    
    participaciones = []
    for p in p_resp.data:
        participaciones.append({
            'mandil': p['numero_mandil'],
            'nombre': p['ejemplares']['nombre'] if p.get('ejemplares') else 'Desconocido',
            'score': p['score'] or 0,
            'irp': p['irp'] or 0
        })
        
    participaciones.sort(key=lambda x: x['score'], reverse=True)
    top4 = participaciones[:4]
    
    print(f"Carrera N° {num_c}:")
    print("Top 4 Favoritos (Mandil - Nombre):")
    for pos, p in enumerate(top4, 1):
        print(f"  {pos}. [{p['mandil']}] {p['nombre']} (Score: {p['score']} | IRP: {p['irp']})")
    
    mandiles = sorted([str(p['mandil']) for p in top4], key=int)
    print(f"Tu sugerencia de Quinela Box: [{', '.join(mandiles)}]\n")
