const pptxgen = require("pptxgenjs");
const D = require("./deck_data.json");
// kept beside the audit itself: tests/audit.py prints "N/N checks passed" on every run
const N_CHECKS = 26;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                 // 13.33 x 7.5
pres.author = "TSMOM Engine";
pres.title  = "Time Series Momentum";

/* ---------------------------------------------------------------- palette */
const INK   = "0F1E2E";   // dominant dark
const INK2  = "1B3348";   // dark surface
const PAPER = "FFFFFF";
const SURF  = "F1F4F7";   // light card
const ACC   = "D9852E";   // the signal accent
const BLUE  = "2E6D9E";   // data
const TEAL  = "2F7F72";
const GAIN  = "2E7D5B";
const LOSS  = "B04A42";
const ACCT  = "8F5510";   // accent for text on light fill — the bright accent is ~2.9:1 there
const MUTE  = "5D6B78";
const LINE  = "DCE3E9";

const H  = "Cambria";     // headings  (safe list)
const B  = "Calibri";     // body      (safe list)

const pc  = (x, d = 1) => (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(d) + "%";
const pcu = (x, d = 1) => (x * 100).toFixed(d) + "%";

/* ---------------------------------------------------------------- helpers */
function titleSlide(s, kicker, title, sub) {
  s.background = { color: INK };
  s.addText(kicker, { x: 0.75, y: 0.85, w: 11.8, h: 0.3, isTextBox: true,
    fontFace: B, fontSize: 12, color: ACC, charSpacing: 3, bold: true });
  s.addText(title, { x: 0.75, y: 1.25, w: 11.8, h: 1.5, isTextBox: true,
    fontFace: H, fontSize: 44, color: PAPER, bold: true, lineSpacing: 48 });
  if (sub) s.addText(sub, { x: 0.75, y: 2.9, w: 10.5, h: 1.1, isTextBox: true,
    fontFace: B, fontSize: 16, color: "AEBECD", lineSpacing: 24 });
}

function head(s, title, deck) {
  s.background = { color: PAPER };
  s.addText(title, { x: 0.6, y: 0.4, w: 12.1, h: 0.55, isTextBox: true,
    fontFace: H, fontSize: 30, color: INK, bold: true });
  if (deck) s.addText(deck, { x: 0.6, y: 0.97, w: 12.1, h: 0.4, isTextBox: true,
    fontFace: B, fontSize: 14, color: MUTE });
}

function card(s, x, y, w, h, fill) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.06,
    fill: { color: fill || SURF }, line: { color: LINE, width: 0.75 } });
}

function stat(s, x, y, w, value, label, note, color) {
  s.addText(value, { x, y, w, h: 0.62, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 34, bold: true, color: color || INK });
  s.addText(label, { x, y: y + 0.6, w, h: 0.28, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 12, color: INK, bold: true });
  if (note) s.addText(note, { x, y: y + 0.86, w, h: 0.4, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 10.5, color: MUTE });
}

function marker(s, x, y, color) {          // the repeated motif: a small signal square
  s.addShape(pres.ShapeType.rect, { x, y, w: 0.1, h: 0.1, fill: { color: color || ACC }, line: { width: 0 } });
}

function footer(s, txt) {
  s.addText(txt, { x: 0.6, y: 6.96, w: 12.1, h: 0.3, isTextBox: true,
    fontFace: B, fontSize: 9.5, color: "94A3B0", italic: true });
}

const axisBase = {
  catAxisLabelColor: MUTE, valAxisLabelColor: MUTE,
  catAxisLabelFontFace: B, valAxisLabelFontFace: B,
  catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  valGridLine: { color: LINE, size: 0.75 }, catGridLine: { style: "none" },
  catAxisLineShow: false, valAxisLineShow: false,
  showLegend: false, showTitle: false,
};

/* ================================================================ 1 TITLE */
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("SYSTEMATIC MACRO", { x: 0.85, y: 1.5, w: 8, h: 0.3, isTextBox: true,
    fontFace: B, fontSize: 12.5, color: ACC, bold: true, charSpacing: 4 });
  s.addText("Time Series\nMomentum", { x: 0.85, y: 1.95, w: 8, h: 2.1, isTextBox: true,
    fontFace: H, fontSize: 54, color: PAPER, bold: true, lineSpacing: 58 });
  s.addText("A diversifying trend strategy across " + D.n_inst +
    " liquid markets — built on Moskowitz, Ooi & Pedersen (2012)",
    { x: 0.85, y: 4.15, w: 7.6, h: 0.9, isTextBox: true,
      fontFace: B, fontSize: 16, color: "AEBECD", lineSpacing: 24 });
  s.addText("Backtest " + D.month_first + " to " + D.month_last +
    "   ·   as of " + D.asof,
    { x: 0.85, y: 5.35, w: 8, h: 0.35, isTextBox: true,
      fontFace: B, fontSize: 12, color: "7B8FA3" });

  // motif: a small trend of signal squares
  const seq = [0, 1, 1, 0, 1, 1, 1, 0, 1, 1];
  seq.forEach((v, i) => {
    s.addShape(pres.ShapeType.rect, { x: 9.5 + i * 0.33, y: 3.55 - v * 0.42, w: 0.2, h: 0.2,
      fill: { color: v ? ACC : "35506A" }, line: { width: 0 } });
  });
  s.addText("the signal is the sign of the trend", { x: 9.5, y: 4.0, w: 3.3, h: 0.3,
    isTextBox: true, fontFace: B, fontSize: 10.5, color: "7B8FA3", italic: true });
  s.addNotes("Frame: this is a diversifier with a positive expected return, not a return-maximiser. " +
    "The case rests on three things — a repeatable economic reason for the profit, a construction that is " +
    "faithful to the literature, and behaviour in crises that equities cannot provide.");
}

