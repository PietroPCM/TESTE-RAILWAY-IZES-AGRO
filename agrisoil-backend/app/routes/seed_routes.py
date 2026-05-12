#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Endpoints para popular banco com dados iniciais (seed data)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db
from app.security import verificar_admin

router = APIRouter(prefix="/seed", tags=["seed"])

# Dados das culturas
CULTURAS = [
    {
        "crop_id": "soja",
        "name": "Soja",
        "description": "Glycine max - Cultura de verão",
        "planting_from": "--10-01",
        "planting_to": "--11-30",
        "harvesting_from": "--02-01",
        "harvesting_to": "--04-30",
        "watering_frequency": "weekly",
        "ideal_temp_min": 20,
        "ideal_temp_max": 30,
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 60,
        "ideal_moisture_max": 80,
    },
    {
        "crop_id": "milho",
        "name": "Milho",
        "description": "Zea mays - Cereal de verão",
        "planting_from": "--09-15",
        "planting_to": "--11-30",
        "harvesting_from": "--02-01",
        "harvesting_to": "--05-31",
        "watering_frequency": "weekly",
        "ideal_temp_min": 18,
        "ideal_temp_max": 29,
        "ideal_ph_min": 5.8,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 60,
        "ideal_moisture_max": 80,
    },
    {
        "crop_id": "feijao",
        "name": "Feijão",
        "description": "Phaseolus vulgaris - Leguminosa",
        "planting_from": "--08-01",
        "planting_to": "--11-30",
        "harvesting_from": "--11-01",
        "harvesting_to": "--05-31",
        "watering_frequency": "weekly",
        "ideal_temp_min": 18,
        "ideal_temp_max": 28,
        "ideal_ph_min": 5.5,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 55,
        "ideal_moisture_max": 75,
    },
    {
        "crop_id": "trigo",
        "name": "Trigo",
        "description": "Triticum aestivum - Cereal de inverno",
        "planting_from": "--04-15",
        "planting_to": "--06-30",
        "harvesting_from": "--10-01",
        "harvesting_to": "--11-30",
        "watering_frequency": "weekly",
        "ideal_temp_min": 15,
        "ideal_temp_max": 25,
        "ideal_ph_min": 5.8,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 50,
        "ideal_moisture_max": 70,
    },
    {
        "crop_id": "arroz",
        "name": "Arroz",
        "description": "Oryza sativa - Cereal aquático",
        "planting_from": "--09-01",
        "planting_to": "--11-30",
        "harvesting_from": "--03-01",
        "harvesting_to": "--05-31",
        "watering_frequency": "daily",
        "ideal_temp_min": 20,
        "ideal_temp_max": 32,
        "ideal_ph_min": 5.5,
        "ideal_ph_max": 6.8,
        "ideal_moisture_min": 85,
        "ideal_moisture_max": 100,
    },
    {
        "crop_id": "cana",
        "name": "Cana-de-Açúcar",
        "description": "Saccharum officinarum - Cultura industrial",
        "planting_from": "--08-01",
        "planting_to": "--11-30",
        "harvesting_from": "--05-01",
        "harvesting_to": "--11-30",
        "watering_frequency": "weekly",
        "ideal_temp_min": 22,
        "ideal_temp_max": 32,
        "ideal_ph_min": 5.5,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 65,
        "ideal_moisture_max": 85,
    },
    {
        "crop_id": "algodao",
        "name": "Algodão",
        "description": "Gossypium hirsutum - Fibra",
        "planting_from": "--10-01",
        "planting_to": "--12-31",
        "harvesting_from": "--05-01",
        "harvesting_to": "--08-31",
        "watering_frequency": "weekly",
        "ideal_temp_min": 20,
        "ideal_temp_max": 32,
        "ideal_ph_min": 5.8,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 55,
        "ideal_moisture_max": 75,
    },
    {
        "crop_id": "cafe",
        "name": "Café",
        "description": "Coffea arabica - Perene",
        "planting_from": "--10-01",
        "planting_to": "--03-31",
        "harvesting_from": "--05-01",
        "harvesting_to": "--09-30",
        "watering_frequency": "weekly",
        "ideal_temp_min": 18,
        "ideal_temp_max": 28,
        "ideal_ph_min": 5.8,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 60,
        "ideal_moisture_max": 80,
    },
    {
        "crop_id": "laranja",
        "name": "Laranja",
        "description": "Citrus sinensis - Perene",
        "planting_from": "--09-01",
        "planting_to": "--12-31",
        "harvesting_from": "--06-01",
        "harvesting_to": "--09-30",
        "watering_frequency": "weekly",
        "ideal_temp_min": 20,
        "ideal_temp_max": 35,
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 7.0,
        "ideal_moisture_min": 60,
        "ideal_moisture_max": 80,
    },
    {
        "crop_id": "banana",
        "name": "Banana",
        "description": "Musa spp - Perene",
        "planting_from": "--01-01",
        "planting_to": "--12-31",
        "harvesting_from": "--06-01",
        "harvesting_to": "--12-31",
        "watering_frequency": "daily",
        "ideal_temp_min": 20,
        "ideal_temp_max": 35,
        "ideal_ph_min": 5.5,
        "ideal_ph_max": 6.8,
        "ideal_moisture_min": 70,
        "ideal_moisture_max": 90,
    },
    {
        "crop_id": "batata",
        "name": "Batata",
        "description": "Solanum tuberosum - Tubérculo",
        "planting_from": "--07-01",
        "planting_to": "--09-30",
        "harvesting_from": "--11-01",
        "harvesting_to": "--01-31",
        "watering_frequency": "daily",
        "ideal_temp_min": 15,
        "ideal_temp_max": 23,
        "ideal_ph_min": 5.5,
        "ideal_ph_max": 6.5,
        "ideal_moisture_min": 65,
        "ideal_moisture_max": 80,
    },
    {
        "crop_id": "tomate",
        "name": "Tomate",
        "description": "Solanum lycopersicum - Hortaliça",
        "planting_from": "--08-01",
        "planting_to": "--02-28",
        "harvesting_from": "--11-01",
        "harvesting_to": "--06-30",
        "watering_frequency": "daily",
        "ideal_temp_min": 20,
        "ideal_temp_max": 30,
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.8,
        "ideal_moisture_min": 65,
        "ideal_moisture_max": 80,
    },
]


