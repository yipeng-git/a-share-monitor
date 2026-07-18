/* HJ OBSERVE dashboard */
(function () {
  "use strict";

  const DATA_BASE = "./data";
  const state = {
    meta: null,
    shares: [], // [date, code, shareWan]
    indexes: [], // [date, code, o,h,l,c,v]
    groupId: null,
    etfMode: "sum", // sum | code
    range: "1Y",
  };

  let mainChart;
  let subChart;

  function $(sel) {
    return document.querySelector(sel);
  }

  async function loadJson(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`load failed ${path}: ${res.status}`);
    return res.json();
  }

  async function init() {
    mainChart = echarts.init($("#mainChart"), null, { renderer: "canvas" });
    subChart = echarts.init($("#subChart"), null, { renderer: "canvas" });
    window.addEventListener("resize", () => {
      mainChart.resize();
      subChart.resize();
    });

    const [meta, shares, indexes] = await Promise.all([
      loadJson(`${DATA_BASE}/meta.json`),
      loadJson(`${DATA_BASE}/etf_shares.json`),
      loadJson(`${DATA_BASE}/indexes.json`),
    ]);
    state.meta = meta;
    state.shares = shares;
    state.indexes = indexes;
    state.groupId = (meta.groups && meta.groups[0] && meta.groups[0].id) || null;

    renderMeta();
    renderGroupTabs();
    bindRangeTabs();
    renderAll();
  }

  function renderMeta() {
    const m = state.meta;
    const shareD = m.share_data_date || "—";
    const upd = m.updated_at ? m.updated_at.replace("T", " ").slice(0, 19) : "—";
    $("#metaLine").textContent = `份额日 ${shareD} · 站点更新 ${upd}`;
  }

  function currentGroup() {
    return (state.meta.groups || []).find((g) => g.id === state.groupId);
  }

  function renderGroupTabs() {
    const el = $("#groupTabs");
    el.innerHTML = "";
    (state.meta.groups || []).forEach((g) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = g.name;
      btn.dataset.group = g.id;
      if (g.id === state.groupId) btn.classList.add("active");
      btn.addEventListener("click", () => {
        state.groupId = g.id;
        state.etfMode = "sum";
        renderGroupTabs();
        renderAll();
      });
      el.appendChild(btn);
    });
  }

  function renderEtfTabs() {
    const g = currentGroup();
    const el = $("#etfTabs");
    el.innerHTML = "";
    if (!g) return;

    const make = (label, mode) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      if (state.etfMode === mode) btn.classList.add("active");
      btn.addEventListener("click", () => {
        state.etfMode = mode;
        renderEtfTabs();
        renderAll();
      });
      el.appendChild(btn);
    };

    if (g.etfs.length > 1) {
      make("合计", "sum");
      g.etfs.forEach((e) => {
        const tag = e.exchange === "szse" ? "·SZ" : "";
        make(`${e.code}${tag}`, e.code);
      });
    } else if (g.etfs.length === 1) {
      // single-ETF groups: treat as that code
      if (state.etfMode === "sum") state.etfMode = g.etfs[0].code;
      const e = g.etfs[0];
      const tag = e.exchange === "szse" ? "·SZ" : "";
      make(`${e.code}${tag}`, e.code);
    }
  }

  function bindRangeTabs() {
    $("#rangeTabs").addEventListener("click", (ev) => {
      const btn = ev.target.closest("button[data-range]");
      if (!btn) return;
      state.range = btn.dataset.range;
      [...$("#rangeTabs").querySelectorAll("button")].forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      renderAll();
    });
  }

  function parseDate(s) {
    return new Date(s + "T00:00:00");
  }

  function rangeStart(allDates) {
    if (!allDates.length) return null;
    const last = parseDate(allDates[allDates.length - 1]);
    if (state.range === "ALL") return parseDate(allDates[0]);
    const d = new Date(last);
    if (state.range === "1M") d.setMonth(d.getMonth() - 1);
    else if (state.range === "3M") d.setMonth(d.getMonth() - 3);
    else if (state.range === "1Y") d.setFullYear(d.getFullYear() - 1);
    return d;
  }

  function buildSeries() {
    const g = currentGroup();
    if (!g) return null;

    const codes =
      state.etfMode === "sum" ? g.etfs.map((e) => e.code) : [state.etfMode];
    const codeSet = new Set(codes);

    // date -> { code: share }
    const byDate = new Map();
    for (const [d, code, share] of state.shares) {
      if (!codeSet.has(code)) continue;
      if (!byDate.has(d)) byDate.set(d, {});
      byDate.get(d)[code] = share;
    }

    const indexByDate = new Map();
    for (const row of state.indexes) {
      if (row[1] !== g.index_code) continue;
      indexByDate.set(row[0], row[5]); // close
    }

    const dates = [...byDate.keys()].sort();
    const start = rangeStart(dates);
    const filtered = start
      ? dates.filter((d) => parseDate(d) >= start)
      : dates;

    const shareSeries = [];
    const indexSeries = [];
    const perEtf = {};
    g.etfs.forEach((e) => {
      perEtf[e.code] = [];
    });

    for (const d of filtered) {
      const bag = byDate.get(d) || {};
      let sum = 0;
      let any = false;
      for (const c of codes) {
        if (bag[c] == null) continue;
        sum += bag[c];
        any = true;
      }
      // 合计：当日有任一标的即计入（深市历史较短时不全量要求）
      if (state.etfMode === "sum") {
        if (!any) continue;
      } else if (bag[codes[0]] == null) continue;

      const shareWan = state.etfMode === "sum" ? sum : bag[codes[0]];
      // 万份 → 亿份 for display: / 10000
      const shareYi = shareWan / 10000;
      shareSeries.push([d, shareYi]);
      const idx = indexByDate.get(d);
      indexSeries.push([d, idx != null ? idx : null]);

      if (g.etfs.length > 1) {
        g.etfs.forEach((e) => {
          const v = bag[e.code];
          perEtf[e.code].push([d, v != null ? v / 10000 : null]);
        });
      }
    }

    return { g, shareSeries, indexSeries, perEtf, filtered };
  }

  function lastChange(series) {
    if (!series || series.length < 2) return { last: null, day: null, week: null };
    const last = series[series.length - 1][1];
    const prev = series[series.length - 2][1];
    const day = last - prev;
    let week = null;
    if (series.length >= 6) {
      week = last - series[series.length - 6][1];
    }
    return { last, day, week };
  }

  function fmtYi(n, digits = 2) {
    if (n == null || Number.isNaN(n)) return "—";
    const sign = n > 0 ? "+" : "";
    return `${sign}${n.toFixed(digits)}`;
  }

  function fmtPlain(n, digits = 2) {
    if (n == null || Number.isNaN(n)) return "—";
    return n.toFixed(digits);
  }

  function renderKpi(built) {
    const el = $("#kpi");
    if (!built || !built.shareSeries.length) {
      el.innerHTML = "";
      return;
    }
    const { last, day, week } = lastChange(built.shareSeries);
    const idxSeries = built.indexSeries.filter((x) => x[1] != null);
    const idxLast = idxSeries.length ? idxSeries[idxSeries.length - 1][1] : null;
    const shareLabel = state.etfMode === "sum" ? "合计份额" : "份额";

    const dayCls = day > 0 ? "up" : day < 0 ? "down" : "";
    const weekCls = week > 0 ? "up" : week < 0 ? "down" : "";

    el.innerHTML = `
      <div class="kpi-item">
        <div class="label">${shareLabel}（亿份）</div>
        <div class="value">${fmtPlain(last, 2)}</div>
      </div>
      <div class="kpi-item">
        <div class="label">日变动</div>
        <div class="value ${dayCls}">${fmtYi(day, 2)}</div>
      </div>
      <div class="kpi-item">
        <div class="label">周变动</div>
        <div class="value ${weekCls}">${fmtYi(week, 2)}</div>
      </div>
      <div class="kpi-item">
        <div class="label">${built.g.index_name}</div>
        <div class="value">${fmtPlain(idxLast, 2)}</div>
      </div>
    `;
  }

  function renderMain(built) {
    if (!built) return;
    const shareName =
      state.etfMode === "sum" ? `${built.g.name} 合计份额` : `${state.etfMode} 份额`;

    mainChart.setOption(
      {
        animation: false,
        color: ["#155eef", "#0e0e10"],
        grid: { left: 56, right: 56, top: 36, bottom: 72 },
        legend: {
          data: [shareName, built.g.index_name],
          top: 0,
          textStyle: { color: "#5c6370", fontSize: 12 },
        },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross" },
          valueFormatter: (v) => (v == null ? "—" : Number(v).toFixed(2)),
        },
        axisPointer: { link: [{ xAxisIndex: "all" }] },
        xAxis: {
          type: "category",
          data: built.shareSeries.map((x) => x[0]),
          boundaryGap: false,
          axisLine: { lineStyle: { color: "#b8bdc8" } },
          axisLabel: { color: "#5c6370", fontSize: 11 },
        },
        yAxis: [
          {
            type: "value",
            name: "亿份",
            scale: true,
            nameTextStyle: { color: "#5c6370" },
            splitLine: { lineStyle: { type: "dashed", color: "#d5d8de" } },
            axisLabel: { color: "#5c6370" },
          },
          {
            type: "value",
            name: "指数",
            scale: true,
            nameTextStyle: { color: "#5c6370" },
            splitLine: { show: false },
            axisLabel: { color: "#5c6370" },
          },
        ],
        dataZoom: [
          { type: "inside", start: 0, end: 100 },
          {
            type: "slider",
            height: 18,
            bottom: 8,
            borderColor: "#b8bdc8",
            fillerColor: "rgba(21,94,239,0.12)",
            handleStyle: { color: "#155eef" },
          },
        ],
        series: [
          {
            name: shareName,
            type: "line",
            showSymbol: false,
            lineStyle: { width: 2, color: "#155eef" },
            areaStyle: { color: "rgba(21,94,239,0.08)" },
            data: built.shareSeries.map((x) => x[1]),
          },
          {
            name: built.g.index_name,
            type: "line",
            yAxisIndex: 1,
            showSymbol: false,
            lineStyle: { width: 1.5, color: "#0e0e10", type: "solid" },
            data: built.indexSeries.map((x) => x[1]),
          },
        ],
      },
      true
    );
  }

  const SUB_COLORS = ["#155eef", "#0e0e10", "#c45c26", "#5c6370"];

  function renderSub(built) {
    const panel = $("#subPanel");
    if (!built || built.g.etfs.length < 2 || state.etfMode !== "sum") {
      panel.style.display = "none";
      return;
    }
    panel.style.display = "";
    const dates = built.shareSeries.map((x) => x[0]);
    const series = built.g.etfs.map((e, i) => ({
      name: e.code,
      type: "line",
      showSymbol: false,
      lineStyle: { width: 1.5, color: SUB_COLORS[i % SUB_COLORS.length] },
      data: (built.perEtf[e.code] || []).map((x) => x[1]),
    }));

    subChart.setOption(
      {
        animation: false,
        grid: { left: 56, right: 24, top: 28, bottom: 32 },
        legend: {
          data: built.g.etfs.map((e) => e.code),
          top: 0,
          textStyle: { color: "#5c6370", fontSize: 11 },
        },
        tooltip: { trigger: "axis" },
        xAxis: {
          type: "category",
          data: dates,
          boundaryGap: false,
          axisLine: { lineStyle: { color: "#b8bdc8" } },
          axisLabel: { color: "#5c6370", fontSize: 11 },
        },
        yAxis: {
          type: "value",
          name: "亿份",
          scale: true,
          splitLine: { lineStyle: { type: "dashed", color: "#d5d8de" } },
          axisLabel: { color: "#5c6370" },
        },
        series,
      },
      true
    );
  }

  function renderTable(built) {
    const tbody = $("#changeTable tbody");
    tbody.innerHTML = "";
    if (!built || !built.shareSeries.length) return;

    const rows = [];
    for (let i = built.shareSeries.length - 1; i >= 0 && rows.length < 30; i--) {
      const [d, share] = built.shareSeries[i];
      const prev = i > 0 ? built.shareSeries[i - 1][1] : null;
      const chg = prev != null ? share - prev : null;
      const idx = built.indexSeries[i][1];
      const idxPrev = i > 0 ? built.indexSeries[i - 1][1] : null;
      let pct = null;
      if (idx != null && idxPrev != null && idxPrev !== 0) {
        pct = ((idx - idxPrev) / idxPrev) * 100;
      }
      rows.push({ d, share, chg, idx, pct });
    }

    for (const r of rows) {
      const tr = document.createElement("tr");
      const chgCls = r.chg > 0 ? "up" : r.chg < 0 ? "down" : "";
      const pctCls = r.pct > 0 ? "up" : r.pct < 0 ? "down" : "";
      tr.innerHTML = `
        <td>${r.d}</td>
        <td>${fmtPlain(r.share, 2)}</td>
        <td class="${chgCls}">${fmtYi(r.chg, 2)}</td>
        <td>${fmtPlain(r.idx, 2)}</td>
        <td class="${pctCls}">${r.pct == null ? "—" : fmtYi(r.pct, 2)}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  function renderAll() {
    renderEtfTabs();
    const built = buildSeries();
    renderKpi(built);
    renderMain(built);
    renderSub(built);
    renderTable(built);
    requestAnimationFrame(() => {
      mainChart.resize();
      if ($("#subPanel").style.display !== "none") subChart.resize();
    });
  }

  init().catch((err) => {
    console.error(err);
    $("#metaLine").textContent = "数据加载失败，请先运行 collector 导出 JSON";
  });
})();
