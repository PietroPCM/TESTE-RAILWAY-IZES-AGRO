-- Migração: Adicionar sistema de alertas
-- Data: 2026-01-22
-- Descrição: Cria tabela de alertas com histórico, severidade e deduplicação

-- 1. Criar tipos enum para PostgreSQL
DO $$ BEGIN
    CREATE TYPE severidade_alerta AS ENUM ('critico', 'alto', 'medio', 'baixo');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE status_alerta AS ENUM ('ativo', 'reconhecido', 'resolvido', 'ignorado');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE tipo_alerta AS ENUM ('ph', 'umidade', 'temperatura', 'nitrogenio', 'fosforo', 'potassio', 'condutividade', 'sistema');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Criar tabela de alertas
CREATE TABLE IF NOT EXISTS alertas (
    id SERIAL PRIMARY KEY,
    
    -- Relacionamentos
    sensor_id VARCHAR(100) NOT NULL,
    cliente_id VARCHAR(100) NOT NULL,
    leitura_id INTEGER,
    
    -- Classificação
    tipo tipo_alerta NOT NULL,
    severidade severidade_alerta NOT NULL,
    status status_alerta NOT NULL DEFAULT 'ativo',
    
    -- Conteúdo
    titulo VARCHAR(200) NOT NULL,
    mensagem TEXT NOT NULL,
    valor_medido FLOAT,
    valor_referencia VARCHAR(100),
    recomendacao TEXT,
    
    -- Gestão
    notificacao_enviada BOOLEAN DEFAULT FALSE,
    reconhecido_em TIMESTAMP,
    resolvido_em TIMESTAMP,
    observacao TEXT,
    
    -- Deduplicação
    hash_deduplicacao VARCHAR(64),
    
    -- Metadados
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (sensor_id) REFERENCES sensores(sensor_id) ON DELETE CASCADE,
    FOREIGN KEY (leitura_id) REFERENCES leituras(id) ON DELETE SET NULL
);

-- 3. Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_alertas_sensor_id ON alertas(sensor_id);
CREATE INDEX IF NOT EXISTS idx_alertas_cliente_id ON alertas(cliente_id);
CREATE INDEX IF NOT EXISTS idx_alertas_tipo ON alertas(tipo);
CREATE INDEX IF NOT EXISTS idx_alertas_severidade ON alertas(severidade);
CREATE INDEX IF NOT EXISTS idx_alertas_status ON alertas(status);
CREATE INDEX IF NOT EXISTS idx_alertas_criado_em ON alertas(criado_em);
CREATE INDEX IF NOT EXISTS idx_alertas_hash_dedup ON alertas(hash_deduplicacao);

-- 4. Adicionar coluna de preferências de notificação na tabela usuarios
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS preferencias_notificacao JSONB DEFAULT '{
    "email_ativo": true,
    "email_severidade_minima": "alto",
    "alertas_ph": true,
    "alertas_umidade": true,
    "alertas_temperatura": true,
    "alertas_npk": true,
    "alertas_sistema": true,
    "agrupar_alertas": true,
    "intervalo_minimo_minutos": 60
}'::jsonb;

-- 5. Criar função para atualizar timestamp automaticamente
CREATE OR REPLACE FUNCTION update_alertas_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 6. Criar trigger para atualizar timestamp
DROP TRIGGER IF EXISTS trigger_update_alertas_timestamp ON alertas;
CREATE TRIGGER trigger_update_alertas_timestamp
    BEFORE UPDATE ON alertas
    FOR EACH ROW
    EXECUTE FUNCTION update_alertas_timestamp();

-- 7. Comentários na tabela
COMMENT ON TABLE alertas IS 'Histórico e gestão de alertas do sistema';
COMMENT ON COLUMN alertas.hash_deduplicacao IS 'Hash único para evitar alertas duplicados (sensor_id + tipo + severidade + dia)';
COMMENT ON COLUMN alertas.severidade IS 'Níveis: critico (ação imediata), alto (urgente), medio (atenção), baixo (informativo)';
COMMENT ON COLUMN alertas.status IS 'Status: ativo (novo), reconhecido (visualizado), resolvido (corrigido), ignorado (descartado)';

-- 8. Dados iniciais (opcional - para testes)
-- INSERT INTO alertas (sensor_id, cliente_id, tipo, severidade, titulo, mensagem, hash_deduplicacao)
-- SELECT 
--     s.sensor_id,
--     s.cliente_id,
--     'sistema',
--     'baixo',
--     'Sistema de alertas ativado',
--     'O novo sistema de alertas foi configurado com sucesso para este sensor.',
--     md5(CONCAT(s.sensor_id, 'sistema', 'baixo', CURRENT_DATE::text))
-- FROM sensores s
-- WHERE s.ativo = true
-- LIMIT 5;

-- Verificação
SELECT 'Migração concluída com sucesso!' as status;
SELECT COUNT(*) as total_alertas FROM alertas;
