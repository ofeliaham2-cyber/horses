import asyncio
import aiohttp
import argparse
import os
import logging
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from supabase import create_client, Client

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger("CoreIngester")

class HipodromoAPI(ABC):
    """Clase base abstracta para los Ingesters de Hipódromos."""
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
    
    @abstractmethod
    async def fetch_data(self, session: aiohttp.ClientSession, fecha: str) -> Optional[Any]:
        """Realiza la petición HTTP a la API y devuelve el JSON."""
        pass

    @abstractmethod
    def transform_data(self, raw_data: Any, fecha: str) -> List[Dict[str, Any]]:
        """Mapea el JSON crudo a nuestra estructura relacional."""
        pass

    async def extract_and_load(self, session: aiohttp.ClientSession, fecha: str):
        """Orquestador para una fecha específica: Extrae, Transforma y Carga."""
        raw_data = await self.fetch_data(session, fecha)
        if not raw_data:
            return

        mapped_races = self.transform_data(raw_data, fecha)
        if not mapped_races:
            logger.info(f"Sin carreras estructuradas para {fecha} en {self.__class__.__name__}")
            return
            
        await self.load_to_supabase(mapped_races)

    async def load_to_supabase(self, mapped_races: List[Dict[str, Any]]):
        """
        Carga masiva a Supabase utilizando Upserts para mantener integridad y no duplicar.
        mapped_races debe contener la estructura:
        [{
            "hipodromo_codigo": "CHS",
            "hipodromo_nombre": "Club Hípico de Santiago",
            "carrera": { ... },
            "participaciones": [
                {"ejemplar": "...", "jinete": "...", "preparador": "...", ...}
            ]
        }]
        """
        for race_data in mapped_races:
            try:
                # 1. UPSERT Hipódromo
                hip_code = race_data["hipodromo_codigo"]
                hip_res = self.supabase.table("hipodromos").upsert(
                    {"codigo": hip_code, "nombre": race_data.get("hipodromo_nombre", hip_code)},
                    on_conflict="codigo"
                ).execute()
                hipodromo_id = hip_res.data[0]["id"]

                # 2. UPSERT Carrera
                carrera_info = race_data["carrera"]
                carrera_info["hipodromo_id"] = hipodromo_id
                car_res = self.supabase.table("carreras").upsert(
                    carrera_info,
                    on_conflict="hipodromo_id, fecha_hora, numero_carrera"
                ).execute()
                carrera_id = car_res.data[0]["id"]

                participaciones_batch = []
                # 3. Mapear Participaciones y Entidades Maestras
                for part in race_data.get("participaciones", []):
                    # Upsert Maestros (Ignoramos nulos si la API no los trae)
                    ej_nom = part.pop("ejemplar_nombre", "Desconocido").strip().upper()
                    ej_res = self.supabase.table("ejemplares").upsert({"nombre": ej_nom}, on_conflict="nombre").execute()
                    
                    jin_nom = part.pop("jinete_nombre", "Desconocido").strip().upper()
                    jin_res = self.supabase.table("jinetes").upsert({"nombre": jin_nom}, on_conflict="nombre").execute()
                    
                    prep_nom = part.pop("preparador_nombre", "Desconocido").strip().upper()
                    prep_res = self.supabase.table("preparadores").upsert({"nombre": prep_nom}, on_conflict="nombre").execute()

                    # Armar payload de participación
                    part["carrera_id"] = carrera_id
                    part["ejemplar_id"] = ej_res.data[0]["id"]
                    part["jinete_id"] = jin_res.data[0]["id"]
                    part["preparador_id"] = prep_res.data[0]["id"]
                    
                    participaciones_batch.append(part)

                # 4. UPSERT Participaciones en Batch
                if participaciones_batch:
                    self.supabase.table("participaciones").upsert(
                        participaciones_batch,
                        on_conflict="carrera_id, ejemplar_id"
                    ).execute()
                    
                logger.debug(f"Carrera {carrera_info['numero_carrera']} cargada exitosamente.")

            except Exception as e:
                logger.error(f"Error insertando carrera {race_data.get('carrera', {}).get('numero_carrera')}: {e}")