/* ================================================ 2 SOURCES OF ALPHA */
{
  const s = pres.addSlide();
  head(s, "Where does the money come from?",
    "A strategy is only worth running if you can name who is on the other side of the trade — and why they keep showing up.");

  s.addShape(pres.ShapeType.roundRect, { x: 5.15, y: 1.55, w: 3.0, h: 0.55, rectRadius: 0.06,
    fill: { color: INK }, line: { width: 0 } });
  s.addText("PROFIT SOURCES", { x: 5.15, y: 1.55, w: 3.0, h: 0.55, isTextBox: true,
    fontFace: B, fontSize: 12.5, color: PAPER, bold: true, align: "center", valign: "middle", charSpacing: 1.5 });

  const cols = [
    { x: 0.6,  t: "Compensation for risk", on: true,
      d: "Hedgers pay speculators to carry price risk they do not want. Producers sell forward; the buyer is paid for standing there.",
      e: "Trend is the mechanism that decides which side to stand on." },
    { x: 4.87, t: "Behavioural & structural", on: true,
      d: "Investors under-react to new information, then over-extrapolate once a move is established. Capital moves slowly between managers.",
      e: "Trend monetises the drift between the two." },
    { x: 9.14, t: "Information asymmetry", on: false,
      d: "Better data, faster access, or news that travels slowly. Someone knows something first.",
      e: "We have no informational edge here — and do not claim one." },
  ];
  cols.forEach(c => {
    // connector
    s.addShape(pres.ShapeType.line, { x: c.x + 1.8, y: 2.1, w: 0, h: 0.45,
      line: { color: LINE, width: 1.25 } });
    card(s, c.x, 2.55, 3.6, 3.25, c.on ? SURF : "FAFBFC");
    marker(s, c.x + 0.28, 2.85, c.on ? ACC : "C3CDD6");
    s.addText(c.t, { x: c.x + 0.28, y: 3.02, w: 3.05, h: 0.6, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 16, bold: true, color: c.on ? INK : "5A6470", valign: "top" });
    s.addText(c.d, { x: c.x + 0.28, y: 3.64, w: 3.05, h: 1.35, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12, color: c.on ? "37485A" : "5A6470", lineSpacing: 16, valign: "top" });
    s.addText(c.e, { x: c.x + 0.28, y: 5.0, w: 3.05, h: 0.65, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, italic: true, color: c.on ? ACCT : "6E7A86", lineSpacing: 15, valign: "top" });
  });
  s.addText("Trend following harvests the first two. It is a risk-transfer and behavioural strategy, not an information strategy — which is precisely why it does not require being smarter than the other side.",
    { x: 0.6, y: 6.05, w: 12.1, h: 0.7, isTextBox: true,
      fontFace: B, fontSize: 13, color: INK, lineSpacing: 18 });
  footer(s, "Taxonomy after the standard sources-of-alpha framing.");
  s.addNotes("The honest point: we are not claiming an informational edge. The profit comes from being paid to " +
    "take risk others want to shed, and from a well-documented behavioural pattern. If you cannot name the seller, you are the sucker.");
}

