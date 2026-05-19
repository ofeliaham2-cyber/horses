import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

# Añadir el root del proyecto al PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.model.predictor import MonteCarloPredictor
from src.model.value_bet import detect_value_leaks
from src.features.engine import HorsePredictorEngine

# Configuración inicial de Streamlit
st.set_page_config(page_title="SIPH-Antigravity Dashboard", layout="wide", page_icon="🏇")

# Tema CSS Personalizado para el Dashboard Táctico
st.markdown("""
<style>
    .reportview-container { background: #0e1117; }
    h1, h2, h3 { color: #00ffcc; font-family: 'Courier New', Courier, monospace; }
    .stButton>button { background-color: #00ffcc; color: #000; border-radius: 5px; font-weight: bold; border: 1px solid #00ffcc; width: 100%;}
    .stButton>button:hover { background-color: #000; color: #00ffcc; border: 1px solid #00ffcc; }
    .metric-container { border-left: 3px solid #00ffcc; padding-left: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🏇 SIPH-Antigravity: Terminal de Comando Táctico")
st.markdown("Dashboard del Ensamble IA para Predicción de Quinelas Box con >85% Confianza.")

# Inicializar motor de features (Agente 2)
@st.cache_resource
def get_engine():
    return HorsePredictorEngine()

engine = get_engine()

# Pestañas principales
tab_live, tab_backtest = st.tabs(["🚀 Operación Live", "📊 Backtesting & Post-Mortem"])

with tab_live:
    col_params, col_data = st.columns([1, 3])
    
    with col_params:
        st.subheader("Parámetros de Simulación")
        fecha = st.date_input("Fecha de Carrera", value=datetime.now().date())
        hipodromo = st.selectbox("Hipódromo", ["CHS", "HCH", "VSC", "CHC"])
        carrera = st.number_input("N° Carrera", min_value=1, max_value=20, value=1)
        
    with col_data:
        st.subheader("Ranking de Caballos (Agente 2)")
        
        # Formatear fechas para la query de Supabase
        fecha_str = fecha.strftime("%Y-%m-%d")
        f_min = f"{fecha_str}T00:00:00-04:00"
        f_max = f"{fecha_str}T23:59:59-04:00"
        
        # Consultar datos pre-calculados vía Engine (Solo Lectura)
        with st.spinner(f"Consultando Supabase para {hipodromo} - Carrera {carrera}..."):
            ranking_data = None
            hipodromos = engine.query_supabase("hipodromos", {"codigo": f"eq.{hipodromo}", "select": "id"})
            
            if hipodromos:
                hipodromo_id = hipodromos[0]['id']
                carreras_db = engine.query_supabase("carreras", {
                    "hipodromo_id": f"eq.{hipodromo_id}",
                    "numero_carrera": f"eq.{int(carrera)}",
                    "fecha_hora": f"gte.{f_min}",
                    "select": "id"
                })
                
                if carreras_db:
                    carrera_id = carreras_db[0]['id']
                    participaciones = engine.query_supabase("participaciones", {
                        "carrera_id": f"eq.{carrera_id}",
                        "select": "numero_mandil, ejemplares(nombre), jinetes(nombre), preparadores(nombre), irp, fcc, sinergia, sigma, score"
                    })
                    
                    if participaciones:
                        procesadas = [p for p in participaciones if p.get('irp') is not None]
                        if procesadas:
                            ranking_data = []
                            for p in procesadas:
                                ranking_data.append({
                                    'mandil': p.get('numero_mandil'),
                                    'ejemplar': p.get('ejemplares', {}).get('nombre', 'Desconocido'),
                                    'jinete': p.get('jinetes', {}).get('nombre', 'Desconocido'),
                                    'preparador': p.get('preparadores', {}).get('nombre', 'Desconocido'),
                                    'irp': p.get('irp'),
                                    'fcc': p.get('fcc'),
                                    'sinergia': p.get('sinergia'),
                                    'sigma': p.get('sigma'),
                                    'score': p.get('score')
                                })
                            ranking_data.sort(key=lambda x: (x.get('sigma', 99), -x.get('score', 0)))
            
        if ranking_data:
            # Crear DataFrame base con copia limpia
            df_ranking = pd.DataFrame(ranking_data).copy()
            
            # Forzar nombres de columnas estrictamente a minúsculas
            df_ranking.columns = [str(c).lower().strip() for c in df_ranking.columns]
            
            # Mapeo unificado para visualización y consistencia con el Predictor
            df_ranking = df_ranking.rename(columns={
                'mandil': 'number',
                'ejemplar': 'name',
                'sinergia': 'synergy'
            })
            
            # Mostrar la tabla con el gradiente sobre las columnas en minúsculas existentes
            st.dataframe(df_ranking.style.background_gradient(subset=['irp', 'fcc', 'synergy'], cmap='viridis'), use_container_width=True)
            
            st.markdown("---")
            st.subheader("Simulación Cuántica")
            
            # Selección de Box basada en los caballos reales
            default_box = df_ranking['number'].tolist()[:4] if len(df_ranking) >= 4 else df_ranking['number'].tolist()
            box_selection = st.multiselect("Seleccionar Quinela Box (Target para Llegar 1° y 2°)", 
                                           df_ranking['number'].tolist(), 
                                           default=default_box)
            
            if st.button("⚡ Ejecutar Simulación Monte Carlo"):
                with st.spinner('Procesando 10,000 trayectorias de varianza...'):
                    import numpy as np
                    predictor = MonteCarloPredictor(n_simulations=10000)
                    
                    # Convertir DataFrame normalizado a registros dict limpios
                    field_data = df_ranking.to_dict('records')
                    
                    n_simulations = 10000
                    box_hits = 0
                    horses = []
                    
                    # 1. Preparar tensores base mapeando las llaves renombradas
                    for horse in field_data:
                        # Extraer variables con fallback seguro en minúsculas
                        val_irp = float(horse.get('irp', 50.0))
                        val_fcc = float(horse.get('fcc', 1.0))
                        val_syn = float(horse.get('synergy', 0.0))
                        val_sigma = float(horse.get('sigma', 5.0))
                        
                        base_score = predictor._mock_xgboost_score(val_irp, val_fcc, val_syn)
                        horses.append({
                            'number': str(horse['number']).strip(),
                            'score': base_score,
                            'sigma': val_sigma
                        })
                    
                    base_scores = np.array([h['score'] for h in horses])
                    sigmas = np.array([h['sigma'] for h in horses]) * 1.5  # Amplificador de varianza (Sigma)
                    horse_numbers = np.array([h['number'] for h in horses])
                    
                    # Crear conjunto optimizado de la selección del usuario
                    set_box = set(str(x).strip() for x in box_selection)
                    
                    # 2. Generar matriz de ruido normalizado
                    noise = np.random.normal(loc=0.0, scale=sigmas, size=(n_simulations, len(horses)))
                    
                    # 3. Correr iteraciones Monte Carlo combinatorias
                    for i in range(n_simulations):
                        sim_scores = base_scores + noise[i]
                        
                        # Extraer las dos mejores posiciones de esta simulación
                        top2_indices = np.argsort(sim_scores)[-2:]
                        top2_numbers = horse_numbers[top2_indices]
                        
                        set_top2 = {str(num).strip() for num in top2_numbers}
                        
                        # Si los dos primeros virtuales caen dentro de la Box, es un acierto
                        if set_top2.issubset(set_box):
                            box_hits += 1
                            
                    confidence = (box_hits / n_simulations) * 100.0
                    
                    # Mostrar Métricas Clave
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    metric_col1.metric(label="Confianza Quinela Box", value=f"{confidence:.2f}%", delta="Target: >85%", delta_color="off")
                    
                    if confidence > 85.0:
                        st.balloons()
                        st.success(f"🟢 **ALERTA DE VALOR DETECTADA!** Confianza de {confidence:.2f}%. Luz verde (PLAY) para inversión.")
                    else:
                        st.warning(f"🔴 **NO BET.** Confianza insuficiente ({confidence:.2f}% < 85.0%). Riesgo de dispersión estadística elevado.")
        else:
            st.error(f"❌ Sin datos para esta carrera ({hipodromo} - Carrera {carrera} el {fecha_str}).")
            st.info("No se han procesado features en lote para esta jornada hípica.")

with tab_backtest:
    st.subheader("Auditoría de Eficiencia Post-Mortem (Agente 4)")
    st.markdown("Comparativa entre nuestras proyecciones matemáticas y el dividendo oficial para detectar Fugas de Valor.")
    
    if 'df_ranking' in locals() and not df_ranking.empty:
        st.info("Analizando eficiencia para la carrera seleccionada...")
        st.markdown("#### 🚨 Fugas de Valor Detectadas (Edge del Modelo)")
        st.write("Consultando dividendos finales en Supabase...")
        st.warning("Funcionalidad de cruce automático con dividendos reales en desarrollo.")
        
        preds_audit = df_ranking[['name', 'irp', 'fcc', 'synergy']].copy()
        preds_audit.columns = [c.lower() for c in preds_audit.columns]
        
        predictor_audit = MonteCarloPredictor(n_simulations=1)
        preds_audit['probabilidad_modelo'] = preds_audit.apply(
            lambda row: predictor_audit._mock_xgboost_score(row['irp'], row['fcc'], row.get('synergy', 0.0)),
            axis=1
        )
        
        preds_audit = preds_audit.rename(columns={'name': 'nombre'})
        
        st.write("Estructura de Auditoría:")
        st.dataframe(preds_audit[['nombre', 'probabilidad_modelo']])
    else:
        st.write("Carga una carrera válida en la pestaña 'Live' para habilitar el análisis de eficiencia.")