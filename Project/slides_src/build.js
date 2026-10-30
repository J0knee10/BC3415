// Builds Smishing_Triage_Slides.pptx: one slide per beat of Project/VIDEO_SCRIPT.md,
// with the spoken lines as speaker notes. The demo slide is left blank on purpose.
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("C:/Users/Jonathan Low/.claude/skills/synced/08835238-e1d8-479f-8280-11dd30317213_753854fc-ad7e-43d7-998f-4b71d65cd2c0/pptx/scripts/apply_theme.js");

const OUT = process.argv[2] || "Smishing_Triage_Slides.pptx";

const THEME = {
  name: "Smishing Triage",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14202E", lt1: "FFFFFF", dk2: "4A5361", lt2: "F2F4F7",
    accent1: "B8501F", accent2: "2B6CB0", accent3: "5E6673",
    accent4: "F08A4B", accent5: "7FB2E5", accent6: "B9C4CF",
    hlink: "2B6CB0", folHlink: "5E6673",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "Smishing Triage";
pres.author = "Jonathan Low";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const S = pres.shapes;
const HEAD = "+mj-lt"; // theme heading font, for big numbers
const MONO = "Consolas";
const DIVIDER = "D5DAE1";
const DARK_CARD = "22324A";
const HIGHLIGHT = "DCE7F3";

// --- Layouts -------------------------------------------------------------
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: 0.8, y: 0.7, w: 11.7, h: 0.4, fontSize: 14, bold: true, color: C.accent4, charSpacing: 3, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.3, w: 11.7, h: 1.4, align: "left", fontSize: 66, bold: true, color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.85, w: 11.7, h: 0.8, fontSize: 26, color: C.accent6, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: 0.6, y: 0.45, w: 12.1, h: 0.35, fontSize: 13, bold: true, color: C.accent1, charSpacing: 2, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.8, w: 12.1, h: 0.8, align: "left", fontSize: 34, bold: true, color: C.text1, valign: "top", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "source", type: "body", x: 0.6, y: 6.95, w: 11.2, h: 0.3, fontSize: 11, color: C.accent3, valign: "top", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.23, y: 6.95, w: 0.5, h: 0.3, fontSize: 11, color: C.accent3, align: "right" },
});
pres.defineSlideMaster({
  title: "STATEMENT",
  background: { color: C.accent1 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: 0.8, y: 0.7, w: 11.7, h: 0.4, fontSize: 14, bold: true, color: C.background1, charSpacing: 3, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.4, w: 11.7, h: 1.2, align: "left", fontSize: 54, bold: true, color: C.background1, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({ title: "BLANK_DARK", background: { color: C.text1 }, objects: [] });

// --- Helpers -------------------------------------------------------------
function box(slide, name, x, y, w, h, fill) {
  slide.addShape(S.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { type: "none" }, rectRadius: 0.12, objectName: name });
}
function text(slide, name, t, opts) {
  slide.addText(t, Object.assign({ margin: 0, isTextBox: true, valign: "top", objectName: name }, opts));
}
function content(section, eyebrow, title, source) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(eyebrow, { placeholder: "eyebrow" });
  s.addText(title, { placeholder: "title" });
  if (source) s.addText(source, { placeholder: "source" });
  return s;
}

// --- 1. The problem --------------------------------------------------------
const SEC1 = "1 · The problem";
pres.addSection({ title: SEC1 });

{
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: SEC1 });
  s.addText("BC3415 · INDIVIDUAL ASSIGNMENT", { placeholder: "eyebrow" });
  s.addText("Smishing Triage", { placeholder: "title" });
  s.addText("A scam checker for a Singapore bank’s customers", { placeholder: "body" });
  text(s, "Name", "Jonathan Low", { x: 0.8, y: 6.2, w: 4, h: 0.45, fontSize: 20, color: C.background1, valign: "middle" });
  const pills = [["No scam signals", C.accent5], ["Marketing spam", C.accent6], ["Likely scam", C.accent4]];
  let px = 6.55;
  const widths = [2.2, 2.1, 1.75];
  pills.forEach(([label, color], i) => {
    s.addShape(S.ROUNDED_RECTANGLE, { x: px, y: 6.2, w: widths[i], h: 0.45, fill: { color: DARK_CARD }, line: { type: "none" }, rectRadius: 0.22, objectName: `Pill ${label}` });
    text(s, `Pill text ${label}`, label, { x: px, y: 6.2, w: widths[i], h: 0.45, fontSize: 15, bold: true, color, align: "center", valign: "middle" });
    px += widths[i] + 0.15;
  });
  s.addNotes(`[0:00] "Hi, I'm Jonathan. This is Smishing Triage, a scam checker for a Singapore bank's customers."`);
}