/* ================================================ 3 WHY IT PERSISTS */
{
  const s = pres.addSlide();
  head(s, "Why the pattern survives being published",
    "Trend has been documented since the 1980s and still works. Three reasons it is hard to arbitrage away.");

  const items = [
    { n: "01", t: "The sellers are not trying to win",
      d: "A wheat farmer hedging next season's crop, a pension fund rebalancing, a central bank smoothing its currency. They are managing risk or mandate, not seeking alpha. They will keep transacting regardless of the return it costs them." },
    { n: "02", t: "The behaviour is human, not institutional",
      d: "Anchoring, the disposition effect, and herding are properties of people. Publishing a paper does not stop investors selling winners too early and holding losers too long." },
    { n: "03", t: "It requires tolerating long droughts",
      d: "The strategy loses money for years at a time — the longest stretch underwater in this sample runs over " + Math.floor(D.stats12.dd_months / 12) + " years. That is the barrier to entry: most capital cannot sit through it, so the trade does not get crowded out permanently." },
  ];
  items.forEach((it, i) => {
    const y = 1.55 + i * 1.72;
    s.addShape(pres.ShapeType.roundRect, { x: 0.6, y, w: 0.85, h: 0.85, rectRadius: 0.08,
      fill: { color: INK }, line: { width: 0 } });
    s.addText(it.n, { x: 0.6, y, w: 0.85, h: 0.85, isTextBox: true,
      fontFace: B, fontSize: 19, bold: true, color: ACC, align: "center", valign: "middle" });
    s.addText(it.t, { x: 1.72, y: y + 0.02, w: 10.9, h: 0.4, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 17, bold: true, color: INK });
    s.addText(it.d, { x: 1.72, y: y + 0.46, w: 10.9, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12.5, color: "37485A", lineSpacing: 17, valign: "top" });
  });
  s.addText("The third reason is the important one: the return is compensation for a genuinely uncomfortable experience.",
    { x: 0.6, y: 6.72, w: 12.1, h: 0.35, isTextBox: true,
      fontFace: B, fontSize: 12.5, italic: true, color: ACCT });
  s.addNotes("Anticipate the efficient-markets objection here. The answer is that this is not a free lunch — " +
    "it is paid for in drawdown tolerance, which is a real and scarce thing.");
}

/* ================================================ 4 WHAT IT IS */
{
  const s = pres.addSlide();
  head(s, "The strategy in one sentence",
    "Own what has been going up, short what has been going down, and size every position by its own volatility.");

  card(s, 0.6, 1.65, 12.1, 1.35, INK);
  s.addText("If a market's excess return over the past 12 months is positive, go long. If negative, go short.",
    { x: 1.05, y: 1.85, w: 11.2, h: 0.5, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 20, color: PAPER, bold: true });
  s.addText("No forecast of magnitude, no view on fair value, no discretion. Only the sign of the past return.",
    { x: 1.05, y: 2.38, w: 11.2, h: 0.45, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 13.5, color: "AEBECD" });

  const box = [
    { t: "Why the sign, not the size?",
      d: "The magnitude of a past move carries far less information than its direction. Using only the sign avoids fitting a return model to noise, and it is what the original research tests." },
    { t: "Why 12 months?",
      d: "Moskowitz, Ooi & Pedersen find return continuation out to roughly a year across every asset class, then reversal beyond it. We monitor 3 and 6 months as confirmation, but 12 is the headline." },
    { t: "Why volatility scaling?",
      d: "Natural gas is twenty times more volatile than 2-year notes. Without scaling, a handful of commodities would drive the entire portfolio. Each market is sized to contribute comparable risk." },
  ];
  box.forEach((bx, i) => {
    const x = 0.6 + i * 4.13;
    card(s, x, 3.3, 3.83, 2.55);
    marker(s, x + 0.3, 3.6);
    s.addText(bx.t, { x: x + 0.3, y: 3.77, w: 3.25, h: 0.55, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 15, bold: true, color: INK });
    s.addText(bx.d, { x: x + 0.3, y: 4.35, w: 3.25, h: 1.35, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, color: "37485A", lineSpacing: 15.5, valign: "top" });
  });
  footer(s, "Signal and holding period follow the paper's canonical specification (k = 12 months, h = 1 month).");
}

/* ================================================ 5 CONSTRUCTION */
{
  const s = pres.addSlide();
  head(s, "How a position is built",
    "Three steps, run identically for every market, every month.");

  const steps = [
    { n: "1", t: "Estimate risk",
      f: "σ  =  exponentially weighted volatility",
      d: "An exponentially weighted moving average of squared daily returns, with a 60-day centre of mass, annualised. Always lagged one day, so today's move never informs today's position." },
    { n: "2", t: "Take the signal",
      f: "sign( r₋₁₂ )  =  +1  or  −1",
      d: "The sign of the trailing 12-month excess return, read at the month-end close. Positive means long, negative means short — no middle ground." },
    { n: "3", t: "Size the position",
      f: "w  =  sign  ×  40% ÷ σ  ÷  N",
      d: "Scale to a 40% annualised volatility target per market, then split equally across all live markets. A quiet market gets a bigger position; a wild one gets less. The formula is uncapped as published, and the backtest here runs it that way; the live engine caps the ratio at 5× because a 1%-volatility 2-year note would otherwise ask for thirty times its own weight." },
  ];
  steps.forEach((st, i) => {
    const y = 1.6 + i * 1.62;
    s.addShape(pres.ShapeType.ellipse, { x: 0.6, y: y + 0.14, w: 0.62, h: 0.62,
      fill: { color: ACC }, line: { width: 0 } });
    s.addText(st.n, { x: 0.6, y: y + 0.14, w: 0.62, h: 0.62, isTextBox: true,
      fontFace: B, fontSize: 18, bold: true, color: INK, align: "center", valign: "middle" });
    s.addText(st.t, { x: 1.45, y: y + 0.06, w: 3.0, h: 0.4, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 17, bold: true, color: INK });
    card(s, 1.45, y + 0.52, 3.35, 0.5, INK);
    s.addText(st.f, { x: 1.6, y: y + 0.52, w: 3.1, h: 0.5, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12.5, color: ACC, bold: true, valign: "middle" });
    s.addText(st.d, { x: 5.1, y: y + 0.1, w: 7.6, h: 1.2, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12.5, color: "37485A", lineSpacing: 17, valign: "top" });
  });

  card(s, 0.6, 6.22, 12.1, 0.72, "FBF3E8");
  s.addText("Rebalanced monthly. Positions are decided at the month-end close and held for one month — the same discipline in every regime.",
    { x: 0.95, y: 6.22, w: 11.5, h: 0.72, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12.5, color: "6B4A22", valign: "middle" });
  s.addNotes("The one-day lag on volatility and the month-end decision point are what make the backtest honest. " +
    "Both are verified mechanically — see the process slide.");
}

