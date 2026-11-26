// tests/test_site_command.py から呼ぶ。標準入力の JSON（ケースの一覧）を site/command.js で読み、結果を JSON で返す
const path = require("path");
const cmd = require(path.join(__dirname, "..", "site", "command.js"));

let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  const { ctx, cases } = JSON.parse(input);
  const out = cases.map((c) => {
    const p = cmd.parse(c.q, { ...ctx, current: c.current ?? null });
    const target = p.indicator || c.current || null;
    const unit = target ? ctx.units[target] : null;
    const r = cmd.resolve(p, target ? ctx.areas[target] : [], unit);
    return { indicator: p.indicator, ties: p.ties, sort: p.sort, ...r, areas: r.areas.map((a) => a.code) };
  });
  process.stdout.write(JSON.stringify(out));
});
