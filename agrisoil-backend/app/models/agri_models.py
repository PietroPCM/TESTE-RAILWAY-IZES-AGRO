"""
Modelos Pydantic para validação de dados das entidades agrícolas
Baseado no Smart Data Models (FIWARE)
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


# ============================================================================
# AGRI FARM (Fazenda)
# ============================================================================

class AgriFarmCreate(BaseModel):
    """Modelo para criar uma fazenda"""
    farm_id: str = Field(..., description="ID único da fazenda")
    cliente_id: str = Field(..., description="ID do cliente proprietário")
    name: str = Field(..., description="Nome da fazenda")
    description: Optional[str] = None
    
    # Endereço
    address_street: Optional[str] = None
    address_locality: Optional[str] = None  # cidade
    address_region: Optional[str] = None  # estado
    address_country: str = "Brasil"
    address_postal_code: Optional[str] = None
    
    # Dados da propriedade
    area: Optional[float] = Field(None, description="Área em hectares")
    area_unit: str = "hectares"
    
    # Proprietário
    owned_by: Optional[str] = None
    contact_point: Optional[str] = None
    
    # Localização (GeoJSON)
    location_coordinates: Optional[List[float]] = Field(None, description="[longitude, latitude]")
    
    class Config:
        json_schema_extra = {
            "example": {
                "farm_id": "fazenda-sao-joao",
                "cliente_id": "cliente123",
                "name": "Fazenda São João",
                "description": "Fazenda de soja e milho",
                "address_locality": "Brasília",
                "address_region": "DF",
                "area": 500,
                "owned_by": "João Silva",
                "contact_point": "61999999999",
                "location_coordinates": [-47.9292, -15.7801]
            }
        }


class AgriFarmUpdate(BaseModel):
    """Modelo para atualizar uma fazenda"""
    name: Optional[str] = None
    description: Optional[str] = None
    address_street: Optional[str] = None
    address_locality: Optional[str] = None
    address_region: Optional[str] = None
    address_postal_code: Optional[str] = None
    area: Optional[float] = None
    owned_by: Optional[str] = None
    contact_point: Optional[str] = None
    location_coordinates: Optional[List[float]] = None
    ativo: Optional[bool] = None


class AgriFarmResponse(BaseModel):
    """Modelo de resposta de uma fazenda"""
    id: int
    farm_id: str
    cliente_id: str
    name: str
    description: Optional[str]
    address_locality: Optional[str]
    address_region: Optional[str]
    area: Optional[float]
    area_unit: str
    owned_by: Optional[str]
    contact_point: Optional[str]
    location_coordinates: Optional[List[float]]
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# AGRI PARCEL (Talhão)
# ============================================================================

class AgriParcelCreate(BaseModel):
    """Modelo para criar um talhão"""
    parcel_id: str = Field(..., description="ID único do talhão")
    cliente_id: str = Field(..., description="ID do cliente")
    farm_id: str = Field(..., description="ID da fazenda à qual pertence")
    name: str = Field(..., description="Nome do talhão")
    description: Optional[str] = None
    category: Optional[str] = Field(None, description="arable, grassland, orchard, etc")
    
    # Área e localização
    area: Optional[float] = Field(None, description="Área em hectares")
    location_coordinates: Optional[List[List[float]]] = Field(None, description="Polígono [[lon,lat], ...]")
    
    # Relacionamentos
    crop_id: Optional[str] = Field(None, description="ID da cultura plantada")
    soil_type: Optional[str] = Field(None, description="Tipo de solo")
    
    class Config:
        json_schema_extra = {
            "example": {
                "parcel_id": "talhao-A",
                "cliente_id": "cliente123",
                "farm_id": "fazenda-sao-joao",
                "name": "Talhão A",
                "description": "Área de soja",
                "category": "arable",
                "area": 50,
                "crop_id": "soja",
                "soil_type": "argiloso"
            }
        }


class AgriParcelUpdate(BaseModel):
    """Modelo para atualizar um talhão"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    area: Optional[float] = None
    location_coordinates: Optional[List[List[float]]] = None
    crop_id: Optional[str] = None
    soil_type: Optional[str] = None
    ativo: Optional[bool] = None


class AgriParcelResponse(BaseModel):
    """Modelo de resposta de um talhão"""
    id: int
    parcel_id: str
    cliente_id: str
    farm_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    area: Optional[float]
    crop_id: Optional[str]
    soil_type: Optional[str]
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# AGRI CROP (Cultura)
# ============================================================================

