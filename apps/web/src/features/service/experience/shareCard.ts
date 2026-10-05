import {
  getDokkaebiAssetUrl,
  type DokkaebiExpression,
} from "../../character/dokkaebiCatalog";

export type ReadingShareContent = {
  topic: string;
  title: string;
  takeaway: string;
  periodLabel?: string;
  limitation?: string;
};

function wrapText(
  context: CanvasRenderingContext2D,
  text: string,
  width: number,
): string[] {
  const lines: string[] = [];
  for (const paragraph of text.split("\n")) {
    let line = "";
    // Keep Korean words together too. Only an overlong unbroken token wraps by character.
    const tokens = paragraph
      .split(/(\s+)/u)
      .flatMap((token) =>
        context.measureText(token).width > width ? Array.from(token) : [token],
      );
    for (const token of tokens) {
      const next = line + token;
      if (line && context.measureText(next).width > width) {
        lines.push(line.trim());
        line = token.trimStart();
      } else line = next;
    }
    lines.push(line.trim());
  }
  return lines;
}

function drawFittedText(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  width: number,
  height: number,
  maxFont: number,
  minFont: number,
  weight: number,
) {
  let fontSize = maxFont;
  let lines: string[] = [];
  while (fontSize >= minFont) {
    context.font = `${weight} ${fontSize}px "Noto Sans KR", "Malgun Gothic", sans-serif`;
    lines = wrapText(context, text, width);
    if (lines.length * fontSize * 1.45 <= height || fontSize === minFont) break;
    fontSize -= 2;
  }
  // Very long provider text gets an explicit ellipsis; the full reading stays on screen.
  const visibleLines = Math.max(1, Math.floor(height / (fontSize * 1.45)));
  if (lines.length > visibleLines) {
    lines = lines.slice(0, visibleLines);
    let last = lines[visibleLines - 1];
    while (last && context.measureText(`${last}…`).width > width)
      last = last.slice(0, -1);
    lines[visibleLines - 1] = `${last}…`;
  }
  lines.forEach((line, index) =>
    context.fillText(line, x, y + index * fontSize * 1.45),
  );
}

export async function createReadingShareCard(
  content: ReadingShareContent,
  expression: DokkaebiExpression,
): Promise<Blob> {
  const image = new Image();
  image.src = getDokkaebiAssetUrl(expression);
  await image.decode();
  await document.fonts.ready;
  const canvas = document.createElement("canvas");
  canvas.width = 1080;
  canvas.height = 1350;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.textBaseline = "top";
  ctx.fillStyle = "#f7f1e7";
  ctx.fillRect(0, 0, 1080, 1350);
  ctx.fillStyle = "#e5dbf4";
  ctx.fillRect(32, 32, 1016, 1286);
  ctx.fillStyle = "#312939";
  drawFittedText(
    ctx,
    `${content.topic}${content.periodLabel ? ` · ${content.periodLabel}` : ""}`,
    88,
    90,
    904,
    60,
    26,
    18,
    500,
  );
  ctx.fillStyle = "#c9543d";
  ctx.fillRect(88, 159, 64, 8);
  ctx.fillStyle = "#282330";
  drawFittedText(ctx, content.title, 88, 213, 904, 295, 66, 32, 800);
  ctx.drawImage(image, 370, 504, 340, 340);
  ctx.fillStyle = "#fbf8f2";
  ctx.fillRect(68, 855, 944, 340);
  ctx.fillStyle = "#302936";
  drawFittedText(ctx, content.takeaway, 106, 900, 868, 258, 36, 22, 500);
  if (content.limitation) {
    ctx.fillStyle = "#51485d";
    drawFittedText(ctx, content.limitation, 88, 1222, 904, 72, 24, 18, 500);
  }
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("PNG export failed"))),
      "image/png",
    ),
  );
}
