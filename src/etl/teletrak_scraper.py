import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from typing import Optional, Any, List, Dict
from playwright.async_api import async_playwright
import re

from .core_api_ingester import HipodromoAPI

logger = logging.getLogger("TeletrakScraper")

class TeletrakScraper(HipodromoAPI):
    """Scraper adaptado para sitios de hipódromos individuales (Fallback Cascade)."""
    
    async def fetch_data(self, session: aiohttp.ClientSession, fecha: str, hipodromo: str = "CHS") -> Optional[Any]:
        logger.info(f"🚨 SCRAPER ACTIVADO: Extrayendo programa {hipodromo} para la fecha {fecha}")
        all_races_html = []
        
        if hipodromo != "CHS":
            logger.warning(f"Scraper para {hipodromo} no está completamente implementado. Solo soportamos CHS actualmente.")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Fetch first race to find total number of races
                url = f"https://www.clubhipico.cl/carreras/programa-y-resultados/?fecha={fecha}&carrera=1"
                await page.goto(url, wait_until='networkidle', timeout=30000)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # Find all race links to determine the maximum race number
                race_links = soup.select('a[href*="carrera="]')
                max_race = 1
                for link in race_links:
                    href = link.get("href", "")
                    match = re.search(r'carrera=(\d+)', href)
                    if match:
                        race_num = int(match.group(1))
                        if race_num > max_race:
                            max_race = race_num
                            
                logger.info(f"Se detectaron {max_race} carreras para la jornada en CHS.")
                all_races_html.append(html)
                
                # Fetch the rest of the races
                for i in range(2, max_race + 1):
                    logger.info(f"Extrayendo carrera {i}/{max_race}...")
                    url_carrera = f"https://www.clubhipico.cl/carreras/programa-y-resultados/?fecha={fecha}&carrera={i}"
                    await page.goto(url_carrera, wait_until='networkidle', timeout=30000)
                    all_races_html.append(await page.content())
                    
                await browser.close()
                return all_races_html # Retornamos una lista de HTMLs
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout navegando en Scraper para {fecha}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado en Scraper para {fecha}: {e}")
            return None

    def transform_data(self, raw_data: Any, fecha: str, hipodromo: str = "CHS") -> List[Dict[str, Any]]:
        """
        Toma una lista de strings HTML y extrae las carreras usando 
        los selectores reales de clubhipico.cl
        """
        if not raw_data:
            return []
            
        mapped_races = []
        
        if hipodromo != "CHS":
            return mapped_races
            
        try:
            # raw_data es una lista de strings HTML
            for index, html in enumerate(raw_data):
                soup = BeautifulSoup(html, "html.parser")
                numero_carrera = index + 1
                
                carrera_obj = {
                    "hipodromo_codigo": hipodromo, 
                    "hipodromo_nombre": hipodromo,
                    "carrera": {
                        "numero_carrera": int(numero_carrera),
                        "fecha_hora": f"{fecha} 12:00:00", # Hora referencial
                        "distancia": 1000, 
                        "superficie": "Arena" 
                    },
                    "participaciones": []
                }
                
                caballos_html = soup.select(".bloque-programa.mix")
                for ej in caballos_html:
                    # Mandil
                    mandil = ej.get("data-mandil", "0")
                    if not mandil.isdigit():
                        mandil_elem = ej.select_one('.full-mandil')
                        if mandil_elem:
                            mandil_text = mandil_elem.text.strip()
                            mandil = mandil_text if mandil_text.isdigit() else "0"
                            
                    # Nombre del ejemplar
                    nombre_elem = ej.select_one(".ejemplar-name a.text-darkk.black")
                    nombre = ""
                    if nombre_elem:
                        from bs4 import NavigableString
                        nombre = "".join([t for t in nombre_elem.contents if isinstance(t, NavigableString)]).strip()
                        if not nombre:
                            nombre = nombre_elem.text.split("(")[0].strip()
                    
                    # Jinete
                    jinete = ""
                    jinete_span = ej.find("span", class_="black", string=re.compile("Jinete", re.I))
                    if jinete_span and jinete_span.parent:
                        jinete_text = jinete_span.parent.text.replace("Jinete:", "").replace("Jinete", "").strip()
                        jinete = re.sub(r'\d+\s*Kg.*', '', jinete_text, flags=re.I).strip()
                        
                    # Preparador
                    preparador = ""
                    prep_span = ej.find("span", class_="black", string=re.compile("Preparador", re.I))
                    if prep_span and prep_span.parent:
                        preparador = prep_span.parent.text.replace("Preparador:", "").replace("Preparador", "").strip()
                    
                    participacion = {
                        "ejemplar_nombre": nombre,
                        "jinete_nombre": jinete,
                        "preparador_nombre": preparador,
                        "numero_mandil": int(mandil) if mandil.isdigit() else 0,
                        "peso_jinete": 0.0,
                        "cajon_partida": int(mandil) if mandil.isdigit() else 0
                    }
                    # Omitir si no hay datos reales
                    if nombre and jinete:
                        carrera_obj["participaciones"].append(participacion)
                    
                if carrera_obj["participaciones"]:
                    mapped_races.append(carrera_obj)
                
            logger.info(f"TeletrakScraper (CHS): Extraídas {len(mapped_races)} carreras exitosamente.")
            
        except AttributeError as e:
            logger.warning(f"Error parseando el HTML (¿Cambió el DOM?): {e}")
        except Exception as e:
            logger.error(f"Error procesando datos en Scraper: {e}")
            
        return mapped_races