{
  const s = content(SEC1, "1 · THE PROBLEM", "Scams in Singapore, 2025", "Source: Singapore Police Force, Annual Scam and Cybercrime Brief 2025");
  const stats = [
    ["S$913m", "lost to scams last year", C.accent1],
    ["S$24,500", "average loss per case (37,308 cases)", C.text1],
    ["9,000+", "cases began on WhatsApp or Telegram", C.text1],
  ];
  const w = 3.777;
  stats.forEach(([num, label, color], i) => {
    const x = 0.6 + i * (w + 0.4);
    box(s, `Stat card ${i + 1}`, x, 2.4, w, 2.8, C.background2);
    text(s, `Stat ${i + 1}`, num, { x: x + 0.4, y: 2.8, w: w - 0.8, h: 1.0, fontSize: 48, bold: true, fontFace: HEAD, color });
    text(s, `Stat label ${i + 1}`, label, { x: x + 0.4, y: 3.95, w: w - 0.8, h: 1.1, fontSize: 20, color: C.text2 });
  });
  s.addNotes(`"Scams cost Singapore 913 million dollars last year, about 24,500 dollars a case, and over 9,000 cases began on WhatsApp or Telegram."`);
}

{
  const s = content(SEC1, "1 · THE PROBLEM", "Why a bank would pay for this",
    "Source: MAS and IMDA, Guidelines on Shared Responsibility Framework, effective 16 December 2024, paragraphs 6.2–6.7.");
  text(s, "Subtitle", "The Shared Responsibility Framework decides who bears a phishing loss, in this order:", { x: 0.6, y: 1.6, w: 12.1, h: 0.45, fontSize: 18, color: C.text2 });
  const tiers = [
    ["The bank", "if it breached one of its anti-phishing duties", C.accent1],
    ["The telco", "next, for scams sent by SMS", C.accent3],
    ["The customer", "otherwise", C.text1],
  ];
  const w = 3.543;
  tiers.forEach(([head, body, color], i) => {
    const x = 0.6 + i * (w + 0.75);
    box(s, `Tier card ${i + 1}`, x, 2.3, w, 2.8, C.background2);
    s.addShape(S.OVAL, { x: x + 0.4, y: 2.7, w: 0.6, h: 0.6, fill: { color }, line: { type: "none" }, objectName: `Tier number ${i + 1}` });
    text(s, `Tier number text ${i + 1}`, String(i + 1), { x: x + 0.4, y: 2.7, w: 0.6, h: 0.6, fontSize: 20, bold: true, color: C.background1, align: "center", valign: "middle" });
    text(s, `Tier head ${i + 1}`, head, { x: x + 0.4, y: 3.5, w: w - 0.8, h: 0.5, fontSize: 24, bold: true, color: C.text1 });
    text(s, `Tier body ${i + 1}`, body, { x: x + 0.4, y: 4.05, w: w - 0.8, h: 0.85, fontSize: 17, color: C.text2 });
    if (i < 2) s.addShape(S.RIGHT_ARROW, { x: x + w + 0.15, y: 3.47, w: 0.45, h: 0.36, fill: { color: C.accent3 }, line: { type: "none" }, objectName: `Tier arrow ${i + 1}` });
  });
  box(s, "Liability callout", 0.6, 5.4, 12.13, 1.2, C.text1);
  text(s, "Liability callout text", [
    { text: "The checker doesn’t move that liability. ", options: { bold: true, color: C.accent4 } },
    { text: "But fewer customers phished means less exposure and fewer disputes.", options: { color: C.background1 } },
  ], { x: 0.95, y: 5.4, w: 11.5, h: 1.2, fontSize: 22, valign: "middle" });
  s.addNotes(`"Why would a bank pay for this? Since December 2024, under MAS's Shared Responsibility Framework, a phishing loss falls on the bank if it breached one of its anti-phishing duties, then on the telco for SMS scams, and otherwise on the customer. The checker doesn't move that liability, but fewer customers phished means less exposure and fewer disputes."`);
}

