import asyncio
import argparse
import logging
import os
import aiohttp
from dotenv import load_dotenv
from supabase import create_client, Client

from src.etl.teletrak_scraper import TeletrakScraper

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BatchIngest")

async def run_batch_ingest(fecha: str, hipodromo: str):
    logger.info(f"Iniciando Ingesta Batch para Fecha: {fecha} | Hipódromo: {hipodromo}")
    
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        logger.error("Credenciales de Supabase no encontradas en .env")
        return

    supabase: Client = create_client(url, key)
    
    # Instanciamos el TeletrakScraper directamente para ingesta masiva por adelantado
    scraper = TeletrakScraper(supabase)
    
    async with aiohttp.ClientSession() as session:
        # Extraemos el HTML vía Playwright
        raw_data = await scraper.fetch_data(session, fecha, hipodromo=hipodromo)
        if not raw_data:
            logger.error(f"No se pudo obtener el HTML de {hipodromo}.")
            return
            
        # Parseamos las carreras
        mapped_races = scraper.transform_data(raw_data, fecha, hipodromo=hipodromo)
        
        if not mapped_races:
            logger.info(f"No se encontraron carreras estructuradas para la fecha {fecha}.")
            return
            
        # Para evitar mezclar hipódromos si la página retorna múltiples, 
        # o para asignar correctamente el código del hipódromo solicitado:
        for race in mapped_races:
            race["hipodromo_codigo"] = hipodromo.upper()
            race["hipodromo_nombre"] = hipodromo.upper()
            
        # Guardamos en Supabase
        await scraper.load_to_supabase(mapped_races)
        logger.info(f"✅ Ingesta Batch completada exitosamente. {len(mapped_races)} carreras insertadas para {hipodromo}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta masiva por adelantado desde Teletrak.")
    parser.add_argument("--fecha", required=True, help="Fecha a extraer (Formato: YYYY-MM-DD)")
    parser.add_argument("--hipodromo", required=True, help="Código del hipódromo (Ej: CHS, HCH, VSC, CHC)")
    
    args = parser.parse_args()
    
    # Ejecutamos el loop asíncrono
    asyncio.run(run_batch_ingest(args.fecha, args.hipodromo))
