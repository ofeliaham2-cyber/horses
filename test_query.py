import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Get race 1 for VSC on 2026-05-11
response = supabase.table("carreras") \
    .select("*, hipodromos(codigo)") \
    .eq("hipodromos.codigo", "VSC") \
    .eq("numero_carrera", 1) \
    .gte("fecha_hora", "2026-05-11T00:00:00-04:00") \
    .lte("fecha_hora", "2026-05-11T23:59:59-04:00") \
    .execute()

print("Carreras:", response.data)

if response.data:
    carrera_id = response.data[0]['id']
    participaciones = supabase.table("participaciones") \
        .select("*, ejemplares(nombre), jinetes(nombre), preparadores(nombre)") \
        .eq("carrera_id", carrera_id) \
        .execute()
    print(f"Participaciones para carrera {carrera_id}:")
    for p in participaciones.data:
        print(f"Mandil {p['numero_mandil']}: {p['ejemplares']['nombre']}")
