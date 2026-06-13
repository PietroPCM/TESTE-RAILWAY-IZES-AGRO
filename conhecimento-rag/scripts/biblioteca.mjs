import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.slice(1)), "..");
const ACCESS_DATE = new Date().toISOString().slice(0, 10);
const MANIFEST_PATH = path.join(ROOT, "scripts", "documentos.json");
const VALIDATION_PATH = path.join(ROOT, "validacao", "resultado_validacao.json");
const EXTRACTION_PATH = path.join(ROOT, "validacao", "resultado_extracao.json");
const METADATA_PATH = path.join(ROOT, "validacao", "metadados_coletados.json");

const INVENTORY_COLUMNS = [
  "documento_id", "titulo", "instituicao", "autores", "ano", "url_original",
  "data_acesso", "caminho_original", "caminho_extraido", "tipo_arquivo",
  "tamanho_bytes", "sha256", "tema", "subtema", "cultura", "regiao",
  "licenca", "idioma", "tipo_extracao", "status_validacao", "observacoes"
];

const THEMES = [
  "Solo e análise de solo", "pH e acidez", "Correção do solo", "Nitrogênio",
  "Fósforo", "Potássio", "Umidade do solo", "Irrigação",
  "Condutividade elétrica", "Sensores agrícolas", "Calibração de sensores",
  "Limitações de sensores NPK de baixo custo", "Batata-doce", "Soja", "Milho",
  "Manejo aplicável ao Paraná e Sul do Brasil"
];

const REQUIRED_FIELDS = [
  "documento_id", "titulo", "instituicao", "ano", "url_pagina", "url_original",
  "pasta_original", "arquivo", "pasta_extraido", "tema", "regiao", "licenca",
  "idioma"
];

const FORBIDDEN_NAMES = new Set([
  "resumo.md", "resumo_tecnico.md", "sintese.md", "explicacao.md",
  "conhecimento_gerado.md"
]);

function relative(filePath) {
  return path.relative(ROOT, filePath).replaceAll("\\", "/");
}

function originalPath(doc) {
  return path.join(ROOT, "originais", doc.pasta_original, doc.arquivo);
}

function extractedPath(doc) {
  return path.join(ROOT, "extraidos", doc.pasta_extraido, `${doc.documento_id}.txt`);
}

function csvCell(value) {
  const text = String(value ?? "");
  return `"${text.replaceAll("\"", "\"\"")}"`;
}

function csv(columns, rows) {
  return [
    columns.join(","),
    ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(","))
  ].join("\r\n") + "\r\n";
}

function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

function isHtml(buffer) {
  const start = buffer.subarray(0, 4096).toString("utf8").trimStart().toLowerCase();
  return start.startsWith("<!doctype html") || start.startsWith("<html") ||
    start.includes("<head") || start.includes("<body");
}

function decodeHtml(text) {
  return text
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", "\"")
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, number) => String.fromCodePoint(Number(number)));
}

function metaValues(html, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const expression = new RegExp(
    `<meta\\s+name=["']${escaped}["'][^>]*content=["']([^"']*)["'][^>]*>`,
    "gi"
  );
  return [...html.matchAll(expression)].map((match) => decodeHtml(match[1].trim()));
}