{
  const s = content(SEC1, "1 · THE PROBLEM", "Three classes, judged on scams caught");
  text(s, "Subtitle", "A two-class spam filter puts marketing and phishing in the same bin.", { x: 0.6, y: 1.6, w: 12.1, h: 0.45, fontSize: 18, color: C.text2 });
  const classes = [
    ["Legitimate", "Ordinary messages", C.accent2],
    ["Marketing spam", "Wastes three seconds", C.accent3],
    ["Smishing", "Phishing by text: can empty an account", C.accent1],
  ];
  const w = 3.777;
  classes.forEach(([name, desc, color], i) => {
    const x = 0.6 + i * (w + 0.4);
    box(s, `Class card ${i + 1}`, x, 2.4, w, 2.75, C.background2);
    s.addShape(S.OVAL, { x: x + 0.4, y: 2.8, w: 0.55, h: 0.55, fill: { color }, line: { type: "none" }, objectName: `Class dot ${i + 1}` });
    text(s, `Class name ${i + 1}`, name, { x: x + 0.4, y: 3.55, w: w - 0.8, h: 0.55, fontSize: 28, bold: true, color });
    text(s, `Class description ${i + 1}`, desc, { x: x + 0.4, y: 4.15, w: w - 0.8, h: 0.85, fontSize: 20, color: C.text1 });
  });
  box(s, "Metric callout", 0.6, 5.55, 12.13, 0.95, C.text1);
  text(s, "Metric callout text", [
    { text: "Headline metric: ", options: { color: C.background1 } },
    { text: "share of scams caught", options: { color: C.accent4, bold: true } },
    { text: ", not accuracy", options: { color: C.background1 } },
  ], { x: 0.95, y: 5.55, w: 11.5, h: 0.95, fontSize: 24, valign: "middle" });
  s.addNotes(`"A spam filter lumps marketing in with phishing, but one wastes three seconds and the other can empty an account. So there are three classes: legitimate, marketing spam, and smishing, which is phishing by text. The model is judged on scams caught, not accuracy."`);
}

{
  const s = content(SEC1, "1 · THE PROBLEM", "It follows the brief’s pattern");
  const steps = [
    ["Text verdict", "Legitimate, spam or scam"],
    ["Image channel", "Forward a screenshot instead"],
    ["Second stage", "Names the problem: the scam type"],
  ];
  const w = 3.543;
  steps.forEach(([head, body], i) => {
    const x = 0.6 + i * (w + 0.75);
    box(s, `Step card ${i + 1}`, x, 2.4, w, 3.0, C.background2);
    s.addShape(S.OVAL, { x: x + 0.4, y: 2.8, w: 0.6, h: 0.6, fill: { color: C.accent1 }, line: { type: "none" }, objectName: `Step number ${i + 1}` });
    text(s, `Step number text ${i + 1}`, String(i + 1), { x: x + 0.4, y: 2.8, w: 0.6, h: 0.6, fontSize: 20, bold: true, color: C.background1, align: "center", valign: "middle" });
    text(s, `Step head ${i + 1}`, head, { x: x + 0.4, y: 3.65, w: w - 0.8, h: 0.5, fontSize: 24, bold: true, color: C.text1 });
    text(s, `Step body ${i + 1}`, body, { x: x + 0.4, y: 4.25, w: w - 0.8, h: 1.0, fontSize: 17, color: C.text2 });
    if (i < 2) s.addShape(S.RIGHT_ARROW, { x: x + w + 0.15, y: 3.72, w: 0.45, h: 0.36, fill: { color: C.accent3 }, line: { type: "none" }, objectName: `Step arrow ${i + 1}` });
  });
  s.addNotes(`[ends 0:55] "It follows the brief's pattern: a text verdict, an image channel, and a second stage that names the problem."`);
}