class ClubHipicoIngester(HipodromoAPI):
    """Ingester específico para la API del Club Hípico de Santiago (CHS)."""
    
    async def fetch_data(self, session: aiohttp.ClientSession, fecha: str) -> Optional[Any]:
        url = f"https://apiweb.clubhipico.cl/v2/programa/home/{fecha}"
        max_retries = 3
        base_delay = 5
        
        for attempt in range(max_retries):
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status >= 500:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"CHS API retornó {response.status} para la fecha {fecha}. Reintento {attempt + 1}/{max_retries} en {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.warning(f"CHS API retornó {response.status} para la fecha {fecha}")
                        return None
            except asyncio.TimeoutError:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Timeout conectando a CHS para fecha {fecha}. Reintento {attempt + 1}/{max_retries} en {delay}s...")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Excepción obteniendo CHS {fecha}: {e}")
                return None
                
        logger.warning(f"Se agotaron los reintentos (máximo {max_retries}) para CHS en la fecha {fecha}.")
        return None

    def transform_data(self, raw_data: Any, fecha: str) -> List[Dict[str, Any]]:
        mapped_races = []
        # Asumimos que la API devuelve un diccionario con una lista de carreras bajo una llave, 
        # o directamente la lista de carreras. Usaremos fallback seguro .get().
        carreras_api = raw_data.get("carreras", []) if isinstance(raw_data, dict) else raw_data
        
        if not isinstance(carreras_api, list):
            logger.warning(f"Estructura no esperada en CHS para {fecha}")
            return []

        for c_api in carreras_api:
            try:
                carrera_obj = {
                    "hipodromo_codigo": "CHS",
                    "hipodromo_nombre": "Club Hípico de Santiago",
                    "carrera": {
                        "numero_carrera": int(c_api.get("carrera", c_api.get("numero", 0))),
                        "fecha_hora": f"{fecha} {c_api.get('hora', '12:00:00')}",
                        "distancia": int(c_api.get("distancia", 0)),
                        "superficie": c_api.get("pista", "Desconocido"),
                        "premio_total": float(c_api.get("premio", 0) or 0)
                    },
                    "participaciones": []
                }
                
                caballos_api = c_api.get("caballos", c_api.get("ejemplares", []))
                for ej in caballos_api:
                    participacion = {
                        "ejemplar_nombre": ej.get("nombre", ej.get("ejemplar", "")),
                        "jinete_nombre": ej.get("jinete", ""),
                        "preparador_nombre": ej.get("preparador", ""),
                        "numero_mandil": int(ej.get("nro", ej.get("mandil", 0))),
                        "peso_jinete": float(ej.get("peso_jinete", ej.get("peso", 0) or 0)),
                        "cajon_partida": int(ej.get("partidor", ej.get("cajon", 0) or 0))
                    }
                    carrera_obj["participaciones"].append(participacion)
                
                mapped_races.append(carrera_obj)
            except Exception as e:
                logger.error(f"Error parseando carrera CHS en {fecha}: {e}")
                continue
                
        return mapped_races