class AgriCropCreate(BaseModel):
    """Modelo para criar uma cultura"""
    crop_id: str = Field(..., description="ID único da cultura")
    name: str = Field(..., description="Nome da cultura")
    alternate_name: Optional[str] = None
    description: Optional[str] = None
    agrovoc_concept: Optional[str] = None
    
    # Calendário agrícola
    planting_from: Optional[str] = Field(None, description="Data de início do plantio (--MM-DD)")
    planting_to: Optional[str] = Field(None, description="Data de fim do plantio (--MM-DD)")
    harvesting_from: Optional[str] = Field(None, description="Data de início da colheita (--MM-DD)")
    harvesting_to: Optional[str] = Field(None, description="Data de fim da colheita (--MM-DD)")
    
    # Requisitos
    watering_frequency: Optional[str] = Field(None, description="daily, weekly, etc")
    
    # Faixas ideais
    ideal_temp_min: Optional[float] = None
    ideal_temp_max: Optional[float] = None
    ideal_ph_min: Optional[float] = None
    ideal_ph_max: Optional[float] = None
    ideal_moisture_min: Optional[float] = None
    ideal_moisture_max: Optional[float] = None
    
    # Produtos recomendados
    recommended_fertilizers: Optional[List[str]] = None
    recommended_pesticides: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "crop_id": "soja",
                "name": "Soja",
                "description": "Glycine max",
                "planting_from": "--10-01",
                "planting_to": "--11-30",
                "harvesting_from": "--02-01",
                "harvesting_to": "--03-31",
                "watering_frequency": "weekly",
                "ideal_temp_min": 20,
                "ideal_temp_max": 30,
                "ideal_ph_min": 6.0,
                "ideal_ph_max": 6.5,
                "ideal_moisture_min": 60,
                "ideal_moisture_max": 80
            }
        }


class AgriCropUpdate(BaseModel):
    """Modelo para atualizar uma cultura"""
    name: Optional[str] = None
    description: Optional[str] = None
    planting_from: Optional[str] = None
    planting_to: Optional[str] = None
    harvesting_from: Optional[str] = None
    harvesting_to: Optional[str] = None
    watering_frequency: Optional[str] = None
    ideal_temp_min: Optional[float] = None
    ideal_temp_max: Optional[float] = None
    ideal_ph_min: Optional[float] = None
    ideal_ph_max: Optional[float] = None
    ideal_moisture_min: Optional[float] = None
    ideal_moisture_max: Optional[float] = None


class AgriCropResponse(BaseModel):
    """Modelo de resposta de uma cultura"""
    id: int
    crop_id: str
    name: str
    description: Optional[str]
    planting_from: Optional[str]
    planting_to: Optional[str]
    harvesting_from: Optional[str]
    harvesting_to: Optional[str]
    watering_frequency: Optional[str]
    ideal_temp_min: Optional[float]
    ideal_temp_max: Optional[float]
    ideal_ph_min: Optional[float]
    ideal_ph_max: Optional[float]
    ideal_moisture_min: Optional[float]
    ideal_moisture_max: Optional[float]
    criado_em: datetime
    atualizado_em: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# AGRI PARCEL RECORD (Registro de Condições)
# ============================================================================

class AgriParcelRecordCreate(BaseModel):
    """Modelo para criar um registro de condições"""
    record_id: str = Field(..., description="ID único do registro")
    parcel_id: str = Field(..., description="ID do talhão")
    cliente_id: str = Field(..., description="ID do cliente")
    
    # Condições do solo
    soil_temperature: Optional[float] = None
    soil_moisture: Optional[float] = None
    soil_moisture_vwc: Optional[float] = None
    soil_moisture_ec: Optional[float] = None
    soil_salinity: Optional[float] = None
    
    # Condições atmosféricas
    atmospheric_pressure: Optional[float] = None
    solar_radiation: Optional[float] = None
    relative_humidity: Optional[float] = None
    air_temperature: Optional[float] = None
    
    # Observações da planta
    leaf_wetness: Optional[float] = None
    leaf_relative_humidity: Optional[float] = None
    leaf_temperature: Optional[float] = None
    
    depth: Optional[float] = Field(None, description="Profundidade da medição (cm)")
    description: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "record_id": "record-001",
                "parcel_id": "talhao-A",
                "cliente_id": "cliente123",
                "soil_temperature": 22,
                "soil_moisture": 65,
                "atmospheric_pressure": 1013,
                "air_temperature": 25,
                "depth": 10
            }
        }


class AgriParcelRecordResponse(BaseModel):
    """Modelo de resposta de um registro"""
    id: int
    record_id: str
    parcel_id: str
    cliente_id: str
    soil_temperature: Optional[float]
    soil_moisture: Optional[float]
    atmospheric_pressure: Optional[float]
    air_temperature: Optional[float]
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# AGRI PARCEL OPERATION (Operações)
# ============================================================================