// --- 2. Demo (blank: the screen recording goes over this slide) ---------
const SEC2 = "2 · Live demo";
pres.addSection({ title: SEC2 });
{
  const s = pres.addSlide({ masterName: "BLANK_DARK", sectionTitle: SEC2 });
  s.addNotes([
    "[0:55-2:10] LIVE DEMO - blank on purpose. Place the screen recording over this slide.",
    "Telegram: https://t.me/bc3415_smishing_bot",
    "",
    "1. Paste: Your DBS account is suspended. Verify at http://dbs-secure.co/login",
    "Expect: Likely scam (98%), then the Gemini scam type.",
    "\"A fake DBS link. It's called a likely scam at 98%, and it shows the words that triggered that, so the customer learns what to look for next time. Below that, an LLM names the scam type: bank impersonation.\"",
    "",
    "2. Paste: WIN a FREE iPhone! Txt WIN to 85233 now. T and Cs apply",
    "Expect: Marketing / spam (99%).",
    "\"Marketing spam. Annoying, but not an alarm.\"",
    "",
    "3. Paste: Eh you reaching already? I order first ah",
    "Expect: No scam signals found (96%).",
    "\"A normal message. It never says 'safe', only 'no scam signals found'. A false all-clear is worse than no answer.\"",
    "",
    "4. Paste: Hi mum this is my new number, my phone broke. Can you PayNow me $500 urgently",
    "Expect: No scam signals found (95%), with 'a person should check it'.",
    "\"The hard case: a scam with no link. The model thinks it's legitimate, but there's a question mark. A person should check it. More on that in a moment.\"",
    "",
    "5. Drag in Indiv/reports/mock_screenshot.png. Expect: Likely scam (88%).",
    "\"Screenshots work too. OCR reads the text, and then the same model judges it.\"",
  ].join("\n"));
}

// --- 3. Where the human is -------------------------------------------------
const SEC3 = "3 · Human review";
pres.addSection({ title: SEC3 });

{
  const s = content(SEC3, "3 · WHERE THE HUMAN IS", "The review line is set by cost",
    "S$67 ≈ S$24,500 average loss × about 1 in 370 missed scams becoming a loss. config.yaml: review cost 0.5 against 20 for a missed scam.");
  text(s, "Subtitle", "Not a flat “below 60% confidence” rule: mistakes don’t cost the same.", { x: 0.6, y: 1.6, w: 12.1, h: 0.45, fontSize: 18, color: C.text2 });
  const w = 3.577, y = 2.75, h = 2.75;
  const cards = [
    ["S$1.67", "a two-minute analyst review", C.background2, C.text1, C.text2],
    ["S$67", "expected loss from a missed scam", C.background2, C.text1, C.text2],
    ["2.5%", "scam chance that sends a “no scam signals” reply to a person", C.accent2, C.background1, C.background1],
  ];
  cards.forEach(([num, label, fill, numColor, labelColor], i) => {
    const x = 0.6 + i * (w + 0.7);
    box(s, `Cost card ${i + 1}`, x, y, w, h, fill);
    text(s, `Cost number ${i + 1}`, num, { x: x + 0.4, y: y + 0.4, w: w - 0.8, h: 0.9, fontSize: 48, bold: true, fontFace: HEAD, color: numColor });
    text(s, `Cost label ${i + 1}`, label, { x: x + 0.4, y: y + 1.4, w: w - 0.8, h: 0.85, fontSize: 18, color: labelColor });
  });
  [["÷", 0], ["=", 1]].forEach(([op, i]) => {
    text(s, `Operator ${op}`, op, { x: 0.6 + w + i * (w + 0.7), y, w: 0.7, h, fontSize: 40, bold: true, color: C.accent3, align: "center", valign: "middle" });
  });
  s.addNotes(`[2:10] "So where's the human? Not at a flat 'below 60% confidence' rule, because mistakes don't cost the same. A two-minute analyst review costs about S$1.67. A missed scam costs about S$67 in expected loss.\n\nSo when the bot would say 'no scam signals', a scam chance above 2.5% sends it to a person."`);
}