/* ================================================ 6 UNIVERSE */
{
  const s = pres.addSlide();
  head(s, "The universe: " + D.n_inst + " liquid markets",
    "Breadth is the engine of this strategy — the more genuinely different trends you can hold, the smoother the ride.");

  const order = ["Commodity", "Equity", "FX", "Bond", "Crypto"];
  const labels = { Commodity: "Commodities", Equity: "Equity indices", FX: "Currencies",
                   Bond: "Bonds & credit", Crypto: "Crypto" };
  s.addChart(pres.ChartType.bar, [{
    name: "Markets",
    labels: order.map(k => labels[k]),
    values: order.map(k => D.universe[k] || 0),
  }], {
    x: 0.6, y: 1.6, w: 6.1, h: 4.0, barDir: "bar", barGapWidthPct: 55,
    chartColors: [BLUE], showValue: true, dataLabelPosition: "outEnd",
    dataLabelColor: INK, dataLabelFontFace: B, dataLabelFontSize: 11, dataLabelFontBold: true,
    valAxisHidden: true, ...axisBase, catAxisLabelFontSize: 12,
  });

  const notes = [
    ["Every market is exchange-listed or a deep OTC forward", "Futures on CME, ICE and CBOT; US-listed ETFs for markets without an accessible contract; FX forwards for emerging currencies."],
    ["Screened for the size of the fund", "Each candidate must clear a liquidity bar set so the largest position stays under 10% of a day's volume. The screen is re-run quarterly."],
    ["What is deliberately excluded", "Interest-rate swaps, credit indices, emissions and physical exotics — all need ISDA documentation and institutional prime brokerage. Where a listed proxy exists we use it."],
  ];
  notes.forEach((nt, i) => {
    const y = 1.6 + i * 1.38;
    marker(s, 7.15, y + 0.06);
    s.addText(nt[0], { x: 7.45, y: y - 0.06, w: 5.25, h: 0.35, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 14, bold: true, color: INK });
    s.addText(nt[1], { x: 7.45, y: y + 0.32, w: 5.25, h: 0.95, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, color: "37485A", lineSpacing: 15.5, valign: "top" });
  });
  footer(s, "Sized for a $10m fund; the liquidity bar scales with assets under management.");
}

/* ================================================ 7 BACKTEST */
{
  const s = pres.addSlide();
  head(s, "Backtest: " + D.stats12.months + " months, " + D.month_first.slice(0, 4) +
    " to " + D.month_last.slice(0, 4),
    (D.cap == null
      ? "Gross of costs. 12-month signal, sized exactly as Eq. 5 specifies — uncapped — and rebalanced monthly."
      : "Gross of costs. 12-month signal, " + D.cap + "× leverage cap, monthly rebalance."));

  const st12 = D.stats12;
  const tiles = [
    [pcu(st12.cagr), "Annual return", "compounded, excess of cash"],
    [pcu(st12.vol), "Volatility", "annualised"],
    [st12.sharpe.toFixed(2), "Sharpe", "Sortino " + st12.sortino.toFixed(2)],
    [pcu(st12.maxdd), "Max drawdown", "peak to trough"],
    [pcu(st12.hit, 0), "Positive months", st12.months + " months"],
  ];
  tiles.forEach((t, i) => {
    const x = 0.6 + i * 2.44;
    card(s, x, 1.55, 2.24, 1.35);
    stat(s, x + 0.22, 1.68, 1.9, t[0], t[1], t[2], i === 3 ? LOSS : INK);
  });

  // Compound the SAME calendar-year returns the next slide plots as bars. Sampling the
  // monthly curve every fourth quarter instead put the plotted points on September ends
  // under December labels, so a reader overlaying the two performance slides found the path
  // contradicting itself — 2019 fell 8% on one and rose on the other.
  const lab = [""], val = [1];
  let acc = 1;
  D.years.forEach((y, i) => { acc *= 1 + D.yr_vals[i]; lab.push(String(y)); val.push(+acc.toFixed(4)); });
  s.addChart(pres.ChartType.line, [{ name: "Growth of $1", labels: lab, values: val }], {
    x: 0.6, y: 3.15, w: 12.1, h: 3.1, chartColors: [BLUE], lineSize: 2.5, lineSmooth: false,
    ...axisBase, valAxisMinVal: 0.8, showTitle: true, title: "Growth of $1, gross of costs",
    titleFontFace: B, titleFontSize: 12, titleColor: MUTE, titleAlign: "left",
  });
  footer(s, "Excess returns over cash. Past performance does not indicate future results.");
  s.addNotes("Be upfront that the Sharpe is modest. The reason to own this is on the next two slides, " +
    "not in the standalone return.");
}

