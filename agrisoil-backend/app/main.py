"""
AgriSoil Backend - Production Ready API
FastAPI com segurança, observability, performance e resiliência
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
import os
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
import logging
import time
import asyncio
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from prometheus_fastapi_instrumentator import Instrumentator

# Import de rotas
from app.routes.clima_routes import router as clima_router
from app.routes.dashboard_routes import router as dashboard_router
from app.routes.ia_routes import router as ia_router
from app.routes.health_routes import router as health_router
from app.routes.health import router as health_check_router
from app.routes.auth_routes import router as auth_router
from app.routes.sensor_routes import router as sensor_router
from app.routes.agri_routes import router as agri_router
from app.routes.alerta_routes import router as alerta_router
from app.routes.fcm_routes import router as fcm_router
from app.routes.webhook_routes import router as webhook_router
from app.routes.monitoring_routes import router as monitoring_router
# Novas rotas (3-camadas arquitetura)
from app.routes.zonas_manejo_routes import router as zonas_manejo_router
from app.routes.biblioteca_routes import router as biblioteca_router
from app.routes.plantio_routes import router as plantio_router
from app.routes.alertas_routes import router as alertas_router
from app.routes.clientes_routes import router as clientes_router
# Rotas de Alertas Estratégicos (10 camadas)
from app.routes.alertas_estrategicos_routes import router as alertas_estrategicos_router
# Rotas de Infraestrutura (contextualização de alertas)
from app.routes.infraestrutura_routes import router as infraestrutura_router
# Rotas de Seed Data (popular banco)
from app.routes.seed_routes import router as seed_router

# Import de configuração
from app.config import settings
from app.logging_config import setup_logging
from app.db import init_db, close_db
from app.exceptions import AgriSoilException
from app.middleware_exceptions import (
    global_exception_handler,
    agrisoil_exception_handler,
    validation_error_handler,
)

logger = setup_logging()

# ===== SENTRY (Erro Tracking) =====
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=settings.environment,
    )
    logger.info("Sentry inicializado")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerenciar lifecycle da aplicação:
    - Startup: Inicializar BD, Cache, Workers
    - Shutdown: Fechar conexões
    """
    # Startup
    logger.info("Inicializando AgriSoil Backend...")
    logger.info(f"🌍 Ambiente: {settings.environment}")
    logger.info(f"🔒 HTTPS forçado: {settings.force_https}")
    logger.info("🚀 VERSÃO COM SEED AUTOMÁTICO - BUILD 2026-02-02-v3")
    
    # Criar tabelas no banco (com retry para Railway)
    try:
        logger.info("📋 Iniciando importação de modelos...")
        from app.models.database import SensorDB, LeituraDB, AlertaDB, UsuarioDB
        from app.db import Base
        logger.info(f"Modelos importados. Tabelas no metadata: {list(Base.metadata.tables.keys())}")
        
        for attempt in range(1, 6):
            try:
                logger.info(f"Tentativa {attempt}/5 de criar tabelas...")
                await init_db()
                logger.info("TABELAS CRIADAS - INICIANDO SEED ")
                
                # Popular dados iniciais logo após criar tabelas
                logger.info("🌱 Verificando necessidade de popular dados iniciais...")
                from app.seed_startup import run_startup_seeds
                from app.db import SessionLocal
                
                db = SessionLocal()
                try:
                    await run_startup_seeds(db)
                    logger.info("✅ Verificação de seeds concluída")
                except Exception as seed_error:
                    logger.error(f"❌ Erro ao executar seeds: {seed_error}", exc_info=True)
                finally:
                    db.close()
                
                break
            except Exception as e:
                logger.warning(f"Tentativa {attempt}/5 falhou: {type(e).__name__}: {e}")
                if attempt < 5:
                    await asyncio.sleep(3)
                else:
                    logger.warning("Banco ainda indisponível após 5 tentativas. App seguirá sem bloquear.")
    except ImportError as e:
        logger.error(f"Erro ao importar modelos: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Falha ao inicializar BD no startup: {type(e).__name__}: {e}", exc_info=True)
    
    # Inicializar Redis Cache (não-bloqueante)
    try:
        from app.cache import cache
        if cache.client:
            cache.client.ping()
            logger.info("Redis cache conectado")
        else:
            logger.warning("Redis não configurado (opcional)")
    except Exception as e:
        logger.warning(f"Redis não disponível (opcional): {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Encerrando AgriSoil Backend...")
    try:
        await close_db()
    except Exception as e:
        logger.warning(f"Erro ao fechar pool do BD: {e}")


# Criar aplicação com lifespan
app = FastAPI(
    title="AgriSoil Backend",
    description="API integrada de sensores agrícolas com clima, IA e IoT - Production Ready",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    # Configuração de segurança no Swagger
    swagger_ui_parameters={
        "persistAuthorization": True,  # Mantém token após refresh
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True
    }
)

# Configurar esquema de segurança Bearer JWT no OpenAPI
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="AgriSoil Backend",
        version="2.1.0",
        description="""
        ## 🔐 Autenticação e Autorização
        
        Esta API usa **JWT Bearer tokens** para autenticação.
        
        ### Como usar:
        1. **Faça login** em `/api/auth/login` com suas credenciais
        2. **Copie o token** retornado no campo `access_token`
        3. **Clique no botão "Authorize" 🔒** no topo da página
        4. **Cole o token** (não precisa adicionar "Bearer ", é automático)
        5. **Clique em "Authorize"** e feche o modal
        
        ### Níveis de permissão (roles):
        - **🔴 ADMIN**: Acesso total, pode editar bibliotecas e configurações globais
        - **🟠 GESTOR**: Gerencia múltiplas fazendas/clientes
        - **🟢 PRODUTOR**: Gerencia sua propriedade
        - **🔵 TÉCNICO**: Consultas e relatórios
        - **⚪ VIEWER**: Apenas visualização
        
        Endpoints protegidos mostram um cadeado 🔒 e especificam a role necessária.
        """,
        routes=app.routes,
    )
    
    # Adicionar esquema de segurança Bearer
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Insira o token JWT obtido no login (sem 'Bearer ')"
        }
    }
    
    # Aplicar segurança globalmente (cada rota pode sobrescrever)
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ===== MIDDLEWARE =====

