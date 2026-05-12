"""
EXEMPLO: Como usar o sistema de permissões nas rotas

Este arquivo demonstra como proteger endpoints com diferentes níveis de acesso.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.security import (
    get_current_user,
    verificar_admin,
    verificar_gestor_ou_superior,
    verificar_produtor_ou_superior,
    require_role
)

router = APIRouter(prefix="/api/exemplo", tags=["Exemplo de Permissões"])


# ============================================================================
# EXEMPLO 1: Apenas usuários autenticados (qualquer role)
# ============================================================================

@router.get("/meus-dados")
async def obter_meus_dados(user_id: str = Depends(get_current_user)):
    """
    🔓 Qualquer usuário autenticado pode acessar.
    
    Não verifica role específica, apenas se tem token válido.
    """
    return {
        "user_id": user_id,
        "mensagem": "Qualquer usuário logado pode ver isso"
    }


# ============================================================================
# EXEMPLO 2: Apenas ADMIN
# ============================================================================

@router.post("/biblioteca/criar-cultura")
async def criar_cultura_na_biblioteca(
    nome_cultura: str,
    user: dict = Depends(verificar_admin)
):
    """
    🔒 SOMENTE ADMIN pode acessar.
    
    Use para:
    - Criar/editar bibliotecas de culturas
    - Configurações globais do sistema
    - Gerenciar usuários e permissões
    """
    return {
        "mensagem": f"Cultura '{nome_cultura}' criada na biblioteca",
        "criado_por": user.get("email"),
        "role": user.get("role")
    }


@router.delete("/usuarios/{user_id}")
async def deletar_usuario(
    user_id: str,
    admin: dict = Depends(verificar_admin)
):
    """
    🔒 SOMENTE ADMIN pode deletar usuários.
    """
    return {
        "mensagem": f"Usuário {user_id} deletado",
        "deletado_por": admin.get("email")
    }


# ============================================================================
# EXEMPLO 3: GESTOR ou superior (gestor + admin)
# ============================================================================

@router.post("/fazendas/criar")
async def criar_fazenda(
    nome_fazenda: str,
    user: dict = Depends(verificar_gestor_ou_superior)
):
    """
    🔐 GESTOR ou ADMIN podem acessar.
    
    Use para:
    - Criar/gerenciar fazendas
    - Atribuir usuários a fazendas
    - Relatórios gerenciais
    """
    return {
        "mensagem": f"Fazenda '{nome_fazenda}' criada",
        "criado_por": user.get("email"),
        "role": user.get("role")
    }


# ============================================================================
# EXEMPLO 4: PRODUTOR ou superior (produtor + gestor + admin)
# ============================================================================

@router.post("/zonas-manejo/criar")
async def criar_zona_manejo(
    nome_zona: str,
    user: dict = Depends(verificar_produtor_ou_superior)
):
    """
    🔓 PRODUTOR, GESTOR ou ADMIN podem criar zonas.
    
    Use para:
    - Criar/editar zonas de manejo
    - Configurar sensores
    - Definir plantios
    """
    return {
        "mensagem": f"Zona '{nome_zona}' criada",
        "criado_por": user.get("email"),
        "role": user.get("role")
    }


# ============================================================================
# EXEMPLO 5: Roles customizadas com require_role()
# ============================================================================

@router.post("/relatorios/exportar")
async def exportar_relatorio(
    formato: str,
    user: dict = Depends(require_role("admin", "gestor", "tecnico"))
):
    """
    🔧 Roles customizadas: ADMIN, GESTOR ou TÉCNICO.
    
    Use require_role() para combinar roles específicas de forma flexível.
    """
    return {
        "mensagem": f"Relatório exportado em {formato}",
        "exportado_por": user.get("email"),
        "role": user.get("role")
    }


@router.post("/sensores/calibrar")
async def calibrar_sensor(
    sensor_id: str,
    user: dict = Depends(require_role("admin", "tecnico"))
):
    """
    🔧 Apenas ADMIN ou TÉCNICO podem calibrar sensores.
    """
    return {
        "mensagem": f"Sensor {sensor_id} calibrado",
        "calibrado_por": user.get("email")
    }


# ============================================================================
# EXEMPLO 6: Verificação adicional de propriedade do recurso
# ============================================================================

@router.get("/zonas-manejo/{zona_id}")
async def obter_zona_manejo(
    zona_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    🔓 Qualquer usuário, mas verifica se pertence ao cliente correto.
    
    Pattern: Autenticação + verificação de ownership no código.
    """
    # Aqui você buscaria a zona no BD e verificaria se user_id tem acesso
    # from app.repositories import zonas_repo
    # zona = await zonas_repo.get_by_id(zona_id)
    # if zona.cliente_id != user_id:
    #     raise HTTPException(403, "Você não tem acesso a esta zona")
    
    return {
        "zona_id": zona_id,
        "user_id": user_id,
        "mensagem": "Zona encontrada e acesso verificado"
    }


# ============================================================================
# RESUMO DE USO
# ============================================================================

"""
GUIA RÁPIDO - Quando usar cada dependency:

1. get_current_user
   ✅ Qualquer usuário autenticado
   ✅ Endpoints de leitura genéricos
   ✅ Quando você precisa do user_id mas não se importa com a role

2. verificar_admin
   ✅ Criar/editar bibliotecas de culturas
   ✅ Parâmetros ideais globais
   ✅ Configurações do sistema
   ✅ Gerenciar usuários
   ❌ Não usar para operações de fazenda

3. verificar_gestor_ou_superior  
   ✅ Criar/gerenciar fazendas
   ✅ Atribuir usuários a propriedades
   ✅ Relatórios multi-fazenda
   ❌ Não usar para configurações globais

4. verificar_produtor_ou_superior
   ✅ Criar zonas de manejo
   ✅ Configurar sensores
   ✅ Definir plantios
   ✅ Alterar configurações da fazenda

5. require_role("role1", "role2", ...)
   ✅ Combinações customizadas de roles
   ✅ Quando nenhuma das dependencies acima se encaixa
   ✅ Controle granular


DOCUMENTAÇÃO NO SWAGGER:

Todas as rotas protegidas aparecerão com um cadeado 🔒 no Swagger.
O usuário precisa:
1. Fazer login em /api/auth/login
2. Copiar o token da resposta
3. Clicar em "Authorize" no topo do Swagger
4. Colar o token no formato: Bearer <token>

EXEMPLO DE TOKEN NO JWT:
{
  "sub": "user123",
  "email": "produtor@fazenda.com",
  "role": "produtor",
  "exp": 1707696000
}
"""