{
  const s = content(SEC3, "3 · WHERE THE HUMAN IS", "10% reviewed, including every missed scam",
    "Source: reports/human_review.csv (test set); review costs 0.14 / 0.5 / 1.0 / 2.0 against 20 for a missed scam, with a review fixed at S$1.67.");
  text(s, "Hard case label", "THE HARD CASE", { x: 0.6, y: 1.95, w: 5.6, h: 0.35, fontSize: 13, bold: true, color: C.accent1, charSpacing: 2 });
  box(s, "Message bubble", 0.6, 2.4, 5.6, 1.25, C.background2);
  text(s, "Message text", "Hi mum this is my new number, my phone broke. Can you PayNow me $500 urgently",
    { x: 0.85, y: 2.4, w: 5.1, h: 1.25, fontSize: 16, fontFace: MONO, color: C.text1, valign: "middle" });
  box(s, "Reply bubble", 0.6, 3.85, 5.6, 1.1, C.text1);
  text(s, "Reply text", [
    { text: "❔ No scam signals found (95%)", options: { bold: true, color: C.background1, breakLine: true } },
    { text: "🔎 A person should check it.", options: { color: C.accent6 } },
  ], { x: 0.85, y: 3.85, w: 5.1, h: 1.1, fontSize: 17, valign: "middle" });
  text(s, "Hard case result", [
    { text: "Scam chance " }, { text: "4%", options: { bold: true } },
    { text: ", above the 2.5% line, so it goes to " }, { text: "review", options: { bold: true, color: C.accent2 } },
  ], { x: 0.6, y: 5.2, w: 5.6, h: 0.8, fontSize: 18, color: C.text1 });

  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 } } });
  const row = (cells, used) => cells.map((t) => ({ text: t, options: used ? { bold: true, fill: { color: HIGHLIGHT } } : {} }));
  s.addTable([
    [hdr("If a missed scam costs"), hdr("Messages reviewed"), hdr("Missed scams reviewed")],
    row(["about S$240", "42.7%", "26 of 26"]),
    row(["S$67 (used)", "10.0%", "26 of 26"], true),
    row(["about S$33", "5.2%", "25 of 26"]),
    row(["about S$17", "4.0%", "22 of 26"]),
  ], { x: 6.7, y: 2.4, w: 6.03, colW: [1.8, 2.1, 2.13], rowH: 0.5, fontSize: 16, color: C.text1, valign: "middle", border: { type: "solid", pt: 0.75, color: DIVIDER }, margin: 0.1, objectName: "Review cost table" });
  text(s, "Table caption", "The S$67 is the least certain number, so every alternative is shown.",
    { x: 6.7, y: 5.2, w: 6.03, h: 0.8, fontSize: 15, color: C.text2 });
  s.addNotes(`"'Hi mum' had a 4% scam chance, so it goes to review.\n\nOn the test set that's 10% of messages, including every scam the model missed. The S$67 is my least certain number, so the table shows every alternative."`);
}

// --- 4. Two steps ----------------------------------------------------------
const SEC4 = "4 · Two steps";
pres.addSection({ title: SEC4 });