class ElTurfIngester(HipodromoAPI):
    """Ingester para Hipódromo Chile (HCH), Club Hípico Concepción (CHC) vía ElTurf."""
    
    async def extract_and_load(self, session: aiohttp.ClientSession, fecha: str):
        raw_data = await self.fetch_data(session, fecha)
        if not raw_data:
            logger.error(f"🚨 ElTurf falló para {fecha} (SPOF detectado). Iniciando FALLBACK CASCADE.")
            from .teletrak_scraper import TeletrakScraper
            fallback_scraper = TeletrakScraper(self.supabase)
            await fallback_scraper.extract_and_load(session, fecha)
            return

        mapped_races = self.transform_data(raw_data, fecha)
        if not mapped_races:
            logger.info(f"Sin carreras estructuradas para {fecha} en {self.__class__.__name__}")
            return
            
        await self.load_to_supabase(mapped_races)
    
    async def fetch_data(self, session: aiohttp.ClientSession, fecha: str) -> Optional[Any]:
        fecha_formateada = fecha.replace("-", "") # A veces elTurf pide formato YYYYMMDD
        url = f"https://node.elturf.com/api/general/carreras/general/programas/fecha/{fecha}"
        max_retries = 3
        base_delay = 5
        
        for attempt in range(max_retries):
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status >= 500:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"ElTurf API retornó {response.status} para la fecha {fecha}. Reintento {attempt + 1}/{max_retries} en {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.warning(f"ElTurf API retornó {response.status} para la fecha {fecha}")
                        return None
            except asyncio.TimeoutError:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Timeout conectando a ElTurf para fecha {fecha}. Reintento {attempt + 1}/{max_retries} en {delay}s...")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Excepción obteniendo ElTurf {fecha}: {e}")
                return None
                
        logger.warning(f"Se agotaron los reintentos (máximo {max_retries}) para ElTurf en la fecha {fecha}.")
        return None

    def transform_data(self, raw_data: Any, fecha: str) -> List[Dict[str, Any]]:
        mapped_races = []
        carreras_api = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data
        
        if not isinstance(carreras_api, list):
            return []

        for c_api in carreras_api:
            try:
                # ElTurf mezcla hipódromos, filtramos solo HCH y CHC si es necesario.
                hip_code = str(c_api.get("hipodromo", "UNKNOWN")).upper()
                
                carrera_obj = {
                    "hipodromo_codigo": hip_code,
                    "hipodromo_nombre": hip_code,
                    "carrera": {
                        "numero_carrera": int(c_api.get("num_carrera", 0)),
                        "fecha_hora": f"{fecha} {c_api.get('hora', '12:00:00')}",
                        "distancia": int(c_api.get("distancia", 0)),
                        "superficie": c_api.get("superficie", "Desconocida"),
                        "indice_inferior": int(c_api.get("handicap_min", 0) or 0),
                        "indice_superior": int(c_api.get("handicap_max", 0) or 0)
                    },
                    "participaciones": []
                }
                
                for ej in c_api.get("inscritos", []):
                    participacion = {
                        "ejemplar_nombre": ej.get("nombre_caballo", ""),
                        "jinete_nombre": ej.get("nombre_jinete", ""),
                        "preparador_nombre": ej.get("nombre_preparador", ""),
                        "numero_mandil": int(ej.get("numero", 0)),
                        "peso_jinete": float(ej.get("peso", 0) or 0),
                        "cajon_partida": int(ej.get("partidor", 0) or 0)
                    }
                    carrera_obj["participaciones"].append(participacion)
                
                mapped_races.append(carrera_obj)
            except Exception as e:
                logger.error(f"Error parseando carrera ElTurf en {fecha}: {e}")
                continue
                
        return mapped_races


async def main_async(start_date: str, end_date: str):
    load_dotenv()
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        logger.error("Credenciales de Supabase faltantes. Revisa .env.")
        return

    supabase_client: Client = create_client(url, key)
    
    # === EMERGENCY FALLBACK: Force track creation ===
    try:
        logger.info("Iniciando carga de emergencia: Verificando existencia de hipódromos base...")
        base_tracks = [
            {"codigo": "CHS", "nombre": "Club Hípico de Santiago", "ciudad": "Santiago"},
            {"codigo": "HCH", "nombre": "Hipódromo Chile", "ciudad": "Santiago"},
            {"codigo": "VSC", "nombre": "Valparaíso Sporting", "ciudad": "Viña del Mar"},
            {"codigo": "CHC", "nombre": "Club Hípico de Concepción", "ciudad": "Concepción"}
        ]
        for t in base_tracks:
            supabase_client.table("hipodromos").upsert(t, on_conflict="codigo").execute()
        logger.info("✅ Hipódromos base (CHS, HCH, VSC, CHC) inicializados correctamente.")
    except Exception as e:
        logger.error(f"❌ Error forzando creación de hipódromos: {e}")
    # ================================================

    # Instanciamos los ingesters
    ingesters: List[HipodromoAPI] = [
        ClubHipicoIngester(supabase_client),
        ElTurfIngester(supabase_client)
    ]

    d1 = datetime.strptime(start_date, "%Y-%m-%d")
    d2 = datetime.strptime(end_date, "%Y-%m-%d")
    delta = d2 - d1

    logger.info(f"Iniciando ingesta masiva desde {start_date} hasta {end_date} ({delta.days + 1} días)")

    async with aiohttp.ClientSession() as session:
        for i in range(delta.days + 1):
            current_date = (d1 + timedelta(days=i)).strftime("%Y-%m-%d")
            logger.info(f"=== Procesando Fecha: {current_date} ===")
            
            # Lanzamos todos los ingesters en paralelo para la fecha actual
            tasks = [ingester.extract_and_load(session, current_date) for ingester in ingesters]
            await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Ingesta masiva finalizada exitosamente.")

def main():
    parser = argparse.ArgumentParser(description="Core API Ingester para APIs Hípicas Chilenas")
    parser.add_argument("--start", type=str, required=True, help="Fecha de inicio (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="Fecha final (YYYY-MM-DD)")
    args = parser.parse_args()

    asyncio.run(main_async(args.start, args.end))

if __name__ == "__main__":
    main()