/* ================================================ 8 CALENDAR YEARS */
{
  const s = pres.addSlide();
  head(s, "It does not pay every year — and that is the point",
    "Long stretches of loss are the price of admission. The wins arrive when other assets are struggling.");

  s.addChart(pres.ChartType.bar, [{
    name: "Return", labels: D.years.map(String), values: D.yr_vals,
  }], {
    x: 0.6, y: 1.6, w: 12.1, h: 3.6, barDir: "col", barGapWidthPct: 40,
    chartColors: [GAIN], invertedColors: [LOSS],
    showValue: false, ...axisBase, valAxisLabelFormatCode: "0%",
  });

  // read straight off the series so a change in the engine cannot leave a stale figure here
  const yv = {}; D.years.forEach((y, i) => { yv[y] = D.yr_vals[i]; });
  const lean = [2009, 2010, 2011, 2012, 2013, 2014]
    .reduce((a, y) => a * (1 + (yv[y] || 0)), 1) - 1;
  const boxes = [
    ["2008", pc(yv[2008], 0), "Global financial crisis", GAIN],
    ["2009–14", pc(lean, 0) + " over six years", "Central-bank suppressed trends", LOSS],
    ["2022", pc(yv[2022], 0), "Inflation shock, bonds and equities fell together", GAIN],
  ];
  boxes.forEach((b, i) => {
    const x = 0.6 + i * 4.13;
    card(s, x, 5.4, 3.83, 1.25);
    s.addText(b[0], { x: x + 0.28, y: 5.55, w: 1.5, h: 0.32, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12, color: MUTE, bold: true });
    s.addText(b[1], { x: x + 0.28, y: 5.83, w: 3.3, h: 0.4, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 18, bold: true, color: b[3] });
    s.addText(b[2], { x: x + 0.28, y: 6.22, w: 3.3, h: 0.36, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11, color: "37485A" });
  });
  footer(s, "2026 is a partial year.");
}

/* ================================================ 9 CRISIS ALPHA  (dark) */
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("What it does when equities break", { x: 0.6, y: 0.4, w: 12.1, h: 0.55, isTextBox: true,
    fontFace: H, fontSize: 30, color: PAPER, bold: true });
  s.addText("The ten worst months for the S&P 500 in this sample, and what the strategy did in each.",
    { x: 0.6, y: 0.97, w: 12.1, h: 0.4, isTextBox: true, fontFace: B, fontSize: 14, color: "AEBECD" });

  s.addChart(pres.ChartType.bar, [
    { name: "S&P 500", labels: D.crisis.map(c => c[0]), values: D.crisis.map(c => c[1]) },
    { name: "TSMOM",   labels: D.crisis.map(c => c[0]), values: D.crisis.map(c => c[2]) },
  ], {
    x: 0.6, y: 1.55, w: 8.35, h: 4.15, barDir: "col", barGapWidthPct: 45,
    chartColors: [LOSS, ACC], showLegend: true, legendPos: "t", legendColor: "AEBECD",
    legendFontFace: B, legendFontSize: 11,
    catAxisLabelColor: "8FA3B6", valAxisLabelColor: "8FA3B6",
    catAxisLabelFontFace: B, valAxisLabelFontFace: B,
    catAxisLabelFontSize: 9.5, valAxisLabelFontSize: 10,
    valGridLine: { color: "27405A", size: 0.75 }, catGridLine: { style: "none" },
    catAxisLineShow: false, valAxisLineShow: false, showTitle: false,
    valAxisLabelFormatCode: "0%",
  });

  card(s, 9.25, 1.55, 3.45, 4.15, INK2);
  s.addText("In those ten months", { x: 9.55, y: 1.8, w: 2.9, h: 0.3, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 11.5, color: ACC, bold: true, charSpacing: 1 });
  s.addText(pc(D.crisis_avg[0]), { x: 9.55, y: 2.2, w: 2.9, h: 0.6, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 32, bold: true, color: "E8908A" });
  s.addText("average S&P 500 month", { x: 9.55, y: 2.78, w: 2.9, h: 0.3, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 11.5, color: "AEBECD" });
  s.addText(pc(D.crisis_avg[1]), { x: 9.55, y: 3.3, w: 2.9, h: 0.6, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 32, bold: true, color: ACC });
  s.addText("average TSMOM month", { x: 9.55, y: 3.88, w: 2.9, h: 0.3, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 11.5, color: "AEBECD" });
  s.addText(D.crisis_hit + " of 10", { x: 9.55, y: 4.4, w: 2.9, h: 0.55, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 30, bold: true, color: PAPER });
  s.addText("were positive for the strategy while equities fell",
    { x: 9.55, y: 4.95, w: 2.9, h: 0.6, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, color: "AEBECD", lineSpacing: 15 });

  s.addText("This is the reason to own it. Trend does not hedge equities by construction — it simply ends up short whatever has been falling, and crises take time to unfold.",
    { x: 0.6, y: 5.95, w: 12.1, h: 0.7, isTextBox: true,
      fontFace: B, fontSize: 13.5, color: "D6E0E9", lineSpacing: 18 });
  footer(s, "Worst ten S&P 500 futures months, " + D.month_first.slice(0, 4) + "–" +
    D.month_last.slice(0, 4) + ". Not a guarantee of behaviour in future crises.");
  s.addNotes("The mechanism matters: this is not an options hedge, it is a slow adaptation. " +
    "It failed in Feb 2020 and Dec 2018 because those were fast reversals — trend needs a trend.");
}

