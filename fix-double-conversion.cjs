const fs = require("fs");
const p = "C:/Users/yangjili/.vscode/extensions/rooveterinaryinc.roo-cline-3.53.0/dist/extension.js";
let c = fs.readFileSync(p, "utf8");
console.log("File size:", c.length);

const old =
  'const t = convertToR1Format([{role:"user",content:e},...r],{mergeToolResultText:true});\nreturn xd(t);';
const neu =
  'return convertToR1Format([{role:"user",content:e},...r],{mergeToolResultText:true})';

if (c.includes(old)) {
  c = c.replace(old, neu);
  fs.writeFileSync(p, c, "utf8");
  const n = (c.match(/openAiR1FormatEnabled/g) || []).length;
  console.log("✓ Fixed! openAiR1FormatEnabled count:", n);
} else {
  console.log("Pattern not found. Searching for convertToR1Format...");
  const idx = c.indexOf("convertToR1Format");
  if (idx > -1) {
    console.log("Found at index:", idx);
    console.log("Context:", JSON.stringify(c.substring(idx - 10, idx + 180)));
  } else {
    console.log("convertToR1Format not found in file");
  }
}
