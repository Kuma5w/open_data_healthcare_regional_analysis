/* 質問窓口に書かれた「表示の切り替え」の依頼（地域・並べ方・指標）を読み取る。
   決まった規則だけで読み取り、AIは使わない。数値も扱わない。
   site/index.html と、テスト（tests/test_site_command.py が node で実行）から使う。

   使い方（2段階）
     const p = ChiikiCommand.parse("熊本県の結果を出して", { prefectures, indicators, current });
     // p.indicator で表示する指標が決まったら、その指標の結果の地域一覧で地域名を照合する
     const r = ChiikiCommand.resolve(p, areas, unit);   // areas: [{code, name}]
*/
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ChiikiCommand = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // 全角・半角をそろえ、空白と中点を除く（「熊本・上益城」と「熊本上益城」を同じに扱う）
  const norm = (s) => String(s ?? "").normalize("NFKC").replace(/[\s・]/g, "");

  // 表示の依頼を表す言い方。「表示中の」「表示されている」「並べ方」などの説明の言葉は除く
  const VERB = /出して|だして|出せ|出力し|表示して|表示(?![中さしの])|見せて|みせて|見たい|みたい|切り?替え|切替|きりかえ|変えて|かえて|にして(?![はもい])|絞り込|絞って|しぼって|開いて|ひらいて|戻して|もどして|戻る|並べ(?!方)|ならべ(?!かた)|並び替え|ソート|移動して|選んで/;
  const VERB_G = new RegExp(VERB.source, "g");
  const REQUEST = /ください|下さい|くれますか|くれる|もらえますか|もらえる|いただけますか|いただけます|お願いします|お願い|おねがい|ほしい|欲しい|頼む|たい/g;
  const FILLER = /結果|値|表|グラフ|地図|一覧|だけ|のみ|データ|画面|ページ|全体/g;
  const QWORDS = /なぜ|何故|どうして|教えて|説明|理由|意味|とは|注意|違い|どう|なに|何|どこ|どれ|いくつ|いくら|比べ|読み方|解釈|ですか|でしょう/;
  const SORTS = [
    [/(小さい|少ない|低い)順|昇順/, "asc"],
    [/(大きい|多い|高い)順|降順/, "desc"],
    [/(コード|番号)順/, "code"],
  ];
  // 地名の一部かどうか（直前・直後が漢字やカタカナなら、もっと長い地名の一部とみなす）
  const NAMECH = /[㐀-鿿゠-ヿヶ]/;
  // 構想区域名のあとに付く言葉
  const SUFFIX = /^(構想区域|区域|医療圏|圏域|地域)/;

  const bigrams = (s) => { const g = new Set(); for (let i = 0; i < s.length - 1; i++) g.add(s.slice(i, i + 2)); return g; };
  const findAll = (text, word) => { const out = []; if (!word) return out; let i = text.indexOf(word); while (i >= 0) { out.push(i); i = text.indexOf(word, i + 1); } return out; };
  const overlaps = (a, b) => a.start < b.end && b.start < a.end;
  const shortName = (name) => (name === "北海道" ? name : name.replace(/[都府県]$/, ""));

  // 都道府県名を探す。正式名（熊本県）を先に、次に短い名前（熊本）。短い名前は、長い地名の一部（北広島市の「広島」）を除く
  function findPrefs(text, prefectures) {
    const hits = [];
    for (const [code, name] of Object.entries(prefectures || {})) {
      for (const s of findAll(text, name)) hits.push({ code, start: s, end: s + name.length, full: true });
      const sn = shortName(name);
      if (sn !== name) {
        for (const s of findAll(text, sn)) {
          if (s > 0 && NAMECH.test(text[s - 1])) continue;
          hits.push({ code, start: s, end: s + sn.length, full: false });
        }
      }
    }
    // 重なったら、前にあるもの、同じ位置なら長いもの（正式名）を残す（「東京都府中市」の「京都府」を除く）
    hits.sort((a, b) => a.start - b.start || b.end - a.end);
    const out = [];
    for (const h of hits) if (!out.some((o) => overlaps(o, h))) out.push(h);
    return out;
  }

  function matchIndicator(text, indicators, current) {
    const list = (indicators || []).map((x) => ({ id: x.id, g: bigrams(norm(x.name)) }));
    if (!list.length) return { indicator: null, ties: [] };
    // すべての指標名に共通する2文字組（「ごと」など）は手がかりにしない
    const common = list.length > 1 ? [...list[0].g].filter((g) => list.every((x) => x.g.has(g))) : [];
    const qg = bigrams(text);
    for (const g of common) qg.delete(g);
    const scored = list.map((x) => { let n = 0; for (const g of qg) if (x.g.has(g)) n++; return { id: x.id, n }; });
    const best = Math.max(...scored.map((x) => x.n));
    if (best < 3) return { indicator: null, ties: [] };
    const ties = scored.filter((x) => x.n === best).map((x) => x.id);
    if (ties.length === 1) return { indicator: ties[0], ties: [] };
    if (current && ties.includes(current)) return { indicator: current, ties: [] };
    return { indicator: null, ties };
  }

  /**
   * 1段階目：都道府県・全国・並べ方・指標・表示の依頼かどうかを読む。
   * ctx = { prefectures: {"01": "北海道", ...}, indicators: [{id, name}], current: 表示中の指標id }
   */
  function parse(q, ctx = {}) {
    const text = norm(q);
    const prefHits = findPrefs(text, ctx.prefectures);
    let sort = null;
    for (const [re, v] of SORTS) if (re.test(text)) { sort = v; break; }
    const { indicator, ties } = matchIndicator(text, ctx.indicators, ctx.current);
    return { q, text, prefHits, national: /全国/.test(text), sort, verb: VERB.test(text), indicator, ties };
  }

  /**
   * 2段階目：表示する指標の地域一覧（areas）で、市区町村名・構想区域名を照合し、地域を決める。
   * unit は指標の単位（municipality / koso_kuiki など）。areas のコードの先頭2桁が都道府県コード。
   * 返す値：{ display, question, pref, prefs, areas }
   *   pref: undefined（指定なし）、""（全国）、都道府県コード
   *   areas: 照合できた地域 [{code, name}]（同じ名前が複数あれば、そのすべて）
   */
  function resolve(p, areas, unit) {
    const t = p.text;
    const prefCodes = new Set(p.prefHits.map((h) => h.code));
    const cand = [];
    for (const a of areas || []) {
      const n = norm(a.name);
      if (!n) continue;
      const isKoso = unit !== "municipality";
      for (const s of findAll(t, n)) {
        const e = s + n.length;
        const suffix = SUFFIX.test(t.slice(e));
        if (isKoso && !suffix) {
          // 区域名と都道府県の短い名前が同じ（「富山」）なら、都道府県として読む
          if (p.prefHits.some((h) => h.start === s && h.end === e)) continue;
          const before = s > 0 && NAMECH.test(t[s - 1]) && !p.prefHits.some((h) => h.end === s);
          const after = e < t.length && NAMECH.test(t[e]);
          if (before || after) continue;
          // 2文字以下の区域名（「県南」「東部」）は、同じ文にその都道府県があるときだけ。「堺市」のように市町村名と同じ形の区域名は除く
          if (n.length <= 2 && !/[市町村区]$/.test(n) && !prefCodes.has(a.code.slice(0, 2))) continue;
        }
        cand.push({ code: a.code, name: a.name, start: s, end: e + (suffix ? t.slice(e).match(SUFFIX)[0].length : 0) });
      }
    }
    // 長い名前を優先し、重なるものは除く（「北広島市」と「広島市」）
    cand.sort((a, b) => (b.end - b.start) - (a.end - a.start) || a.start - b.start);
    const spans = [];
    let hits = [];
    for (const c of cand) {
      if (spans.some((s) => overlaps(s, c) && !(s.start === c.start && s.end === c.end))) continue;
      if (!spans.some((s) => s.start === c.start && s.end === c.end)) spans.push(c);
      hits.push(c);
    }
    // 地域名の一部として読んだ都道府県名は除く（「石川町」の「石川」）
    const prefHits = p.prefHits.filter((h) => !spans.some((s) => s.start <= h.start && h.end <= s.end));
    const prefs = [...new Set(prefHits.map((h) => h.code))];
    if (prefs.length) {
      const inPref = hits.filter((h) => prefs.includes(h.code.slice(0, 2)));
      if (inPref.length) hits = inPref;
    }
    const seen = new Set();
    const found = hits.filter((h) => !seen.has(h.code) && seen.add(h.code)).map(({ code, name }) => ({ code, name }));

    // 依頼の言葉と地名などを除いた残り。何も残らなければ、地名だけの依頼（「熊本県」）とみなす
    let rest = t;
    const cut = [...prefHits, ...spans].sort((a, b) => b.start - a.start);
    for (const c of cut) rest = rest.slice(0, c.start) + rest.slice(c.end);
    rest = rest.replace(/全国/g, "").replace(VERB_G, "").replace(REQUEST, "").replace(FILLER, "");
    for (const [re] of SORTS) rest = rest.replace(new RegExp(re.source, "g"), "");
    const bare = rest.replace(/[のをでにはへもとがかね。、！!?？「」]/g, "");
    const targeted = prefs.length > 0 || found.length > 0 || p.national || !!p.sort;
    const display = p.verb || (targeted && bare === "");
    const question = QWORDS.test(rest) || (/[?？]/.test(rest) && bare.length >= 4);

    let pref;
    if (prefs.length) pref = prefs[0];
    else if (found.length) pref = found[0].code.slice(0, 2);
    else if (p.national) pref = "";
    return { display, question, pref, prefs, areas: found };
  }

  return { norm, parse, resolve };
});
