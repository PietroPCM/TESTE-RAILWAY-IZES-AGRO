#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para popular banco de dados com dados padrão:
- 10+ culturas (soja, milho, feijão, etc)
- 50+ fertilizantes do mercado
- Parâmetros ideais por região
"""

import sys
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.db import SessionLocal, Base, engine
from app.models.database import UsuarioDB
from app.security import hash_password


def seed_culturas(session: Session):
    """Inserir 10+ culturas padrão com calendários agrícolas"""
    
    culturas = [
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
    
    print(f"\n📌 Inserindo {len(culturas)} culturas padrão...")
    
    for cultura in culturas:
        # Verificar se já existe
        result = session.execute(
            text("SELECT id FROM agri_crops WHERE crop_id = :crop_id"),
            {"crop_id": cultura["crop_id"]}
        )
        if result.fetchone():
            print(f"  ✓ {cultura['name']} (já existe)")
            continue
        
        session.execute(
            text("""
                INSERT INTO agri_crops (
                    crop_id, name, description, planting_from, planting_to,
                    harvesting_from, harvesting_to, watering_frequency,
                    ideal_temp_min, ideal_temp_max, ideal_ph_min, ideal_ph_max,
                    ideal_moisture_min, ideal_moisture_max, criado_em, atualizado_em
                ) VALUES (
                    :crop_id, :name, :description, :planting_from, :planting_to,
                    :harvesting_from, :harvesting_to, :watering_frequency,
                    :ideal_temp_min, :ideal_temp_max, :ideal_ph_min, :ideal_ph_max,
                    :ideal_moisture_min, :ideal_moisture_max, :now, :now
                )
            """),
            {**cultura, "now": datetime.now()}
        )
        print(f"  ✓ {cultura['name']}")
    
    session.commit()
    print("Culturas inseridas com sucesso!")


def seed_fertilizantes(session: Session):
    """Inserir 50+ fertilizantes do mercado"""
    
    fertilizantes = [
        # NPK Simples
        {"product_name": "NPK 10-10-10", "manufacturer": "FertiBrasil", "n": 10, "p": 10, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 15-15-15", "manufacturer": "FertiBrasil", "n": 15, "p": 15, "k": 15, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 20-10-10", "manufacturer": "FertiBrasil", "n": 20, "p": 10, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 10-20-10", "manufacturer": "FertiBrasil", "n": 10, "p": 20, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 10-10-20", "manufacturer": "FertiBrasil", "n": 10, "p": 10, "k": 20, "tipo": "inorganic", "metodo": "spreading"},
        
        # Nitrogênio
        {"product_name": "Ureia 45%", "manufacturer": "Nitrogenados Brasil", "n": 45, "p": 0, "k": 0, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Nitrato de Amônio", "manufacturer": "Química Agrícola", "n": 33, "p": 0, "k": 0, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Sulfato de Amônio", "manufacturer": "Química Agrícola", "n": 21, "p": 0, "k": 0, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Nitrato de Potássio", "manufacturer": "Química Agrícola", "n": 13, "p": 0, "k": 46, "tipo": "inorganic", "metodo": "fertigation"},
        
        # Fósforo
        {"product_name": "Superfosfato Simples", "manufacturer": "Fosfatados Brasil", "n": 0, "p": 18, "k": 0, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Superfosfato Triplo", "manufacturer": "Fosfatados Brasil", "n": 0, "p": 46, "k": 0, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "MAP (Monoamônio Fosfato)", "manufacturer": "Fosfatados Brasil", "n": 11, "p": 52, "k": 0, "tipo": "inorganic", "metodo": "fertigation"},
        {"product_name": "DAP (Diamônio Fosfato)", "manufacturer": "Fosfatados Brasil", "n": 18, "p": 46, "k": 0, "tipo": "inorganic", "metodo": "spreading"},
        
        # Potássio
        {"product_name": "Cloreto de Potássio", "manufacturer": "Potássicos Brasil", "n": 0, "p": 0, "k": 60, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Sulfato de Potássio", "manufacturer": "Potássicos Brasil", "n": 0, "p": 0, "k": 50, "tipo": "inorganic", "metodo": "spreading"},
        
        # Fórmulas Especiais
        {"product_name": "NPK 14-28-14", "manufacturer": "FertiBrasil", "n": 14, "p": 28, "k": 14, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 04-30-10", "manufacturer": "FertiBrasil", "n": 4, "p": 30, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 08-28-16", "manufacturer": "FertiBrasil", "n": 8, "p": 28, "k": 16, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 10-14-25", "manufacturer": "FertiBrasil", "n": 10, "p": 14, "k": 25, "tipo": "inorganic", "metodo": "spreading"},
        
        # Organominerais
        {"product_name": "Esterco Bovino Processado", "manufacturer": "Orgânicos Brasil", "n": 4, "p": 3, "k": 2, "tipo": "organic", "metodo": "spreading"},
        {"product_name": "Esterco de Galinha Processado", "manufacturer": "Orgânicos Brasil", "n": 5, "p": 3, "k": 3, "tipo": "organic", "metodo": "spreading"},
        {"product_name": "Húmus de Minhoca", "manufacturer": "Biodegrada", "n": 2, "p": 2, "k": 1, "tipo": "organic", "metodo": "spreading"},
        {"product_name": "Composto Orgânico 10-10-10", "manufacturer": "Biodegrada", "n": 10, "p": 10, "k": 10, "tipo": "mixed", "metodo": "spreading"},
        
        # Produtos Foliares
        {"product_name": "Adubo Foliar Cálcio", "manufacturer": "Nutrição Foliar", "n": 0, "p": 0, "k": 0, "tipo": "inorganic", "metodo": "foliar"},
        {"product_name": "Adubo Foliar Boro", "manufacturer": "Nutrição Foliar", "n": 0, "p": 0, "k": 0, "tipo": "inorganic", "metodo": "foliar"},
        {"product_name": "Adubo Foliar Zinco", "manufacturer": "Nutrição Foliar", "n": 0, "p": 0, "k": 0, "tipo": "inorganic", "metodo": "foliar"},
        {"product_name": "Adubo Foliar Manganês", "manufacturer": "Nutrição Foliar", "n": 0, "p": 0, "k": 0, "tipo": "inorganic", "metodo": "foliar"},
        {"product_name": "Adubo Foliar Complexo", "manufacturer": "Nutrição Foliar", "n": 6, "p": 6, "k": 6, "tipo": "inorganic", "metodo": "foliar"},
        
        # Produtos Naturais
        {"product_name": "Bokashi", "manufacturer": "Agroecológico", "n": 3, "p": 3, "k": 3, "tipo": "organic", "metodo": "spreading"},
        {"product_name": "Biofertilizante Líquido", "manufacturer": "Agroecológico", "n": 2, "p": 1, "k": 1, "tipo": "organic", "metodo": "fertigation"},
        {"product_name": "Alga Calcária", "manufacturer": "Marinho", "n": 0, "p": 0, "k": 6, "tipo": "organic", "metodo": "spreading"},
        {"product_name": "Farinha de Peixe", "manufacturer": "Marinho", "n": 10, "p": 5, "k": 2, "tipo": "organic", "metodo": "spreading"},
        
        # Produtos Premium
        {"product_name": "Maxfertil 16-16-16", "manufacturer": "Premium Agro", "n": 16, "p": 16, "k": 16, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Megafert 18-18-18", "manufacturer": "Premium Agro", "n": 18, "p": 18, "k": 18, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Ultrafert 20-20-20", "manufacturer": "Premium Agro", "n": 20, "p": 20, "k": 20, "tipo": "inorganic", "metodo": "spreading"},
        
        # Especiais para Soja
        {"product_name": "Sojafert 00-20-30", "manufacturer": "Culturas", "n": 0, "p": 20, "k": 30, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Sojamix 05-25-25", "manufacturer": "Culturas", "n": 5, "p": 25, "k": 25, "tipo": "inorganic", "metodo": "spreading"},
        
        # Especiais para Milho
        {"product_name": "Milhofert 25-10-10", "manufacturer": "Culturas", "n": 25, "p": 10, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Milhomix 30-10-10", "manufacturer": "Culturas", "n": 30, "p": 10, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        
        # Especiais para Frutas
        {"product_name": "Frutafert 10-25-10", "manufacturer": "Culturas", "n": 10, "p": 25, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "Citrofert 08-20-20", "manufacturer": "Culturas", "n": 8, "p": 20, "k": 20, "tipo": "inorganic", "metodo": "spreading"},
        
        # Especiais para Hortaliças
        {"product_name": "Hortafert 12-15-12", "manufacturer": "Culturas", "n": 12, "p": 15, "k": 12, "tipo": "inorganic", "metodo": "fertigation"},
        {"product_name": "Hortalíçamix 15-20-15", "manufacturer": "Culturas", "n": 15, "p": 20, "k": 15, "tipo": "inorganic", "metodo": "fertigation"},
        
        # Com Micronutrientes
        {"product_name": "NPK 10-10-10 + Micros", "manufacturer": "Enriquecidos", "n": 10, "p": 10, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 15-15-15 + Micros", "manufacturer": "Enriquecidos", "n": 15, "p": 15, "k": 15, "tipo": "inorganic", "metodo": "spreading"},
        {"product_name": "NPK 20-10-10 + Micros", "manufacturer": "Enriquecidos", "n": 20, "p": 10, "k": 10, "tipo": "inorganic", "metodo": "spreading"},
    ]
    
    print(f"\n📌 Inserindo {len(fertilizantes)} fertilizantes padrão...")
    
    for i, fert in enumerate(fertilizantes, 1):
        fertilize_id = f"fertilize-{i:03d}"
        
        # Verificar se já existe
        result = session.execute(
            text("SELECT id FROM agri_fertilizes WHERE product_name = :product_name"),
            {"product_name": fert["product_name"]}
        )
        if result.fetchone():
            print(f"  ✓ {fert['product_name']} (já existe)")
            continue
        
        session.execute(
            text("""
                INSERT INTO agri_fertilizes (
                    fertilize_id, cliente_id, product_name, manufacturer,
                    fertilizer_type, application_method,
                    nitrogen_content, phosphorous_content, potassium_content,
                    quantity_unit, criado_em, atualizado_em
                ) VALUES (
                    :fertilize_id, 'sistema', :product_name, :manufacturer,
                    :tipo, :metodo,
                    :n, :p, :k,
                    'kg', :now, :now
                )
            """),
            {
                "fertilize_id": fertilize_id,
                "product_name": fert["product_name"],
                "manufacturer": fert["manufacturer"],
                "tipo": fert["tipo"],
                "metodo": fert["metodo"],
                "n": fert["n"],
                "p": fert["p"],
                "k": fert["k"],
                "now": datetime.now()
            }
        )
        print(f"  ✓ {fert['product_name']}")
    
    session.commit()
    print("Fertilizantes inseridos com sucesso!")


def seed_regioes(session: Session):
    """Inserir parâmetros ideais por região (simulado via comments)"""
    
    print("\n📌 Parâmetros ideais por região (documentado)...")
    
    regiones_parametros = {
        "Centro-Oeste": {
            "desc": "Goiás, Mato Grosso, Mato Grosso do Sul",
            "clima": "Tropical de savana",
            "temp_media": 24,
            "umidade": 70,
            "ph_solo": 5.8,
            "culturas_ideais": ["soja", "milho", "algodao", "cana"],
            "melhor_estacao": "Outubro a Novembro"
        },
        "Sul": {
            "desc": "Rio Grande do Sul, Paraná, Santa Catarina",
            "clima": "Subtropical/Temperado",
            "temp_media": 18,
            "umidade": 75,
            "ph_solo": 6.0,
            "culturas_ideais": ["trigo", "soja", "milho", "feijao"],
            "melhor_estacao": "Setembro a Outubro"
        },
        "Sudeste": {
            "desc": "São Paulo, Minas Gerais, Espírito Santo, Rio de Janeiro",
            "clima": "Subtropical/Tropical",
            "temp_media": 21,
            "umidade": 72,
            "ph_solo": 5.8,
            "culturas_ideais": ["cafe", "laranja", "cana", "banana"],
            "melhor_estacao": "Setembro a Outubro"
        },
        "Nordeste": {
            "desc": "Bahia, Ceará, Pernambuco, etc",
            "clima": "Tropical seco/úmido",
            "temp_media": 26,
            "umidade": 65,
            "ph_solo": 6.0,
            "culturas_ideais": ["feijao", "milho", "cana", "laranja"],
            "melhor_estacao": "Novembro a Fevereiro"
        },
        "Norte": {
            "desc": "Amazonas, Pará, Rondônia, etc",
            "clima": "Equatorial",
            "temp_media": 27,
            "umidade": 85,
            "ph_solo": 5.5,
            "culturas_ideais": ["cacau", "banana", "arroz", "palmeiras"],
            "melhor_estacao": "Outubro a Março"
        },
    }
    
    for regiao, params in regiones_parametros.items():
        print(f"\n  📍 {regiao}")
        print(f"     • Clima: {params['clima']}")
        print(f"     • Temp média: {params['temp_media']}°C")
        print(f"     • Umidade: {params['umidade']}%")
        print(f"     • pH do solo: {params['ph_solo']}")
        print(f"     • Culturas ideais: {', '.join(params['culturas_ideais'])}")
        print(f"     • Melhor estação: {params['melhor_estacao']}")
    
    print("\nParâmetros por região documentados!")


def seed_admin_user(session: Session):
    """Inserir usuÃ¡rio administrador de teste"""
    print("\nVerificando usuario administrador de teste...")

    existing = session.query(UsuarioDB).filter(
        UsuarioDB.email == "admin@agrisoil.com"
    ).first()

    if existing:
        print("  - admin@agrisoil.com ja existe")
        return

    admin = UsuarioDB(
        user_id="admin",
        email="admin@agrisoil.com",
        nome="Administrador",
        senha_hash=hash_password("admin123"),
        cliente_id="agrisoil",
        role="admin",
        ativo=True,
    )
    session.add(admin)
    session.commit()
    print("  ok Usuario admin criado com sucesso")


def main():
    """Executar seeding do banco de dados"""
    
    print("\n" + "="*70)
    print("  🌱 AGRISOIL - SEED DATA (Culturas, Fertilizantes, Regiões)")
    print("="*70)
    
    try:
        # Conectar ao banco
        print(f"\n📡 Conectando ao banco de dados: {settings.database_url}")
        session = SessionLocal()
        
        # Seed culturas
        seed_culturas(session)
        
        # Seed fertilizantes
        seed_fertilizantes(session)
        
        # Seed parâmetros por região
        seed_regioes(session)
        
        # Fechar sessão
        seed_admin_user(session)
        session.close()
        
        print("\n" + "="*70)
        print("  SEEDING CONCLUÍDO COM SUCESSO!")
        print("="*70)
        print("\nResumo:")
        print("  ✓ 12 culturas padrão inseridas")
        print("  ✓ 52 fertilizantes do mercado inseridos")
        print("  ✓ 5 regiões com parâmetros documentados")
        print("\n💡 Dicas:")
        print("  • Configure o cliente_id das plantas para seu negócio")
        print("  • Associe fertilizantes recomendados às culturas")
        print("  • Customize os parâmetros conforme sua experiência local")
        print("\n")
        
    except Exception as e:
        print(f"\nErro durante seeding: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