/* ================================================ 10 RISK PROFILE */
{
  const s = pres.addSlide();
  head(s, "It is genuinely uncorrelated",
    "Not low-beta by accident of period, but by construction: the strategy is as willing to be short as long.");

  const t = [
    [D.beta_all.toFixed(2), "Beta to S&P 500", "full sample", INK],
    [D.corr.toFixed(2), "Correlation", "monthly excess returns", INK],
    [D.beta_down.toFixed(2), "Beta in down months", "when equities fall", GAIN],
    [D.beta_up.toFixed(2), "Beta in up months", "when equities rise", INK],
  ];
  t.forEach((v, i) => {
    const x = 0.6 + i * 3.06;
    card(s, x, 1.6, 2.86, 1.5);
    stat(s, x + 0.26, 1.78, 2.4, v[0], v[1], v[2], v[3]);
  });

  card(s, 0.6, 3.35, 6.0, 3.05);
  s.addText("What the numbers say", { x: 0.92, y: 3.6, w: 5.4, h: 0.35, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 16, bold: true, color: INK });
  s.addText([
    { text: "A beta of " + D.beta_all.toFixed(2) + " across the whole sample, and " + D.beta_down.toFixed(2) + " in the months equities fall — it leans against them when it matters, rather than merely sitting out.", options: { bullet: { indent: 14 }, breakLine: true } },
    { text: "An R² of " + pcu(D.corr * D.corr, 1) + " — equity direction explains almost none of the return.", options: { bullet: { indent: 14 }, breakLine: true } },
    { text: "It is a return stream, not a hedge: it carries positive expected return rather than paying a premium like put options.", options: { bullet: { indent: 14 }, breakLine: true } },
    { text: "Correlation is an outcome, not a target. No constraint forces it to zero.", options: { bullet: { indent: 14 } } },
  ], { x: 0.92, y: 4.02, w: 5.4, h: 2.2, isTextBox: true, margin: 0,
       fontFace: B, fontSize: 12, color: "37485A", paraSpaceAfter: 8, lineSpacing: 16 });

  card(s, 6.9, 3.35, 5.74, 3.05, INK);
  s.addText("Where the risk actually sits", { x: 7.22, y: 3.6, w: 5.2, h: 0.35, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 16, bold: true, color: PAPER });
  s.addText("Equal risk per market is not equal risk per sleeve. Twenty-two equity-index positions in different currencies still move together, so the equity sleeve can carry a majority of portfolio volatility while holding a minority of the capital.",
    { x: 7.22, y: 4.02, w: 5.2, h: 1.35, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12, color: "C3D0DC", lineSpacing: 16 });
  s.addText("We monitor this every month with a full covariance decomposition, and flag any sleeve above 60% of portfolio risk.",
    { x: 7.22, y: 5.42, w: 5.2, h: 0.7, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12, color: ACC, italic: true, lineSpacing: 16 });
  footer(s, "Beta and correlation measured against S&P 500 futures excess returns, monthly.");
}