{
  const s = content(SEC4, "4 · TWO STEPS", "A trained model first, the LLM second",
    "50,000 checks a year (writeup section 1). Measured 24 Oct: 123 input + 78 output tokens per Gemini call, at US$0.30 / US$2.50 per million tokens.");
  box(s, "Classifier card", 0.6, 2.0, 4.6, 2.0, C.background2);
  text(s, "Classifier label", "1 · EVERY CHECK", { x: 0.95, y: 2.3, w: 4.0, h: 0.35, fontSize: 13, bold: true, color: C.accent2, charSpacing: 2 });
  text(s, "Classifier head", "Trained classifier", { x: 0.95, y: 2.75, w: 4.0, h: 0.5, fontSize: 26, bold: true, color: C.text1 });

  s.addShape(S.RIGHT_ARROW, { x: 5.75, y: 2.72, w: 1.8, h: 0.55, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Gate arrow" });
  text(s, "Gate label", "only if flagged as a scam", { x: 5.4, y: 3.4, w: 2.5, h: 0.5, fontSize: 15, color: C.text2, align: "center" });

  box(s, "LLM card", 8.1, 2.0, 4.63, 2.0, C.text1);
  text(s, "LLM label", "2 · ABOUT 1 IN 4 CHECKS", { x: 8.45, y: 2.3, w: 4.0, h: 0.35, fontSize: 13, bold: true, color: C.accent4, charSpacing: 2 });
  text(s, "LLM head", "The LLM (Gemini)", { x: 8.45, y: 2.75, w: 4.0, h: 0.5, fontSize: 26, bold: true, color: C.background1 });

  box(s, "Token card", 0.6, 4.4, 12.13, 2.15, C.background2);
  text(s, "Token label", "TOKEN BILL, 50,000 CHECKS A YEAR (APPROXIMATE)", { x: 0.95, y: 4.7, w: 8, h: 0.35, fontSize: 13, bold: true, color: C.accent1, charSpacing: 2 });
  text(s, "Token numbers", [
    { text: "US$12", options: { color: C.accent3 } },
    { text: "  →  ", options: { color: C.accent3 } },
    { text: "US$3", options: { color: C.text1 } },
  ], { x: 0.95, y: 5.15, w: 7.5, h: 1.0, fontSize: 44, bold: true, fontFace: HEAD, valign: "middle" });
  text(s, "Token note", "Trivial either way.", { x: 8.45, y: 5.15, w: 4.0, h: 1.0, fontSize: 24, italic: true, color: C.text2, valign: "middle" });
  s.addNotes(`[2:50] "Why a trained model first, and the LLM second? It saves tokens: only about a quarter of checks reach the LLM, so the bill drops from about 12 US dollars a year to 3. Trivial either way."`);
}

{
  const s = content(SEC4, "4 · TWO STEPS", "The real savings are elsewhere",
    "Timings measured 24 Oct: predict() with LIME 0.01–0.16 s; one Gemini call 6–8 s.");
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 } } });
  const row = (label, a, b) => [{ text: label, options: { bold: true } }, { text: a, options: { color: C.text2 } }, { text: b, options: { bold: true } }];
  s.addTable([
    [hdr(""), hdr("LLM on every check"), hdr("Model first")],
    row("Speed", "6–8 seconds", "about a fifth of a second"),
    row("Privacy", "every message goes to an AI provider", "unflagged messages never do"),
    row("Review rule", "no probability to price", "a probability it can price"),
  ], { x: 0.6, y: 1.95, w: 12.13, colW: [2.6, 4.6, 4.93], rowH: 0.78, fontSize: 20, color: C.text1, valign: "middle", border: { type: "solid", pt: 0.75, color: DIVIDER }, margin: 0.12, objectName: "Gate savings table" });
  box(s, "Funding callout", 0.6, 5.45, 12.13, 0.95, C.text1);
  text(s, "Funding callout text", [
    { text: "Not a funding question: ", options: { bold: true, color: C.accent4 } },
    { text: "if an LLM beats this model on local data, it can sit behind the same ", options: { color: C.background1 } },
    { text: "predict()", options: { color: C.background1, fontFace: MONO } },
    { text: ".", options: { color: C.background1 } },
  ], { x: 0.95, y: 5.45, w: 11.5, h: 0.95, fontSize: 20, valign: "middle" });
  s.addNotes(`"The real savings are elsewhere. Speed: a fifth of a second, not 6 to 8. Privacy: unflagged messages never go to an AI provider. And a probability I can price for the review rule, which an LLM doesn't give me.\n\nIt isn't a funding question. If an LLM beats this model on local data, it can sit behind the same predict()."`);
}

// --- 5. Why the numbers are honest -----------------------------------------
const SEC5 = "5 · Honest numbers";
pres.addSection({ title: SEC5 });