class AgriParcelOperationCreate(BaseModel):
    """Modelo para criar uma operação"""
    operation_id: str = Field(..., description="ID único da operação")
    parcel_id: str = Field(..., description="ID do talhão")
    cliente_id: str = Field(..., description="ID do cliente")
    
    operation_type: str = Field(..., description="fertilising, irrigation, harvesting, sowing, etc")
    description: Optional[str] = None
    status: str = Field("planned", description="planned, ongoing, finished, cancelled")
    
    # Datas
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # Recursos
    operator: Optional[str] = None
    water_source: Optional[str] = None
    working_area: Optional[float] = None
    
    # Quantidade e produto
    quantity: Optional[float] = None
    quantity_unit: Optional[str] = None
    product_type: Optional[str] = None
    
    # Custo
    reported_cost: Optional[float] = None
    cost_currency: str = "BRL"
    
    # Relacionamento com fertilização
    fertilize_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "operation_id": "operation-001",
                "parcel_id": "talhao-A",
                "cliente_id": "cliente123",
                "operation_type": "fertilising",
                "description": "Aplicação de NPK",
                "status": "planned",
                "planned_start": "2026-01-25T08:00:00",
                "operator": "José Silva",
                "quantity": 500,
                "quantity_unit": "kg",
                "product_type": "NPK 10-10-10"
            }
        }


class AgriParcelOperationUpdate(BaseModel):
    """Modelo para atualizar uma operação"""
    description: Optional[str] = None
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    operator: Optional[str] = None
    quantity: Optional[float] = None
    reported_cost: Optional[float] = None


class AgriParcelOperationResponse(BaseModel):
    """Modelo de resposta de uma operação"""
    id: int
    operation_id: str
    parcel_id: str
    cliente_id: str
    operation_type: str
    description: Optional[str]
    status: str
    planned_start: Optional[datetime]
    planned_end: Optional[datetime]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    operator: Optional[str]
    quantity: Optional[float]
    quantity_unit: Optional[str]
    product_type: Optional[str]
    reported_cost: Optional[float]
    criado_em: datetime
    atualizado_em: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# AGRI FERTILIZE (Fertilização)
# ============================================================================

class AgriFertilizeCreate(BaseModel):
    """Modelo para criar um registro de fertilização"""
    fertilize_id: str = Field(..., description="ID único do fertilizante")
    cliente_id: str = Field(..., description="ID do cliente")
    
    product_name: str = Field(..., description="Nome do produto")
    product_code: Optional[str] = None
    manufacturer: Optional[str] = None
    
    fertilizer_type: Optional[str] = Field(None, description="organic, inorganic, mixed")
    application_method: Optional[str] = Field(None, description="spreading, fertigation, foliar")
    
    # Composição
    nitrogen_content: Optional[float] = Field(None, description="% N")
    phosphorous_content: Optional[float] = Field(None, description="% P")
    potassium_content: Optional[float] = Field(None, description="% K")
    micronutrients: Optional[List[str]] = None
    
    # Quantidade
    quantity: Optional[float] = None
    quantity_unit: str = "kg"
    recommended_dose: Optional[float] = None
    recommended_dose_unit: Optional[str] = None
    
    description: Optional[str] = None
    safety_instructions: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "fertilize_id": "fertilize-001",
                "cliente_id": "cliente123",
                "product_name": "NPK 10-10-10",
                "manufacturer": "FertiBrasil",
                "fertilizer_type": "inorganic",
                "application_method": "spreading",
                "nitrogen_content": 10,
                "phosphorous_content": 10,
                "potassium_content": 10,
                "micronutrients": ["Zn", "B"],
                "quantity": 500,
                "recommended_dose": 300,
                "recommended_dose_unit": "kg/ha"
            }
        }


class AgriFertilizeUpdate(BaseModel):
    """Modelo para atualizar um fertilizante"""
    product_name: Optional[str] = None
    description: Optional[str] = None
    nitrogen_content: Optional[float] = None
    phosphorous_content: Optional[float] = None
    potassium_content: Optional[float] = None
    recommended_dose: Optional[float] = None


class AgriFertilizeResponse(BaseModel):
    """Modelo de resposta de um fertilizante"""
    id: int
    fertilize_id: str
    cliente_id: str
    product_name: str
    manufacturer: Optional[str]
    fertilizer_type: Optional[str]
    nitrogen_content: Optional[float]
    phosphorous_content: Optional[float]
    potassium_content: Optional[float]
    micronutrients: Optional[List[str]]
    quantity: Optional[float]
    quantity_unit: str
    recommended_dose: Optional[float]
    recommended_dose_unit: Optional[str]
    criado_em: datetime
    atualizado_em: datetime
    
    class Config:
        from_attributes = True