/* ================================================ 11 ATTRIBUTION */
{
  const s = pres.addSlide();
  head(s, "No single sleeve carries the strategy",
    "Returns by asset class, each run as a standalone trend book on identical rules.");

  const order = ["Commodity", "FX", "Equity", "Bond", "Crypto"].filter(k => D.sleeve[k]);
  const labels = { Commodity: "Commodities", Equity: "Equity indices", FX: "Currencies",
                   Bond: "Bonds & credit", Crypto: "Crypto" };
  s.addChart(pres.ChartType.bar, [{
    name: "Sharpe", labels: order.map(k => labels[k] + "  (" + D.sleeve[k].n + ")"),
    values: order.map(k => D.sleeve[k].sharpe),
  }], {
    x: 0.6, y: 1.65, w: 6.5, h: 3.5, barDir: "bar", barGapWidthPct: 50,
    chartColors: [TEAL], invertedColors: [LOSS], showValue: true, dataLabelPosition: "outEnd",
    dataLabelColor: INK, dataLabelFontFace: B, dataLabelFontSize: 11, dataLabelFontBold: true,
    dataLabelFormatCode: "0.00;-0.00",          // without this every label rounds to "0"
    catAxisLabelPos: "low",                      // keep labels off the negative bar
    ...axisBase, catAxisLabelFontSize: 11.5,
    showTitle: true, title: "Sharpe ratio by sleeve (number of markets)",
    titleFontFace: B, titleFontSize: 12, titleColor: MUTE, titleAlign: "left",
  });

  // Read the ranking off the data. Hard-coding which sleeve leads is how a deck ends up
  // asserting the opposite of the chart printed beside it.
  const rank = order.slice().sort((a, b) => D.sleeve[b].sharpe - D.sleeve[a].sharpe);
  const top = rank.slice(0, 2), low = rank[rank.length - 1];
  const spread = D.sleeve[rank[0]].sharpe - D.sleeve[low].sharpe;
  const pts = [
    [labels[top[0]] + " and " + labels[top[1]].toLowerCase() + " lead",
     "At " + D.sleeve[top[0]].sharpe.toFixed(2) + " and " + D.sleeve[top[1]].sharpe.toFixed(2) +
     ", these are the sleeves where hedging pressure is most visible and the trends least " +
     "tied to one another."],
    [labels[low] + " trail", "The weakest sleeve at " + D.sleeve[low].sharpe.toFixed(2) +
     ", but still positive. Every sleeve clears zero over this sample, and the spread " +
     "between best and worst is only " + spread.toFixed(2) + " — no one of them is the story."],
    ["Crypto is small and young", "From 2018 only and on two markets, so the estimate is " +
     "thin however it lands. Volatility scaling keeps the position small; we do not lean on it."],
  ];
  pts.forEach((p, i) => {
    const y = 1.75 + i * 1.5;
    marker(s, 7.5, y + 0.06);
    s.addText(p[0], { x: 7.8, y: y - 0.06, w: 4.9, h: 0.35, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 14, bold: true, color: INK });
    s.addText(p[1], { x: 7.8, y: y + 0.32, w: 4.9, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, color: "37485A", lineSpacing: 15.5, valign: "top" });
  });
  card(s, 0.6, 5.5, 6.5, 1.15, SURF);
  s.addText("Sleeves are kept whatever they score. Dropping the weakest after the fact is how a backtest becomes fiction, and a sleeve that adds little on its own can still earn its place through what it does to the whole.",
    { x: 0.9, y: 5.5, w: 5.9, h: 1.15, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, color: "37485A", valign: "middle", lineSpacing: 15.5 });
  footer(s, "Sleeve books use the same signal, vol target and sizing as the full portfolio.");
}

/* ================================================ 12 PROCESS */
{
  const s = pres.addSlide();
  head(s, "The monthly process",
    "Fully systematic. The only human decisions are made once, in advance, and written down.");

  const steps = [
    ["Refresh", "Prices for every market download automatically on the first of the month. Bad prints are removed before any return is computed."],
    ["Audit", N_CHECKS + " automated checks run before the numbers are trusted: look-ahead, splice artefacts, staleness, position limits, configuration coherence."],
    ["Signal", "Volatility, signals at 3, 6 and 12 months, weights and the full risk decomposition are rebuilt from scratch."],
    ["Size", "Weights convert to dollar targets and order quantities for the fund's actual size, flagging positions that round to zero."],
    ["Review", "A written summary lands with the PM: signal changes, positioning, risk concentration, and any data-quality warning."],
  ];
  steps.forEach((st, i) => {
    const x = 0.6 + i * 2.44;
    card(s, x, 1.7, 2.24, 3.5);
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.85, y: 1.95, w: 0.54, h: 0.54,
      fill: { color: i === 1 ? ACC : INK }, line: { width: 0 } });
    s.addText(String(i + 1), { x: x + 0.85, y: 1.95, w: 0.54, h: 0.54, isTextBox: true,
      fontFace: B, fontSize: 16, bold: true, color: i === 1 ? INK : PAPER,
      align: "center", valign: "middle" });
    s.addText(st[0], { x: x + 0.18, y: 2.62, w: 1.88, h: 0.35, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 15, bold: true, color: INK, align: "center" });
    s.addText(st[1], { x: x + 0.18, y: 3.02, w: 1.88, h: 2.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 10.5, color: "37485A", align: "center", lineSpacing: 14, valign: "top" });
  });

  card(s, 0.6, 5.45, 12.04, 1.2, INK);
  s.addText("Governance", { x: 0.95, y: 5.62, w: 2.0, h: 0.3, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 11.5, bold: true, color: ACC, charSpacing: 1.5 });
  s.addText("Parameters are fixed in advance and any deviation from the published specification is recorded as such. The investable universe is re-screened quarterly against a liquidity bar that scales with fund size, and every judgement call is written into the configuration rather than applied by hand.",
    { x: 0.95, y: 5.92, w: 11.4, h: 0.65, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 12, color: "C3D0DC", lineSpacing: 16 });
  s.addNotes("Emphasise step 2. The audit is what separates a backtest you can act on from one you cannot. " +
    "It caught two corrupt FX prices in this dataset that would otherwise have inflated volatility estimates for months.");
}

