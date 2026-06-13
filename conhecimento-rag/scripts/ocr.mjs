import { readFile, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { createCanvas, DOMMatrix, ImageData, Path2D } from "@napi-rs/canvas";
import { createWorker } from "tesseract.js";

globalThis.DOMMatrix = DOMMatrix;
globalThis.ImageData = ImageData;
globalThis.Path2D = Path2D;

const { getDocument } = await import("pdfjs-dist/legacy/build/pdf.mjs");
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.slice(1)), "..");
const PDFJS_WASM_URL = new URL("../node_modules/pdfjs-dist/wasm/", import.meta.url).href;
const ACCESS_DATE = new Date().toISOString().slice(0, 10);

function relative(filePath) {
  return path.relative(ROOT, filePath).replaceAll("\\", "/");
}

async function loadJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

const manifest = await loadJson(path.join(ROOT, "scripts", "documentos.json"));
const validationPath = path.join(ROOT, "validacao", "resultado_validacao.json");
const extractionPath = path.join(ROOT, "validacao", "resultado_extracao.json");
const validation = await loadJson(validationPath);
const extraction = await loadJson(extractionPath);
const validationById = new Map(validation.map((item) => [item.documento_id, item]));
const targets = extraction.filter((item) => {
  const valid = validationById.get(item.documento_id);
  return valid?.valido && !item.sucesso &&
    (
      item.erro?.includes("OCR necessário") ||
      item.erro?.startsWith("OCR parcial:") ||
      item.erro === "OCR não produziu texto"
    );
}).sort((a, b) => (a.paginas ?? 0) - (b.paginas ?? 0));

if (targets.length === 0) {
  console.log("Nenhum PDF escaneado pendente de OCR.");
  process.exit(0);
}

for (const target of targets) {
  const doc = manifest.find((item) => item.documento_id === target.documento_id);
  const valid = validationById.get(target.documento_id);
  const original = path.join(ROOT, "originais", doc.pasta_original, doc.arquivo);
  const destination = path.join(ROOT, "extraidos", doc.pasta_extraido, `${doc.documento_id}.txt`);
  const partialPath = path.join(ROOT, "validacao", `ocr_parcial_${doc.documento_id}.json`);
  const language = doc.idioma === "en" ? "eng" : "por";
  const worker = await createWorker(language, 1);
  console.log(`\nOCR iniciado: ${doc.documento_id}`);
  try {
    const buffer = await readFile(original);
    const pdf = await getDocument({
      data: new Uint8Array(buffer),
      disableWorker: true,
      useSystemFonts: true,
      wasmUrl: PDFJS_WASM_URL
    }).promise;
    let pages = [];
    try {
      pages = JSON.parse(await readFile(partialPath, "utf8"));
    } catch {
      // No prior partial OCR.
    }
    let characterCount = pages.join("").replace(/\s/g, "").length;

    for (let pageNumber = pages.length + 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1.0 });
      const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
      const context = canvas.getContext("2d");
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      await page.render({ canvasContext: context, viewport }).promise;
      const image = canvas.toBuffer("image/png");
      const result = await worker.recognize(image);
      const text = result.data.text.replace(/\r\n/g, "\n").trimEnd();
      characterCount += text.replace(/\s/g, "").length;
      pages.push(`--- PÁGINA ${pageNumber} ---\n${text}`);
      page.cleanup();
      await writeFile(partialPath, JSON.stringify(pages) + "\n");

      const partialFrontmatter = [
        "---",
        `documento_id: ${doc.documento_id}`,
        `titulo: ${doc.titulo}`,
        `instituicao: ${doc.instituicao}`,
        `autores: ${doc.autores}`,
        `ano: ${doc.ano}`,
        `url_original: ${doc.url_original}`,
        `arquivo_original: ${relative(original)}`,
        `sha256: ${valid.sha256}`,
        `data_acesso: ${ACCESS_DATE}`,
        "tipo_extracao: OCR",
        "possiveis_falhas_ocr: true",
        "revisao_humana: true",
        `ocr_paginas_processadas: ${pageNumber}/${pdf.numPages}`,
        "--------------",
        ""
      ].join("\n");
      await writeFile(destination, partialFrontmatter + pages.join("\n\n") + "\n", "utf8");
      Object.assign(target, {
        sucesso: false,
        caminho_extraido: relative(destination),
        paginas: pdf.numPages,
        caracteres_sem_espaco: characterCount,
        tipo_extracao: "OCR",
        erro: `OCR parcial: ${pageNumber}/${pdf.numPages} páginas`,
        revisao_humana: true,
        possiveis_falhas_ocr: true
      });
      await writeFile(extractionPath, JSON.stringify(extraction, null, 2) + "\n");
      console.log(`${doc.documento_id}: página ${pageNumber}/${pdf.numPages}`);
    }
    await pdf.destroy();

    const frontmatter = [
      "---",
      `documento_id: ${doc.documento_id}`,
      `titulo: ${doc.titulo}`,
      `instituicao: ${doc.instituicao}`,
      `autores: ${doc.autores}`,
      `ano: ${doc.ano}`,
      `url_original: ${doc.url_original}`,
      `arquivo_original: ${relative(original)}`,
      `sha256: ${valid.sha256}`,
      `data_acesso: ${ACCESS_DATE}`,
      "tipo_extracao: OCR",
      "possiveis_falhas_ocr: true",
      "revisao_humana: true",
      "--------------",
      ""
    ].join("\n");
    await writeFile(destination, frontmatter + pages.join("\n\n") + "\n", "utf8");
    await unlink(partialPath).catch(() => {});

    Object.assign(target, {
      sucesso: characterCount > 0,
      caminho_extraido: relative(destination),
      paginas: pdf.numPages,
      caracteres_sem_espaco: characterCount,
      tipo_extracao: "OCR",
      erro: characterCount > 0 ? "" : "OCR não produziu texto",
      revisao_humana: true,
      possiveis_falhas_ocr: true
    });
    await writeFile(extractionPath, JSON.stringify(extraction, null, 2) + "\n");
  } catch (error) {
    target.erro = `OCR falhou: ${error.message}`;
    target.revisao_humana = true;
    await writeFile(extractionPath, JSON.stringify(extraction, null, 2) + "\n");
    console.error(`OCR falhou: ${doc.documento_id}: ${error.message}`);
  } finally {
    await worker.terminate();
  }
}

console.log("\nOCR concluído. Todos os resultados permanecem marcados para revisão humana.");