@router.post("/crops", status_code=status.HTTP_201_CREATED)
async def seed_crops(
    db: Session = Depends(get_db),
    _=Depends(verificar_admin)
):
    """
    Popular banco com 12 culturas padrão (ADMIN apenas)
    
    Culturas incluídas:
    - Soja, Milho, Feijão, Trigo, Arroz
    - Cana-de-Açúcar, Algodão, Café
    - Laranja, Banana, Batata, Tomate
    """
    inserted = 0
    skipped = 0
    
    for cultura in CULTURAS:
        # Verificar se já existe
        result = db.execute(
            text("SELECT id FROM agri_crops WHERE crop_id = :crop_id"),
            {"crop_id": cultura["crop_id"]}
        ).first()
        
        if result:
            skipped += 1
            continue
        
        # Inserir cultura
        db.execute(
            text("""
                INSERT INTO agri_crops (
                    crop_id, name, description, planting_from, planting_to,
                    harvesting_from, harvesting_to, watering_frequency,
                    ideal_temp_min, ideal_temp_max, ideal_ph_min, ideal_ph_max,
                    ideal_moisture_min, ideal_moisture_max
                ) VALUES (
                    :crop_id, :name, :description, :planting_from, :planting_to,
                    :harvesting_from, :harvesting_to, :watering_frequency,
                    :ideal_temp_min, :ideal_temp_max, :ideal_ph_min, :ideal_ph_max,
                    :ideal_moisture_min, :ideal_moisture_max
                )
            """),
            cultura
        )
        inserted += 1
    
    db.commit()
    
    return {
        "message": "Culturas inseridas com sucesso",
        "inserted": inserted,
        "skipped": skipped,
        "total": len(CULTURAS)
    }
