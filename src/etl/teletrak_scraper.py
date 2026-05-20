import aiohttp
import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Optional, Any, List, Dict

from .core_api_ingester import HipodromoAPI

logger = logging.getLogger("TeletrakScraper")

class TeletrakScraper(HipodromoAPI):
    """Scraper Enrutador: Usa APIs puras (ElTurf/ClubHipico) o Scraping según el hipódromo."""
    
    async def fetch_data(self, session: aiohttp.ClientSession, fecha: str, hipodromo: str = "CHS") -> Optional[Any]:
        hipodromo = hipodromo.upper()
        logger.info(f"🚨 INGESTOR ACTIVADO: Extrayendo {hipodromo} para la fecha {fecha}")
        
        # --- ESTRATEGIA API ELTURF (CHC y HCH) ---
        if hipodromo in ["CHC", "HCH"]:
            domain = "clubhipicoconcepcion.cl" if hipodromo == "CHC" else "hipodromo.cl"
            url_jornada = f"https://{domain}/api/general/carreras/general/programas/fecha/{fecha}"
            
            logger.info(f"[{hipodromo}] Consultando API Jornada: {url_jornada}")
            try:
                async with session.get(url_jornada) as response:
                    if response.status == 200:
                        data_jornada = await response.json()
                        if data_jornada and "data" in data_jornada:
                            carreras_raw = []
                            for carrera in data_jornada.get("data", []):
                                race_id = carrera.get("ID_CARRERA")
                                if not race_id:
                                    continue
                                    
                                url_detalle = f"https://{domain}/api/general/programa/general/{race_id}"
                                logger.info(f"[{hipodromo}] Descargando detalle Carrera ID: {race_id}")
                                async with session.get(url_detalle) as res_detalle:
                                    if res_detalle.status == 200:
                                        detalle_json = await res_detalle.json()
                                        carreras_raw.append(detalle_json)
                                        
                            if carreras_raw:
                                return {"tipo": "api_elturf", "datos": carreras_raw}
                    
                    logger.warning(f"La API de ElTurf fue bloqueada (Status: {response.status}). Saltando a Playwright...")
            except Exception as e:
                logger.warning(f"Error al conectar con API {hipodromo}: {e}. Saltando a Playwright...")
                
        # --- ESTRATEGIA TELETRAK (CHC/HCH fallback) ---
        if hipodromo in ["CHC", "HCH"]:
            logger.info(f"Iniciando tanque Playwright para {hipodromo} en apuestas.teletrak.cl...")
            try:
                teletrak_data = await asyncio.to_thread(self._fetch_teletrak_with_playwright, hipodromo, fecha)
                if teletrak_data:
                    return {
                        "tipo": "teletrak",
                        "hipodromo": hipodromo,
                        "hipodromo_nombre": teletrak_data.get("hipodromo_nombre", hipodromo),
                        "datos": teletrak_data.get("datos", [])
                    }
                return None
            except Exception as e:
                logger.error(f"Error extrayendo Teletrak para {hipodromo}: {e}")
                return None

        logger.warning(f"Lógica para {hipodromo} en construcción. Solo CHC/HCH activos en este bloque.")
        return None

    def _fetch_teletrak_with_playwright(self, hipodromo: str, fecha: str) -> Optional[Dict[str, Any]]:
        max_attempts = 3
        base_delay = 3
        last_error: Optional[BaseException] = None

        for attempt in range(1, max_attempts + 1):
            try:
                return self._fetch_teletrak_with_playwright_single_try(hipodromo, fecha)
            except Exception as exc:
                last_error = exc
                logger.warning(f"Teletrak intento {attempt}/{max_attempts} fallido: {exc}")
                if attempt < max_attempts:
                    delay = base_delay * attempt
                    logger.info(f"Reintentando Teletrak en {delay}s...")
                    time.sleep(delay)

        logger.error(f"Teletrak agotó reintentos ({max_attempts}) y no logró extraer datos: {last_error}")
        return None

    def _fetch_teletrak_with_playwright_single_try(self, hipodromo: str, fecha: str) -> Optional[Dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        track_hints = {
            "CHC": "Club Hípico De Concepción",
            "VSC": "Valparaíso Sporting",
            "HCH": "Hipódromo Chile",
            "RUK": "Reino Unido"
        }
        target_label = track_hints.get(hipodromo)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self._playwright_user_agent(), locale="es-PR")
            page = context.new_page()
            page.goto("https://apuestas.teletrak.cl/", wait_until="load", timeout=90000)
            page.wait_for_timeout(7000)

            track_option = self._find_teletrak_track_option(page, hipodromo, target_label)
            if not track_option:
                browser.close()
                raise RuntimeError(f"Teletrak no encontró una pista compatible para {hipodromo}.")

            if not self._activate_teletrak_track(page, track_option["label"]):
                browser.close()
                raise RuntimeError(f"No se pudo seleccionar la pista Teletrak {track_option['label']}.")

            races = self._extract_teletrak_races(page, fecha)
            browser.close()
            if not races:
                raise RuntimeError(f"Teletrak devolvió cero carreras para {hipodromo}.")

            return {
                "hipodromo_nombre": self._normalize_track_label(track_option["label"]),
                "datos": races
            }

    def _playwright_user_agent(self) -> str:
        return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    def _find_teletrak_track_option(self, page, hipodromo: str, hint: Optional[str]) -> Optional[Dict[str, str]]:
        options = page.evaluate('''() => {
            return Array.from(document.querySelectorAll('.event-detail-dropdown-options [data-option-label]')).map(el => ({
                label: el.getAttribute('data-option-label'),
                value: el.getAttribute('value')
            }));
        }''')
        if not options:
            return None

        def normalize(text: Optional[str]) -> str:
            return (text or "").strip().lower()

        hipodromo_key = hipodromo.strip().lower()
        if hint:
            hint_text = normalize(hint)
            for option in options:
                if normalize(option["label"]) == hint_text:
                    return option

        for option in options:
            label_text = normalize(option["label"])
            if hipodromo_key in label_text:
                return option

        if hint:
            for option in options:
                if hint.lower() in normalize(option["label"]):
                    return option

        return None

    def _activate_teletrak_track(self, page, label: str) -> bool:
        try:
            dropdown = page.query_selector('.event-detail-dropdown .dropdown-selected')
            if not dropdown:
                return False
            dropdown.click()
            page.wait_for_timeout(500)

            option = page.query_selector(f'[data-option-label="{label}"]')
            if not option:
                return False
            option.click()
            
            # CORRECCIÓN: F-String directa sin pasar argumentos extra
            page.wait_for_function(
                f'''() => {{
                    const el = document.querySelector(".race-box .dropdown-selected-template-value");
                    return !!el && el.innerText.trim() === "{label}";
                }}''',
                timeout=10000
            )
            page.wait_for_timeout(1000)
            return True
        except Exception as e:
            logger.warning(f"Error activando pista Teletrak: {e}")
            return False

    def _extract_teletrak_races(self, page, fecha: str) -> List[Dict[str, Any]]:
        race_buttons = page.query_selector_all('.button.races-switch-tab')
        if not race_buttons:
            logger.warning("Teletrak no tiene botones de carrera activos.")
            return []

        races: List[Dict[str, Any]] = []
        for idx in range(len(race_buttons)):
            button = page.query_selector_all('.button.races-switch-tab')[idx]
            if not button:
                continue
            label = button.inner_text().strip()
            if not label.isdigit():
                continue

            button.click()
            
            # CORRECCIÓN: F-String directa sin pasar argumentos extra
            page.wait_for_function(
                f'''() => {{
                    const el = document.querySelector(".button.races-switch-tab.active");
                    return !!el && el.innerText.trim() === "{label}";
                }}''',
                timeout=10000
            )
            page.wait_for_timeout(800)

            race_name = page.evaluate('''() => {
                const el = document.querySelector('.race-detail-details-row-item.race-detail-expander');
                return el ? el.innerText.trim() : null;
            }''')
            if not race_name:
                continue

            race_details = page.evaluate('''() => {
                const details = {};
                const entries = Array.from(document.querySelectorAll('.race-detail .race-specifics-entry'));
                entries.forEach(entry => {
                    const labelEl = entry.querySelector('.race-specifics-entry__bold');
                    const label = labelEl ? labelEl.innerText.replace(/:\s*$/, '').trim() : null;
                    const valueEls = Array.from(entry.querySelectorAll('h5')).slice(1);
                    const value = valueEls.map(el => el.innerText.trim()).filter(Boolean).join(' ');
                    if (label) {
                        details[label] = value;
                    }
                });
                return details;
            }''') or {}

            post_time = page.evaluate('''() => {
                const el = document.querySelector('.race-box .mtp-block-value');
                return el ? el.innerText.trim() : null;
            }''')
            
            runners = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('.data-grid.wager-data-grid tr.master-detail__master')).map(row => {
                    const rowText = (sel, prefix) => {
                        const el = row.querySelector(sel);
                        if (!el) return null;
                        let text = el.innerText.trim().replace(/\s+/g, ' ');
                        if (prefix) {
                            text = text.replace(prefix, '').trim();
                        }
                        return text;
                    };
                    return {
                        program: rowText('.program-number .colorful-index'),
                        post: rowText('.post-position-cell .post-position'),
                        horse: rowText('.runner-cell-horse-name'),
                        trainer: rowText('.runner-cell-trainer', 'E:'),
                        jockey: rowText('.runner-cell-rider', 'J:'),
                        weight: rowText('.weight-cell'),
                        color: rowText('.color-cell'),
                        sex: rowText('.sex-cell'),
                        age: rowText('.age-cell'),
                        probable: rowText('.probable-pays-cell')
                    };
                });
            }''') or []

            races.append({
                "numero_carrera": self._parse_int(label),
                "nombre": race_name,
                "post_time": post_time,
                "distancia": race_details.get("Distancia"),
                "superficie": race_details.get("Superficie"),
                "premio_total": self._parse_price(race_details.get("Premio")),
                "descripcion": None,
                "participaciones": runners,
                "fecha": fecha
            })

        return races

    def _normalize_track_label(self, label: str) -> str:
        if not label:
            return ""
        return re.sub(r"^\d+\.\s*", "", label).strip()

    def _parse_int(self, value: Any, default: int = 0) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        text = str(value).strip()
        match = re.search(r"-?\d+", text)
        if not match:
            return default
        try:
            return int(match.group())
        except ValueError:
            return default

    def _parse_float(self, value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        if isinstance(value, (float, int)):
            return float(value)
        text = str(value).strip().replace(' ', '')
        if text == "":
            return default
        if "." in text and "," in text:
            text = text.replace('.', '').replace(',', '.')
        elif "," in text:
            text = text.replace(',', '.')
        try:
            return float(text)
        except ValueError:
            return default

    def _parse_price(self, value: Any) -> float:
        if value is None:
            return 0.0
        text = str(value).strip().replace('$', '').strip()
        return self._parse_float(text, 0.0)

    def _format_fecha_hora(self, fecha: str, time_str: Optional[str]) -> str:
        if not time_str:
            return f"{fecha} 12:00:00"
        try:
            time_obj = datetime.strptime(time_str.upper(), "%I:%M %p")
            return f"{fecha} {time_obj.strftime('%H:%M:%S')}"
        except ValueError:
            return f"{fecha} {time_str}"

    def _parse_distance(self, value: Any) -> int:
        if value is None:
            return 0
        text = str(value).strip().lower()
        if not text:
            return 0
        if "furlong" in text:
            match = re.search(r"(\d+)(?:\s+(\d)/(\d))?", text)
            if match:
                base = float(match.group(1))
                if match.group(2) and match.group(3):
                    base += float(match.group(2)) / float(match.group(3))
                return int(round(base * 201.168))
        if "metro" in text or "m" in text:
            match = re.search(r"(\d+)", text)
            if match:
                return int(match.group(1))
        return self._parse_int(text, 0)

    def transform_data(self, raw_data: Any, fecha: str, hipodromo: str = "CHS") -> List[Dict[str, Any]]:
        """Transforma el JSON de la API en el formato canónico de Starless Media."""
        hipodromo = hipodromo.upper()
        if not raw_data or raw_data.get("tipo") not in {"api_elturf", "teletrak"}:
            return []

        mapped_races = []
        carreras_json = raw_data.get("datos", [])
        hipodromo_nombre = raw_data.get("hipodromo_nombre", hipodromo)

        try:
            for carrera_data in carreras_json:
                if raw_data.get("tipo") == "api_elturf":
                    data = carrera_data.get("data", {})
                    numero = data.get("NRO_CARRERA", 0)
                    distancia = data.get("DISTANCIA", 1000)
                    superficie = data.get("SUPERFICIE", "Desconocida")
                    inscritos = data.get("inscritos", [])
                    post_time = None
                    premio_total = data.get("PREMIO", 0)
                else:
                    data = carrera_data
                    numero = data.get("numero_carrera", 0)
                    distancia = data.get("distancia")
                    superficie = data.get("superficie", "Desconocida")
                    inscritos = data.get("participaciones", [])
                    post_time = data.get("post_time")
                    premio_total = data.get("premio_total", 0)

                carrera_obj = {
                    "hipodromo_codigo": hipodromo,
                    "hipodromo_nombre": hipodromo_nombre,
                    "carrera": {
                        "numero_carrera": int(numero),
                        "fecha_hora": self._format_fecha_hora(fecha, post_time),
                        "distancia": self._parse_distance(distancia),
                        "superficie": superficie,
                        "premio_total": self._parse_price(premio_total)
                    },
                    "participaciones": []
                }

                for runner in inscritos:
                    if raw_data.get("tipo") == "api_elturf":
                        nombre = runner.get("CABALLO", "").strip()
                        jinete = runner.get("JINETE", "").strip()
                        preparador = runner.get("PREPARADOR", "").strip()
                        mandil = runner.get("NRO_MANDIL", 0)
                        peso = 0.0
                        cajon = mandil
                    else:
                        nombre = runner.get("horse", "").strip()
                        jinete = runner.get("jockey", "").strip()
                        preparador = runner.get("trainer", "").strip()
                        mandil = runner.get("program")
                        cajon = runner.get("post")
                        peso = runner.get("weight")

                    if not nombre:
                        continue

                    participacion = {
                        "ejemplar_nombre": nombre,
                        "jinete_nombre": jinete,
                        "preparador_nombre": preparador,
                        "numero_mandil": self._parse_int(mandil),
                        "peso_jinete": self._parse_float(peso),
                        "cajon_partida": self._parse_int(cajon)
                    }
                    carrera_obj["participaciones"].append(participacion)

                if carrera_obj["participaciones"]:
                    mapped_races.append(carrera_obj)

            logger.info(f"Ingestor ({hipodromo}): {len(mapped_races)} carreras procesadas vía {raw_data.get('tipo')}.")
        except Exception as e:
            logger.error(f"Error transformando datos JSON: {e}")

        return mapped_races