# HTTPS Redirect (produção)
if settings.force_https and settings.environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    logger.info("HTTPS redirect ativado")

# CORS - Permitir requisições cross-origin
# Em desenvolvimento liberamos tudo para facilitar testes (Flutter web muda a porta a cada run)
cors_origins = ["*"] if settings.environment == "development" else settings.cors_origins
cors_credentials = False if settings.environment == "development" else settings.cors_credentials
cors_methods = ["*"] if settings.environment == "development" else settings.cors_methods
cors_headers = ["*"] if settings.environment == "development" else settings.cors_headers

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_credentials,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
)

# Trusted Host - Apenas aceitar requisições de hosts confiáveis
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.agrisoil.com", "*"]  # * para dev
)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ===== PROMETHEUS METRICS =====
if settings.prometheus_enabled:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus metrics: /metrics")


# ===== REQUEST/RESPONSE LOGGING =====

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log estruturado de requisições HTTP"""
    start_time = time.time()
    
    # Executar requisição
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f" Erro na requisição: {e}", exc_info=True)
        raise
    
    # Calcular tempo de processamento
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log estruturado
    log_data = {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "process_time": f"{process_time:.3f}s",
        "client_ip": request.client.host if request.client else "unknown"
    }
    
    if response.status_code >= 400:
        logger.warning(f" {log_data}")
    else:
        logger.info(f" {log_data}")
    
    return response


# ===== ROTAS =====

# Health checks (sem rate limit) - registrar AMBOS os routers
app.include_router(health_router)
app.include_router(health_check_router)

# Monitoring (webhooks do Alertmanager)
app.include_router(monitoring_router)

# Auth (sem rate limit para login)
app.include_router(auth_router)

# Rotas com rate limit
app.include_router(sensor_router)
app.include_router(agri_router)
app.include_router(alerta_router)
app.include_router(fcm_router)
app.include_router(webhook_router)
app.include_router(clima_router)
app.include_router(dashboard_router)
app.include_router(ia_router)

# Novas rotas (3-camadas arquitetura)
app.include_router(zonas_manejo_router)
app.include_router(biblioteca_router)
app.include_router(plantio_router)
app.include_router(alertas_router)
app.include_router(clientes_router)
# Alertas Estratégicos (10 camadas)
app.include_router(alertas_estrategicos_router)
# Infraestrutura (contextualização)
app.include_router(infraestrutura_router)
# Seed Data (popular banco com dados iniciais)
app.include_router(seed_router)


# ===== STATIC FILES (Dashboard) =====
# Tentar vários caminhos possíveis
possible_paths = [
    os.path.join(os.path.dirname(__file__), "..", "public"),  # app/../public
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public"),  # Absolute path
    "/app/public",  # Docker path
    os.path.join(os.getcwd(), "public"),  # Current working directory
]

public_path = None
for path in possible_paths:
    if os.path.exists(path):
        public_path = path
        logger.info(f"✓ Pasta public encontrada em: {path}")
        break

if public_path:
    try:
        app.mount("/static", StaticFiles(directory=public_path, check_dir=True), name="static")
        logger.info(f"✓ Arquivos estáticos montados: /static em {public_path}")
    except Exception as e:
        logger.error(f"✗ Erro ao montar arquivos estáticos: {e}")
else:
    logger.warning(f"✗ Pasta public não encontrada em nenhum dos caminhos: {possible_paths}")


# ===== ROOT =====

@app.get("/")
async def root():
    """Root endpoint - redireciona para dashboard"""
    return {
        "application": "AgriSoil Backend",
        "version": "2.1.0",
        "status": "running",
        "environment": settings.environment,
        "dashboard": "/dashboard",
        "docs": "/docs",
        "health": "/api/health",
        "metrics": "/metrics" if settings.prometheus_enabled else None
    }


# ===== DASHBOARD ENDPOINT =====

@app.get("/dashboard", response_class=JSONResponse)
async def get_dashboard_html():
    """Servir HTML do dashboard diretamente"""
    from fastapi.responses import HTMLResponse
    
    # Procurar o arquivo dashboard.html
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "public", "dashboard.html"),
        "/app/public/dashboard.html",
        os.path.join(os.getcwd(), "public", "dashboard.html"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                return HTMLResponse(content=html_content)
            except Exception as e:
                logger.error(f"Erro ao ler dashboard.html: {e}")
    
    logger.warning(f"dashboard.html não encontrado em: {possible_paths}")
    return HTMLResponse(
        content="<h1>Dashboard não encontrado</h1><p>O arquivo public/dashboard.html não foi encontrado no servidor.</p>",
        status_code=404
    )


# ===== ERROR HANDLERS =====

# Handler para exceções da aplicação
app.add_exception_handler(AgriSoilException, agrisoil_exception_handler)

# Handler para erros de validação Pydantic
from fastapi.exceptions import RequestValidationError
app.add_exception_handler(RequestValidationError, validation_error_handler)

# Handler global para exceções não capturadas
app.add_exception_handler(Exception, global_exception_handler)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )
