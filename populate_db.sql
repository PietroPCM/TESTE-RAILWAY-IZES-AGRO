-- Verificar culturas existentes
SELECT COUNT(*) as total_culturas FROM agri_crops;

-- Inserir culturas (se não existirem)
INSERT INTO agri_crops (
  crop_id, name, description, planting_from, planting_to,
  harvesting_from, harvesting_to, watering_frequency,
  ideal_temp_min, ideal_temp_max, ideal_ph_min, ideal_ph_max,
  ideal_moisture_min, ideal_moisture_max
) VALUES
('soja','Soja','Glycine max - Cultura de verão','--10-01','--11-30','--02-01','--04-30','weekly',20,30,6.0,6.5,60,80),
('milho','Milho','Zea mays - Cereal de verão','--09-15','--11-30','--02-01','--05-31','weekly',18,29,5.8,6.5,60,80),
('feijao','Feijão','Phaseolus vulgaris - Leguminosa','--08-01','--11-30','--11-01','--05-31','weekly',18,28,5.5,6.5,55,75),
('trigo','Trigo','Triticum aestivum - Cereal de inverno','--04-15','--06-30','--10-01','--11-30','weekly',15,25,5.8,6.5,50,70),
('arroz','Arroz','Oryza sativa - Cereal aquático','--09-01','--11-30','--03-01','--05-31','daily',20,32,5.5,6.8,85,100),
('cana','Cana-de-Açúcar','Saccharum officinarum - Cultura industrial','--08-01','--11-30','--05-01','--11-30','weekly',22,32,5.5,6.5,65,85),
('algodao','Algodão','Gossypium hirsutum - Fibra','--10-01','--12-31','--05-01','--08-31','weekly',20,32,5.8,6.5,55,75),
('cafe','Café','Coffea arabica - Perene','--10-01','--03-31','--05-01','--09-30','weekly',18,28,5.8,6.5,60,80),
('laranja','Laranja','Citrus sinensis - Perene','--09-01','--12-31','--06-01','--09-30','weekly',20,35,6.0,7.0,60,80),
('banana','Banana','Musa spp - Perene','--01-01','--12-31','--06-01','--12-31','daily',20,35,5.5,6.8,70,90),
('batata','Batata','Solanum tuberosum - Tubérculo','--07-01','--09-30','--11-01','--01-31','daily',15,23,5.5,6.5,65,80),
('tomate','Tomate','Solanum lycopersicum - Hortaliça','--08-01','--02-28','--11-01','--06-30','daily',20,30,6.0,6.8,65,80)
ON CONFLICT (crop_id) DO NOTHING;

-- Inserir fertilizantes
INSERT INTO agri_fertilizes (name, description, npk_n, npk_p, npk_k, type) VALUES
('Nitrogênio (N)', 'Promove crescimento foliar e verde das plantas', 46, 0, 0, 'mineral'),
('Fósforo (P)', 'Estimula desenvolvimento de raízes e flores', 0, 46, 0, 'mineral'),
('Potássio (K)', 'Aumenta resistência a doenças e estiagem', 0, 0, 60, 'mineral'),
('NPK 10-10-10', 'Fertilizante balanceado de uso geral', 10, 10, 10, 'mineral'),
('NPK 20-5-20', 'Formulação com alto nitrogênio e potássio', 20, 5, 20, 'mineral'),
('NPK 4-14-8', 'Enriquecido em fósforo para enraizamento', 4, 14, 8, 'mineral'),
('Sulfato de Amônio', 'Fonte concentrada de nitrogênio (21%)', 21, 0, 0, 'mineral'),
('Composto Orgânico', 'Matéria orgânica fermentada e estabilizada', 2, 1, 1, 'organico'),
('Esterco Bovino', 'Fertilizante natural de decomposição lenta', 1, 1, 1, 'organico'),
('Vermicomposto', 'Adubo produzido por minhocas', 1, 1, 1, 'organico'),
('Calcário Agrícola', 'Corrige acidez do solo e fornece Ca e Mg', 0, 0, 0, 'mineral'),
('Micronutrientes', 'Mistura de B, Cu, Fe, Mn, Mo, Zn', 0, 0, 0, 'mineral')
ON CONFLICT (name) DO NOTHING;

-- Verificar quantas culturas e fertilizantes foram inseridos
SELECT COUNT(*) as total_culturas FROM agri_crops;
SELECT COUNT(*) as total_fertilizantes FROM agri_fertilizes;