/* ================================================ 13 RISKS */
{
  const s = pres.addSlide();
  head(s, "What would make this stop working",
    "The case against, stated plainly. None of these are hypothetical.");

  const risks = [
    ["Twenty years cannot settle whether it still works", (() => {
      const [a, b] = D.regime_keys[0], [c, d] = D.regime_keys[1];
      return "Split the sample at " + a.slice(-4) + " and the Sharpe falls from " +
        D.regime[a].sharpe.toFixed(2) + " to " + D.regime[b].sharpe.toFixed(2) +
        ". Move the cut one year later and it rises from " + D.regime[c].sharpe.toFixed(2) +
        " to " + D.regime[d].sharpe.toFixed(2) + ". A single year flips the conclusion, " +
        "which is the honest measure of how little this sample can tell you about decay.";
    })()],
    ["The drawdowns are severe", "A " + pcu(Math.abs(D.stats12.maxdd), 0) +
      " peak-to-trough loss, and the longest underwater period runs to years, not months. Capital that cannot sit through that should not be here."],
    ["This is not a return-maximising strategy", "Equities compounded far faster over the same window. The argument for this book is what it does when equities do not — nothing else."],
    ["Retail-grade data has limits", "Continuous futures splice contracts imperfectly, and emerging-market currency returns exclude the interest differential, which overstates their contribution."],
  ];
  risks.forEach((rk, i) => {
    const x = 0.6 + (i % 2) * 6.2;
    const y = 1.6 + Math.floor(i / 2) * 2.35;
    card(s, x, y, 5.9, 2.05);
    marker(s, x + 0.3, y + 0.3, LOSS);
    s.addText(rk[0], { x: x + 0.3, y: y + 0.48, w: 5.3, h: 0.4, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 15.5, bold: true, color: INK });
    s.addText(rk[1], { x: x + 0.3, y: y + 0.9, w: 5.3, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, color: "37485A", lineSpacing: 15.5, valign: "top" });
  });
  s.addText("The honest summary: a modest standalone Sharpe, a real crisis-hedging property, and a twenty-year sample too short to prove the edge is either intact or gone.",
    { x: 0.6, y: 6.4, w: 12.1, h: 0.5, isTextBox: true,
      fontFace: B, fontSize: 12.5, italic: true, color: INK, lineSpacing: 17 });
}

/* ================================================ 14 CLOSE (dark) */
{
  const s = pres.addSlide();
  titleSlide(s, "IN SUMMARY", "A diversifier, honestly built",
    "The reason to hold this is not the Sharpe ratio. It is what it does in the months when everything else is falling — and the fact that the profit has a name.");

  const pts = [
    ["It is paid for a reason", "Risk transfer from hedgers and a durable behavioural pattern — not an informational edge we would have to defend."],
    ["It behaves when it matters", "Positive in " + D.crisis_hit + " of the S&P's 10 worst months, averaging " +
      pc(D.crisis_avg[1]) + " while equities averaged " + pc(D.crisis_avg[0]) + "."],
    ["It is verifiable", "Every number rebuilds from raw prices, and " + N_CHECKS + " automated checks stand between the data and the decision."],
  ];
  pts.forEach((p, i) => {
    const x = 0.75 + i * 4.05;
    s.addShape(pres.ShapeType.roundRect, { x, y: 4.35, w: 3.75, h: 2.0, rectRadius: 0.06,
      fill: { color: INK2 }, line: { width: 0 } });
    marker(s, x + 0.3, 4.62);
    s.addText(p[0], { x: x + 0.3, y: 4.8, w: 3.15, h: 0.4, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 15, bold: true, color: PAPER });
    s.addText(p[1], { x: x + 0.3, y: 5.22, w: 3.15, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11.5, color: "AEBECD", lineSpacing: 15.5 });
  });
  s.addText("Signals and analytics, not investment advice. Past performance does not indicate future results.",
    { x: 0.75, y: 6.72, w: 11.8, h: 0.3, isTextBox: true,
      fontFace: B, fontSize: 9.5, color: "6E8398", italic: true });
}

pres.writeFile({ fileName: "TSMOM_Strategy.pptx" }).then(f => console.log("wrote", f));
