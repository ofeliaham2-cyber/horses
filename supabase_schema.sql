-- ==============================================================================
-- SIPH-ANTIGRAVITY: ESQUEMA RELACIONAL SUPABASE (POSTGRESQL)
-- Optimizaciones: Tipos de datos estrictos, Integridad Referencial y B-Trees
-- ==============================================================================

-- 1. ENTIDADES MAESTRAS
CREATE TABLE hipodromos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) UNIQUE NOT NULL, -- CHS, HCH, VSC, CHC
    nombre VARCHAR(100) NOT NULL,
    ciudad VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ejemplares (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    fecha_nacimiento DATE,
    sexo VARCHAR(10),
    padre VARCHAR(100),
    madre VARCHAR(100),
    abuelo_materno VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE jinetes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    peso_minimo DECIMAL(4,1),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE preparadores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. TRANSACCIONAL: CARRERAS
CREATE TABLE carreras (
    id SERIAL PRIMARY KEY,
    hipodromo_id INTEGER REFERENCES hipodromos(id) ON DELETE CASCADE,
    numero_carrera INTEGER NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL,
    distancia INTEGER NOT NULL, -- Expresado en metros
    superficie VARCHAR(20) NOT NULL, -- Arena, Pasto
    estado_pista VARCHAR(20), -- Normal, Pesada, Barrosa, Ligera
    condicion_clima VARCHAR(50), -- Soleado, Nublado, Lluvia
    temperatura_ambiente DECIMAL(4,1), -- Grados Celsius
    velocidad_viento DECIMAL(5,2), -- km/h
    indice_inferior INTEGER, -- Handicap (ej. 8)
    indice_superior INTEGER, -- Handicap (ej. 12)
    premio_total DECIMAL(12,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(hipodromo_id, fecha_hora, numero_carrera)
);

-- 3. TRANSACCIONAL CORE: PARTICIPACIONES (Features del ML)
CREATE TABLE participaciones (
    id BIGSERIAL PRIMARY KEY,
    carrera_id INTEGER REFERENCES carreras(id) ON DELETE CASCADE,
    ejemplar_id INTEGER REFERENCES ejemplares(id) ON DELETE RESTRICT,
    jinete_id INTEGER REFERENCES jinetes(id) ON DELETE RESTRICT,
    preparador_id INTEGER REFERENCES preparadores(id) ON DELETE RESTRICT,
    numero_mandil INTEGER NOT NULL, -- Número del programa
    cajon_partida INTEGER, -- Gatera/Partidor
    peso_jinete DECIMAL(4,1) NOT NULL, -- Kilos asignados
    peso_fisico_caballo INTEGER, -- Kilos en balanza
    es_retiro BOOLEAN DEFAULT FALSE,
    -- Resultados (Nulos antes de la carrera)
    dividendo_final DECIMAL(6,2), 
    probabilidad_implicita DECIMAL(5,4), -- 1 / dividendo_final
    posicion_llegada INTEGER,
    cuerpos_ventaja DECIMAL(5,2), -- 0.00 si es el ganador
    tiempo_final DECIMAL(6,2), -- En segundos
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(carrera_id, ejemplar_id)
);

-- 4. SERIES DE TIEMPO: MONEY FLOW
CREATE TABLE dividendos_live (
    id BIGSERIAL PRIMARY KEY,
    carrera_id INTEGER REFERENCES carreras(id) ON DELETE CASCADE,
    ejemplar_id INTEGER REFERENCES ejemplares(id) ON DELETE CASCADE,
    timestamp_captura TIMESTAMPTZ NOT NULL,
    dividendo DECIMAL(6,2) NOT NULL,
    volumen_estimado DECIMAL(12,2), -- Si el hipódromo provee montos apostados
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- ÍNDICES HIPER-OPTIMIZADOS (B-TREE) PARA MACHINE LEARNING
-- ==============================================================================

-- Búsquedas temporales de carreras (ej. extraer último mes de datos)
CREATE INDEX idx_carreras_fecha_hora ON carreras(fecha_hora DESC);
CREATE INDEX idx_carreras_hipodromo_fecha ON carreras(hipodromo_id, fecha_hora DESC);

-- Búsquedas de historial específico para RNN/LSTM
CREATE INDEX idx_participaciones_ejemplar_carrera ON participaciones(ejemplar_id, carrera_id DESC);
CREATE INDEX idx_participaciones_jinete_preparador ON participaciones(jinete_id, preparador_id);

-- Joins rápidos de carrera y llegada
CREATE INDEX idx_participaciones_carrera_llegada ON participaciones(carrera_id, posicion_llegada);

-- Time-Series Fast Lookup para el Money Flow
CREATE INDEX idx_dividendos_live_busqueda ON dividendos_live(carrera_id, ejemplar_id, timestamp_captura DESC);