{
  const s = content(SEC5, "5 · WHY THE NUMBERS ARE HONEST", "My first version claimed 95%");
  const chipColor = { A: C.accent1, B: C.accent2, C: C.text1, D: C.accent3 };
  const panels = [
    ["BEFORE", C.accent1, "Scam campaigns send near-identical copies. Some test messages had copies in training.", "AABC", "ABD"],
    ["NOW", C.accent2, "Near-copies are grouped into clusters, and each cluster stays on one side of the split.", "AAABB", "CDD"],
  ];
  const w = 5.9;
  panels.forEach(([label, color, body, train, test], i) => {
    const x = 0.6 + i * (w + 0.33);
    box(s, `${label} panel`, x, 1.95, w, 3.95, C.background2);
    text(s, `${label} label`, label, { x: x + 0.4, y: 2.25, w: w - 0.8, h: 0.35, fontSize: 13, bold: true, color, charSpacing: 2 });
    text(s, `${label} body`, body, { x: x + 0.4, y: 2.65, w: w - 0.8, h: 0.95, fontSize: 18, color: C.text1 });
    [["Train", train, 3.85], ["Test", test, 4.85]].forEach(([name, chips, y]) => {
      text(s, `${label} ${name} label`, name, { x: x + 0.4, y, w: 0.9, h: 0.6, fontSize: 17, color: C.text2, valign: "middle" });
      chips.split("").forEach((c, j) => {
        const cx = x + 1.4 + j * 0.75;
        s.addShape(S.ROUNDED_RECTANGLE, { x: cx, y, w: 0.6, h: 0.6, fill: { color: chipColor[c] }, line: { type: "none" }, rectRadius: 0.08, objectName: `${label} ${name} chip ${j + 1}` });
        text(s, `${label} ${name} chip text ${j + 1}`, c, { x: cx, y, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle" });
      });
    });
  });
  text(s, "Chip caption", "Each letter is one scam campaign. The same letter in training and test means the model has already seen the answer.",
    { x: 0.6, y: 6.1, w: 12.1, h: 0.5, fontSize: 16, color: C.text2 });
  s.addNotes(`[3:30] "How do I know these numbers are honest? My first version claimed 95%. But scam campaigns send near-identical copies, and my test set had copies of the training data. Now near-copies are grouped and kept on one side of the split."`);
}

{
  const s = content(SEC5, "5 · WHY THE NUMBERS ARE HONEST", "The honest result", "Source: reports/test_result.json; reports/sg_scams_predictions.csv for the Singapore sets.");
  text(s, "Headline recall", "76%", { x: 0.6, y: 2.2, w: 4.6, h: 1.7, fontSize: 110, bold: true, fontFace: HEAD, color: C.accent1 });
  text(s, "Headline caption", "of test scams caught (83 of 109)", { x: 0.6, y: 4.0, w: 4.6, h: 0.9, fontSize: 22, color: C.text1 });
  const rows = [
    ["56–89%", "95% interval: wide, because there are only 43 distinct campaigns"],
    ["0.2%", "of Singaporeans’ personal chats wrongly flagged (18 of 8,547)"],
    ["1 command", "rebuilds the model and its test figures from one config file"],
    ["19 tests", "check it, including that the LLM gate holds"],
  ];
  rows.forEach(([num, cap], i) => {
    const y = 1.95 + i * 1.15;
    if (i > 0) s.addShape(S.LINE, { x: 5.8, y: y - 0.075, w: 6.93, h: 0, line: { color: DIVIDER, width: 1 }, objectName: `Row divider ${i}` });
    text(s, `Result ${i + 1}`, num, { x: 5.8, y, w: 2.3, h: 1.0, fontSize: 30, bold: true, fontFace: HEAD, color: C.text1, valign: "middle" });
    text(s, `Result caption ${i + 1}`, cap, { x: 8.2, y, w: 4.53, h: 1.0, fontSize: 17, color: C.text2, valign: "middle" });
  });
  s.addNotes(`"The honest result is 76% of scams caught. The interval is wide, 56 to 89%, because there are only 43 distinct campaigns. 0.2% of Singaporeans' personal chats are wrongly flagged. The model and its test figures rebuild from one config file and one command. 19 tests check it, including that the LLM gate holds."`);
}

// --- 6. Recommendation -----------------------------------------------------
const SEC6 = "6 · Recommendation";
pres.addSection({ title: SEC6 });

{
  const s = pres.addSlide({ masterName: "STATEMENT", sectionTitle: SEC6 });
  s.addText("6 · RECOMMENDATION", { placeholder: "eyebrow" });
  s.addText("Not ready for customers", { placeholder: "title" });
  const stats = [
    ["60%", "of real local scams caught (36 of 60)"],
    ["5 of 5", "genuine bank and SingPost notices flagged as scams: a no-go on its own"],
  ];
  stats.forEach(([num, cap], i) => {
    const x = 0.8 + i * 6.1;
    text(s, `Verdict stat ${i + 1}`, num, { x, y: 3.1, w: 5.6, h: 1.2, fontSize: 66, bold: true, fontFace: HEAD, color: C.background1 });
    text(s, `Verdict caption ${i + 1}`, cap, { x, y: 4.35, w: 5.4, h: 1.0, fontSize: 22, color: C.background1 });
  });
  text(s, "Root cause", "Both problems come from foreign training data.", { x: 0.8, y: 6.0, w: 11.7, h: 0.6, fontSize: 24, italic: true, color: C.background1 });
  s.addNotes(`[4:10] "My recommendation is that it's not ready for customers. It catches 60% of real local scams. It also flagged all 5 genuine bank and SingPost notices it saw, and that alone is a no-go. Both problems come from foreign training data."`);
}

{
  const s = content(SEC6, "6 · RECOMMENDATION", "The ask: a three-month pilot, about S$9,000", "Pilot costs are estimates at S$50 per analyst-hour (writeup section 1).");
  [["S$5,000", "to label local messages"], ["S$4,000", "of staff time to run the trial"]].forEach(([num, cap], i) => {
    const x = 0.6 + i * 6.165;
    box(s, `Pilot cost card ${i + 1}`, x, 1.95, 5.965, 2.2, C.background2);
    text(s, `Pilot cost ${i + 1}`, num, { x: x + 0.4, y: 2.3, w: 5.1, h: 0.85, fontSize: 44, bold: true, fontFace: HEAD, color: C.text1 });
    text(s, `Pilot cost caption ${i + 1}`, cap, { x: x + 0.4, y: 3.2, w: 5.1, h: 0.6, fontSize: 20, color: C.text2 });
  });
  const cards = [
    ["PASS ONLY IF", "≥ 80%", "of local scams caught", C.background2, C.accent2, C.text1, C.text2],
    ["PASS ONLY IF", "≤ 1%", "of the bank’s real alerts flagged", C.background2, C.accent2, C.text1, C.text2],
    ["RUNNING COST", "S$10–14k", "a year of review time: people, not tokens", C.text1, C.accent4, C.background1, C.accent6],
  ];
  const w = 3.777;
  cards.forEach(([label, num, cap, fill, labelColor, numColor, capColor], i) => {
    const x = 0.6 + i * (w + 0.4);
    box(s, `Criterion card ${i + 1}`, x, 4.6, w, 2.1, fill);
    text(s, `Criterion label ${i + 1}`, label, { x: x + 0.4, y: 4.8, w: w - 0.8, h: 0.35, fontSize: 13, bold: true, color: labelColor, charSpacing: 2 });
    text(s, `Criterion number ${i + 1}`, num, { x: x + 0.4, y: 5.15, w: w - 0.8, h: 0.75, fontSize: 36, bold: true, fontFace: HEAD, color: numColor });
    text(s, `Criterion caption ${i + 1}`, cap, { x: x + 0.4, y: 5.95, w: w - 0.8, h: 0.7, fontSize: 16, color: capColor });
  });
  s.addNotes(`"So the ask is a three-month pilot, about S$9,000: 5,000 to label local messages, and 4,000 of staff time to run the trial. It passes only if it catches 80% of local scams and flags at most 1% of the bank's real alerts. The running cost is people, not tokens: about S$10,000 to 14,000 a year of review time. Thank you."`);
}

{
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: SEC6 });
  s.addText("SMISHING TRIAGE", { placeholder: "eyebrow" });
  s.addText("Thank you", { placeholder: "title" });
  s.addText("Try it: t.me/bc3415_smishing_bot", { placeholder: "body" });
  s.addNotes(`[ends about 4:50] "Thank you." (Hold this slide for a second or two at the end.)`);
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
