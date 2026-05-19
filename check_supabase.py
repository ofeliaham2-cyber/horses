import os, json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_KEY'))

# fetch hipodromo id
h = supabase.table('hipodromos').select('id').eq('codigo', 'CHS').execute()
h_id = h.data[0]['id']

# fetch carrera
c = supabase.table('carreras').select('id, numero_carrera').eq('hipodromo_id', h_id).eq('numero_carrera', 5).gte('fecha_hora', '2026-05-18T00:00:00-04:00').execute()
c_id = c.data[0]['id']

# fetch participaciones
p = supabase.table('participaciones').select('numero_mandil, irp, fcc, sinergia, sigma, score').eq('carrera_id', c_id).execute()

for r in p.data:
    print(f"Mandil {r['numero_mandil']} -> IRP: {r['irp']} | Score: {r['score']}")