async function loadJson(filePath, fallback = []) {
  try {
    return JSON.parse(await readFile(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

async function ensureStructure() {
  const dirs = [
    "fontes", "scripts", "validacao", "pendencias",
    "originais/embrapa", "originais/idr_parana", "originais/iapar",
    "originais/fao", "originais/universidades", "originais/artigos_cientificos",
    "originais/extensao_rural", "originais/outros_oficiais",
    "extraidos/solo", "extraidos/nutrientes", "extraidos/irrigacao",
    "extraidos/sensores", "extraidos/batata_doce", "extraidos/soja",
    "extraidos/milho"
  ];
  await Promise.all(dirs.map((dir) => mkdir(path.join(ROOT, dir), { recursive: true })));
}

async function collectOfficialMetadata(doc) {
  const result = { documento_id: doc.documento_id, url_pagina: doc.url_pagina };
  try {
    const response = await fetch(doc.url_pagina, {
      headers: { "user-agent": "IZES-AGRO-document-library/1.0" },
      redirect: "follow"
    });
    result.status_http = response.status;
    result.url_final = response.url;
    result.content_type = response.headers.get("content-type") ?? "";
    if (!response.ok) {
      result.erro = `HTTP ${response.status}`;
      return result;
    }
    const html = await response.text();
    result.titulo = metaValues(html, "DC.title")[0] ??
      metaValues(html, "citation_title")[0] ?? "";
    result.autores = [
      ...metaValues(html, "citation_author"),
      ...metaValues(html, "DC.creator")
    ];
    if (result.autores.length === 0) {
      result.autores = metaValues(html, "DC.contributor");
    }
    result.ano = metaValues(html, "DCTERMS.issued")[0] ??
      metaValues(html, "citation_date")[0] ?? "";
    result.direitos = metaValues(html, "DC.rights");
    result.pdf_declarado = metaValues(html, "citation_pdf_url")[0] ?? "";
  } catch (error) {
    result.erro = error.message;
  }
  return result;
}

async function download() {
  await ensureStructure();
  const docs = await loadJson(MANIFEST_PATH);
  const metadata = [];
  const results = [];

  for (const doc of docs) {
    metadata.push(await collectOfficialMetadata(doc));
    const destination = originalPath(doc);
    await mkdir(path.dirname(destination), { recursive: true });
    try {
      let buffer;
      let responseData;
      try {
        const existing = await readFile(destination);
        if (existing.length > 0) {
          buffer = existing;
          responseData = { status: "existente", contentType: "" };
        }
      } catch {
        // Download only when no preserved original is present.
      }
      if (!buffer) {
        const response = await fetch(doc.url_original, {
          headers: {
            "user-agent": "Mozilla/5.0 (compatible; IZES-AGRO-document-library/1.0)",
            accept: "application/pdf,*/*;q=0.8"
          },
          redirect: "follow"
        });
        const arrayBuffer = await response.arrayBuffer();
        buffer = Buffer.from(arrayBuffer);
        responseData = {
          status: response.status,
          finalUrl: response.url,
          contentType: response.headers.get("content-type") ?? ""
        };
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        await writeFile(destination, buffer);
      }
      results.push({
        documento_id: doc.documento_id,
        caminho: relative(destination),
        tamanho_bytes: buffer.length,
        ...responseData
      });
      console.log(`download: ${doc.documento_id} (${buffer.length} bytes)`);
    } catch (error) {
      results.push({
        documento_id: doc.documento_id,
        caminho: relative(destination),
        erro: error.message
      });
      console.error(`download falhou: ${doc.documento_id}: ${error.message}`);
    }
  }

  await writeFile(METADATA_PATH, JSON.stringify(metadata, null, 2) + "\n");
  await writeFile(
    path.join(ROOT, "validacao", "resultado_download.json"),
    JSON.stringify(results, null, 2) + "\n"
  );
}

async function validate() {
  await ensureStructure();
  const docs = await loadJson(MANIFEST_PATH);
  const results = [];
  const hashes = new Map();

  for (const doc of docs) {
    const filePath = originalPath(doc);
    const result = {
      documento_id: doc.documento_id,
      caminho: relative(filePath),
      valido: false,
      html_falso: false,
      duplicado_de: "",
      erros: []
    };
    try {
      const buffer = await readFile(filePath);
      result.tamanho_bytes = buffer.length;
      result.sha256 = sha256(buffer);
      result.html_falso = isHtml(buffer);
      if (result.html_falso) result.erros.push("arquivo contém HTML");
      if (!buffer.subarray(0, 5).equals(Buffer.from("%PDF-"))) {
        result.erros.push("assinatura PDF ausente");
      }
      if (buffer.length < 1024) result.erros.push("arquivo menor que 1024 bytes");

      try {
        const pdf = await getDocument({
          data: new Uint8Array(buffer),
          disableWorker: true,
          useSystemFonts: true
        }).promise;
        result.paginas = pdf.numPages;
        if (pdf.numPages < 1) result.erros.push("PDF sem páginas");
        await pdf.destroy();
      } catch (error) {
        result.erros.push(`PDF não abriu: ${error.message}`);
      }

      if (hashes.has(result.sha256)) {
        result.duplicado_de = hashes.get(result.sha256);
        result.erros.push(`duplicado por SHA-256 de ${result.duplicado_de}`);
      } else {
        hashes.set(result.sha256, doc.documento_id);
      }
      result.valido = result.erros.length === 0;
    } catch (error) {
      result.erros.push(`arquivo inexistente ou ilegível: ${error.message}`);
    }
    results.push(result);
    console.log(`validacao: ${doc.documento_id}: ${result.valido ? "VALIDO" : "INVALIDO"}`);
  }
  await writeFile(VALIDATION_PATH, JSON.stringify(results, null, 2) + "\n");

  const invalidRows = results.filter((result) => !result.valido).map((result) => ({
    documento_id: result.documento_id,
    caminho: result.caminho,
    motivo: result.erros.join("; ")
  }));
  await writeFile(
    path.join(ROOT, "validacao", "documentos_invalidos.csv"),
    csv(["documento_id", "caminho", "motivo"], invalidRows)
  );
}

function pageText(content) {
  const lines = [];
  let current = "";
  let previousY = null;
  for (const item of content.items) {
    if (!("str" in item)) continue;
    const y = Array.isArray(item.transform) ? item.transform[5] : null;
    const changedLine = previousY !== null && y !== null && Math.abs(y - previousY) > 2;
    if ((changedLine || item.hasEOL) && current.trim()) {
      lines.push(current.trimEnd());
      current = "";
    }
    if (current && item.str && !current.endsWith(" ") && !item.str.startsWith(" ")) {
      current += " ";
    }
    current += item.str;
    previousY = y;
    if (item.hasEOL && current.trim()) {
      lines.push(current.trimEnd());
      current = "";
    }
  }
  if (current.trim()) lines.push(current.trimEnd());
  return lines.join("\n");
}

async function extract() {
  await ensureStructure();
  const docs = await loadJson(MANIFEST_PATH);
  const validation = await loadJson(VALIDATION_PATH);
  const metadata = await loadJson(METADATA_PATH);
  const validationById = new Map(validation.map((item) => [item.documento_id, item]));
  const metadataById = new Map(metadata.map((item) => [item.documento_id, item]));
  const results = [];

  for (const doc of docs) {
    const original = originalPath(doc);
    const destination = extractedPath(doc);
    const valid = validationById.get(doc.documento_id);
    if (!valid?.valido) {
      results.push({
        documento_id: doc.documento_id,
        sucesso: false,
        tipo_extracao: "não executada",
        erro: "documento original não validado",
        revisao_humana: true
      });
      continue;
    }
    try {
      const buffer = await readFile(original);
      const pdf = await getDocument({
        data: new Uint8Array(buffer),
        disableWorker: true,
        useSystemFonts: true
      }).promise;
      const pages = [];
      let characterCount = 0;
      for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
        const page = await pdf.getPage(pageNumber);
        const content = await page.getTextContent({ includeMarkedContent: true });
        const text = pageText(content);
        characterCount += text.replace(/\s/g, "").length;
        pages.push(`--- PÁGINA ${pageNumber} ---\n${text}`);
        page.cleanup();
      }
      await pdf.destroy();

      const official = metadataById.get(doc.documento_id);
      const authors = doc.autores || official?.autores?.join("; ") || "";
      const frontmatter = [
        "---",
        `documento_id: ${doc.documento_id}`,
        `titulo: ${doc.titulo}`,
        `instituicao: ${doc.instituicao}`,
        `autores: ${authors}`,
        `ano: ${doc.ano}`,
        `url_original: ${doc.url_original}`,
        `arquivo_original: ${relative(original)}`,
        `sha256: ${valid.sha256}`,
        `data_acesso: ${ACCESS_DATE}`,
        "tipo_extracao: camada textual do PDF",
        "--------------",
        ""
      ].join("\n");
      await mkdir(path.dirname(destination), { recursive: true });
      await writeFile(destination, frontmatter + pages.join("\n\n") + "\n", "utf8");

      const sparse = characterCount < Math.max(100, pdf.numPages * 20);
      results.push({
        documento_id: doc.documento_id,
        sucesso: !sparse,
        caminho_extraido: relative(destination),
        paginas: pdf.numPages,
        caracteres_sem_espaco: characterCount,
        tipo_extracao: "camada textual do PDF",
        erro: sparse ? "camada textual ausente ou insuficiente; OCR necessário" : "",
        revisao_humana: sparse
      });
      console.log(`extracao: ${doc.documento_id}: ${pdf.numPages} páginas`);
    } catch (error) {
      results.push({
        documento_id: doc.documento_id,
        sucesso: false,
        caminho_extraido: relative(destination),
        tipo_extracao: "falha",
        erro: error.message,
        revisao_humana: true
      });
      console.error(`extracao falhou: ${doc.documento_id}: ${error.message}`);
    }
  }

  await writeFile(EXTRACTION_PATH, JSON.stringify(results, null, 2) + "\n");
  const failures = results.filter((result) => !result.sucesso).map((result) => ({
    documento_id: result.documento_id,
    caminho_original: relative(originalPath(docs.find((doc) => doc.documento_id === result.documento_id))),
    motivo: result.erro,
    revisao_humana: result.revisao_humana ? "SIM" : "NÃO"
  }));
  await writeFile(
    path.join(ROOT, "validacao", "extracoes_com_falha.csv"),
    csv(["documento_id", "caminho_original", "motivo", "revisao_humana"], failures)
  );
}

async function inventory() {
  await ensureStructure();
  const docs = await loadJson(MANIFEST_PATH);
  const validation = await loadJson(VALIDATION_PATH);
  const extraction = await loadJson(EXTRACTION_PATH);
  const metadata = await loadJson(METADATA_PATH);
  const failures = extraction.filter((result) => !result.sucesso).map((result) => ({
    documento_id: result.documento_id,
    caminho_original: relative(originalPath(docs.find((doc) => doc.documento_id === result.documento_id))),
    motivo: result.erro,
    revisao_humana: result.revisao_humana ? "SIM" : "NÃO"
  }));
  await writeFile(
    path.join(ROOT, "validacao", "extracoes_com_falha.csv"),
    csv(["documento_id", "caminho_original", "motivo", "revisao_humana"], failures)
  );
  const validationById = new Map(validation.map((item) => [item.documento_id, item]));
  const extractionById = new Map(extraction.map((item) => [item.documento_id, item]));
  const metadataById = new Map(metadata.map((item) => [item.documento_id, item]));

  const rows = docs.map((doc) => {
    const valid = validationById.get(doc.documento_id);
    const extracted = extractionById.get(doc.documento_id);
    const official = metadataById.get(doc.documento_id);
    return {
      documento_id: doc.documento_id,
      titulo: doc.titulo,
      instituicao: doc.instituicao,
      autores: doc.autores || official?.autores?.join("; ") || "",
      ano: doc.ano,
      url_original: doc.url_original,
      data_acesso: ACCESS_DATE,
      caminho_original: relative(originalPath(doc)),
      caminho_extraido: extracted?.sucesso ? relative(extractedPath(doc)) : "",
      tipo_arquivo: "PDF",
      tamanho_bytes: valid?.tamanho_bytes ?? "",
      sha256: valid?.sha256 ?? "",
      tema: doc.tema,
      subtema: doc.subtema,
      cultura: doc.cultura,
      regiao: doc.regiao,
      licenca: doc.licenca,
      idioma: doc.idioma,
      tipo_extracao: extracted?.tipo_extracao ?? "",
      status_validacao: valid?.valido ? "VÁLIDO" : "INVÁLIDO",
      observacoes: [
        valid?.duplicado_de ? `duplicado de ${valid.duplicado_de}` : "",
        extracted?.erro ?? ""
      ].filter(Boolean).join("; ")
    };
  });
  await writeFile(
    path.join(ROOT, "fontes", "inventario_documentos.csv"),
    csv(INVENTORY_COLUMNS, rows)
  );

  const coverageRows = THEMES.map((theme) => {
    const themedDocs = docs.filter((doc) => doc.tema.split("|").includes(theme));
    const accepted = themedDocs.filter((doc) => validationById.get(doc.documento_id)?.valido);
    const extracted = accepted.filter((doc) => extractionById.get(doc.documento_id)?.sucesso);
    const brazilian = accepted.filter((doc) =>
      ["Embrapa", "IDR-Paraná", "IAPAR"].includes(doc.instituicao)
    );
    const parana = accepted.filter((doc) => /Paraná/i.test(doc.regiao));
    let level = "PENDENTE";
    if (accepted.length >= 5 && brazilian.length >= 1 && extracted.length >= 1) level = "FORTE";
    else if (accepted.length >= 3) level = "MÉDIO";
    else if (accepted.length >= 1) level = "FRACO";
    const pending = [];
    if (accepted.length < 3) pending.push("menos de 3 fontes confiáveis aceitas");
    if (brazilian.length < 1) pending.push("sem documento brasileiro aceito");
    if (extracted.length < accepted.length) pending.push("há extração pendente ou inválida");
    return {
      tema: theme,
      quantidade_fontes: accepted.length,
      quantidade_documentos: accepted.length,
      quantidade_pdfs: accepted.length,
      quantidade_paginas_oficiais: 0,
      documentos_brasileiros: brazilian.length,
      documentos_parana: parana.length,
      documentos_extraidos: extracted.length,
      nivel_cobertura: level,
      pendencias: pending.join("; ")
    };
  });
  const coverageColumns = [
    "tema", "quantidade_fontes", "quantidade_documentos", "quantidade_pdfs",
    "quantidade_paginas_oficiais", "documentos_brasileiros", "documentos_parana",
    "documentos_extraidos", "nivel_cobertura", "pendencias"
  ];
  await writeFile(
    path.join(ROOT, "fontes", "matriz_cobertura.csv"),
    csv(coverageColumns, coverageRows)
  );

  const rejected = [];
  for (const row of rows) {
    if (row.status_validacao === "INVÁLIDO") {
      rejected.push({
        titulo: row.titulo,
        url: row.url_original,
        dominio: new URL(row.url_original).hostname,
        motivo_rejeicao: row.observacoes || "arquivo ausente ou inválido",
        data_avaliacao: ACCESS_DATE
      });
    }
    if (row.observacoes.includes("duplicado de")) {
      rejected.push({
        titulo: row.titulo,
        url: row.url_original,
        dominio: new URL(row.url_original).hostname,
        motivo_rejeicao: "arquivo duplicado por SHA-256",
        data_avaliacao: ACCESS_DATE
      });
    }
  }
  await writeFile(
    path.join(ROOT, "fontes", "fontes_rejeitadas.csv"),
    csv(["titulo", "url", "dominio", "motivo_rejeicao", "data_avaliacao"], rejected)
  );

  const pendingRows = coverageRows
    .filter((row) => row.pendencias)
    .map((row) => ({
      documento_id: "",
      titulo: row.tema,
      motivo: row.pendencias,
      acao_necessaria: "localizar e validar fonte original adicional"
    }));
  for (const result of extraction.filter((item) => item.revisao_humana)) {
    const doc = docs.find((item) => item.documento_id === result.documento_id);
    const ocrConcluido = result.sucesso && result.tipo_extracao === "OCR";
    pendingRows.push({
      documento_id: result.documento_id,
      titulo: doc?.titulo ?? "",
      motivo: ocrConcluido ? "OCR concluído; possíveis falhas de reconhecimento" : result.erro,
      acao_necessaria: ocrConcluido
        ? "revisão humana da qualidade do texto OCR"
        : "revisão humana; aplicar OCR somente se confirmado PDF escaneado"
    });
  }
  await writeFile(
    path.join(ROOT, "pendencias", "documentos_pendentes.csv"),
    csv(["documento_id", "titulo", "motivo", "acao_necessaria"], pendingRows)
  );
}

async function listFiles(directory) {
  const output = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) output.push(...await listFiles(fullPath));
    else output.push(fullPath);
  }
  return output;
}

async function check() {
  await ensureStructure();
  const docs = await loadJson(MANIFEST_PATH);
  const validation = await loadJson(VALIDATION_PATH);
  const extraction = await loadJson(EXTRACTION_PATH);
  const files = await listFiles(ROOT);
  const errors = [];
  const warnings = [];

  const ids = new Set();
  for (const doc of docs) {
    for (const field of REQUIRED_FIELDS) {
      if (!String(doc[field] ?? "").trim()) errors.push(`${doc.documento_id || "SEM_ID"}: campo obrigatório ${field} vazio`);
    }
    if (ids.has(doc.documento_id)) errors.push(`documento_id duplicado: ${doc.documento_id}`);
    ids.add(doc.documento_id);
    try {
      const original = await stat(originalPath(doc));
      if (!original.isFile()) errors.push(`${doc.documento_id}: caminho original não é arquivo`);
    } catch {
      errors.push(`${doc.documento_id}: caminho original inexistente`);
    }
  }

  for (const file of files) {
    if (FORBIDDEN_NAMES.has(path.basename(file).toLowerCase())) {
      errors.push(`arquivo proibido: ${relative(file)}`);
    }
  }
  for (const result of validation) {
    if (!result.valido) warnings.push(`${result.documento_id}: documento inválido`);
  }
  for (const result of extraction) {
    if (!result.sucesso) warnings.push(`${result.documento_id}: extração falhou ou requer OCR`);
  }

  const quality = {
    data_verificacao: ACCESS_DATE,
    total_manifesto: docs.length,
    documentos_validos: validation.filter((item) => item.valido).length,
    documentos_invalidos: validation.filter((item) => !item.valido).length,
    html_falso: validation.filter((item) => item.html_falso).length,
    duplicados: validation.filter((item) => item.duplicado_de).length,
    documentos_extraidos: extraction.filter((item) => item.sucesso).length,
    extracoes_ocr: extraction.filter((item) => item.tipo_extracao === "OCR").length,
    extracoes_com_falha: extraction.filter((item) => !item.sucesso).length,
    arquivos_proibidos: files.filter((file) => FORBIDDEN_NAMES.has(path.basename(file).toLowerCase())).length,
    erros: errors,
    avisos: warnings
  };
  await writeFile(
    path.join(ROOT, "validacao", "relatorio_qualidade.json"),
    JSON.stringify(quality, null, 2) + "\n"
  );
  console.log(JSON.stringify(quality, null, 2));
  if (errors.length > 0) process.exitCode = 1;
}

async function main() {
  const command = process.argv[2] ?? "check";
  if (command === "download") await download();
  else if (command === "validate") await validate();
  else if (command === "extract") await extract();
  else if (command === "inventory") await inventory();
  else if (command === "check") await check();
  else if (command === "all") {
    await download();
    await validate();
    await extract();
    await inventory();
    await check();
  } else {
    throw new Error(`comando desconhecido: ${command}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
