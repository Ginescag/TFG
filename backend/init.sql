

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. TABLA: usuarios
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tlf VARCHAR(20),
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(20) DEFAULT 'user', -- 'admin' o 'user'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. TABLA: robots
CREATE TABLE robots (
    id VARCHAR(50) PRIMARY KEY,          
    usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
    secret_hash VARCHAR(255), -- Puede ser NULL inicialmente, se genera cuando el robot se bootea por primera vez (TOFU: Trust On First Use)
    alias VARCHAR(50),                   
    estado_conexion VARCHAR(20) DEFAULT 'offline', -- Solo actualiza al conectar/desconectar
    estado_operativo VARCHAR(30) DEFAULT 'idle',   
    ultima_actividad TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. TABLA: incidentes
CREATE TABLE incidentes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    robot_id VARCHAR(50) REFERENCES robots(id) ON DELETE CASCADE,
    --tipo_incidencia VARCHAR(50) NOT NULL,          
    --nivel_confianza DECIMAL(4,3) NOT NULL,         
    bucket_name VARCHAR(100) NOT NULL,
    file_name VARCHAR(255) NOT NULL,                        
    revisado BOOLEAN DEFAULT FALSE,                                           
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ÍNDICES de rendimiento
CREATE INDEX idx_incidentes_robot_fecha ON incidentes(robot_id, created_at DESC);
CREATE INDEX idx_incidentes_no_revisados ON incidentes(revisado) WHERE revisado = FALSE;