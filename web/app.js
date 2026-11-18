// Factory Production Monitoring (OEE) dashboard. Talks to the API; when there is no
// API (the GitHub Pages demo) it reads the same responses from data/demo.json.
(function () {
  "use strict";
  var root = document.documentElement;
  var demo = null;
  var selected = null;
  var chart = null;
  var paretoChart = null;
  var paretoData = [];

  // ---- language ---------------------------------------------------------
  try {
    var saved = localStorage.getItem("lang") || ((navigator.language || "").slice(0, 2) === "id" ? "id" : "en");
    root.dataset.lang = saved;
  } catch (e) {}
  document.querySelector(".lang").addEventListener("click", function () {
    root.dataset.lang = root.dataset.lang === "en" ? "id" : "en";
    try { localStorage.setItem("lang", root.dataset.lang); } catch (e) {}
    renderPareto(paretoData);  // chart labels are drawn on the canvas, not in spans
  });

  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
  function t(en, id) { return '<span class="t-en">' + esc(en) + '</span><span class="t-id">' + esc(id) + "</span>"; }
  function pct(v) { return v == null ? "–" : (v * 100).toFixed(1) + "%"; }
  function num(v) { return v == null ? "–" : Number(v).toLocaleString(root.dataset.lang === "id" ? "id-ID" : "en-US"); }
  function lang(label) { return label ? label[root.dataset.lang] || label.en : ""; }
  function css(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }
  function time(iso, opts) {
    return new Date(iso).toLocaleString(root.dataset.lang === "id" ? "id-ID" : "en-GB",
      opts || { weekday: "short", hour: "2-digit", minute: "2-digit" });
  }

  // ---- data -------------------------------------------------------------
  async function api(path) {
    if (!demo) {
      try {
        var res = await fetch("api/" + path);
        if (res.ok && (res.headers.get("content-type") || "").indexOf("json") !== -1) return res.json();
      } catch (e) {}
      var file = await fetch("data/demo.json");
      demo = await file.json();
      document.body.classList.add("is-demo");
    }
    return demo.api[path];
  }

  // ---- rendering --------------------------------------------------------
  function statusTag(line) {
    if (line.down) return '<span class="status s-down">' + t("Stopped", "Berhenti") + "</span>";
    var s = line.current_shift && line.current_shift.band ? line.current_shift : line.last_24h;
    return s && s.band ? '<span class="status s-' + s.band + '">' + t(s.band_label.en, s.band_label.id) + "</span>"
      : '<span class="status s-none">' + t("Break", "Istirahat") + "</span>";
  }

  function renderKpis(summary) {
    var d = summary.last_24h;
    var items = [
      ["var(--accent)", pct(d.oee), "OEE, all lines (24 h)", "OEE, semua lini (24 jam)"],
      ["var(--world_class)", pct(d.availability), "Availability", "Ketersediaan"],
      ["var(--acceptable)", pct(d.performance), "Performance", "Performa"],
      ["var(--muted)", pct(d.quality), "Quality", "Kualitas"],
      ["var(--down)", summary.lines_down + "/" + summary.lines, "Lines stopped now", "Lini berhenti sekarang"],
      ["var(--low)", summary.alerts_24h, "Alerts (24 h)", "Peringatan (24 jam)"]
    ];
    document.getElementById("kpis").innerHTML = items.map(function (k) {
      return '<div class="kpi" style="--c:' + k[0] + '"><b>' + esc(k[1]) + "</b><span>" + t(k[2], k[3]) + "</span></div>";
    }).join("");
  }

  function renderTable(lines) {
    var rows = lines.slice().sort(function (a, b) {
      return (a.last_24h.oee == null ? 2 : a.last_24h.oee) - (b.last_24h.oee == null ? 2 : b.last_24h.oee);
    });
    document.getElementById("line-rows").innerHTML = rows.map(function (l) {
      var s = l.current_shift || {}, d = l.last_24h;
      var low = function (v) { return v != null && v < 0.65 ? ' class="num bad"' : ' class="num"'; };
      return '<tr data-id="' + esc(l.id) + '"' + (l.id === selected ? ' class="selected"' : "") + ">" +
        "<td><b>" + esc(l.name) + "</b><small>" + esc(l.plant) + " · " + esc(l.city) + "</small></td>" +
        "<td>" + statusTag(l) + "</td>" +
        "<td" + low(s.oee) + "><b>" + pct(s.oee) + "</b></td><td" + low(d.oee) + ">" + pct(d.oee) + "</td>" +
        '<td class="num">' + pct(d.availability) + '</td><td class="num">' + pct(d.performance) +
        '</td><td class="num">' + pct(d.quality) + "</td></tr>";
    }).join("");
  }

  async function renderDetail(line) {
    var s = line.current_shift || {};
    document.getElementById("d-name").textContent = line.name;
    document.getElementById("d-where").innerHTML = esc(line.plant) + " · " + esc(line.estate) + ", " + esc(line.city) +
      "<br>" + t(line.product.en, line.product.id) + " · " + t("ideal cycle ", "siklus ideal ") + esc(line.ideal_cycle_s) + " s";
    document.getElementById("d-status").innerHTML = statusTag(line) + (line.down ?
      ' <span class="muted">' + t(line.down.reason_label.en, line.down.reason_label.id) + "</span>" : "");
    document.getElementById("d-oee").textContent = pct(s.oee);
    var cards = [
      ["Availability", "Ketersediaan", pct(s.availability), "", s.availability != null && s.availability < 0.8],
      ["Performance", "Performa", pct(s.performance), "", s.performance != null && s.performance < 0.8],
      ["Quality", "Kualitas", pct(s.quality), "", s.quality != null && s.quality < 0.97],
      ["Good / total", "Baik / total", num(s.good_count), "/ " + num(s.total_count), false],
      ["Downtime", "Waktu henti", num(s.downtime_minutes), "min", s.downtime_minutes > 30],
      ["Planned time", "Waktu terencana", num(s.planned_minutes), "min", false]
    ];
    document.getElementById("d-params").innerHTML = cards.map(function (c) {
      return '<div class="param' + (c[4] ? " over" : "") + '"><span>' + t(c[0], c[1]) + "</span><b>" + esc(c[2]) +
        "</b> <small>" + esc(c[3]) + "</small></div>";
    }).join("");
    document.getElementById("d-shifts").innerHTML = '<span class="muted">' + t("24 h by shift:", "24 jam per shift:") + "</span>" +
      line.shifts_24h.map(function (x) {
        return '<span class="chip status s-' + (x.band || "none") + '">Shift ' + esc(x.shift) + " · " + pct(x.oee) + "</span>";
      }).join("");

    var results = await Promise.all([api("lines/" + line.id + "/history?hours=72"), api("lines/" + line.id + "/downtime?hours=24")]);
    var history = results[0] || [], stops = results[1] || [];
    var labels = history.map(function (h) { return time(h.timestamp); });
    var series = [["OEE", "oee", "--accent", 3], ["A", "availability", "--world_class", 1.5],
      ["P", "performance", "--acceptable", 1.5], ["Q", "quality", "--muted", 1.5]];
    var datasets = series.map(function (x) {
      return { label: x[0], borderColor: css(x[2]), borderWidth: x[3], pointRadius: 0, tension: 0.25, spanGaps: true,
        data: history.map(function (h) { return h[x[1]] == null ? null : +(h[x[1]] * 100).toFixed(1); }) };
    });
    datasets.push({ label: "65%", data: history.map(function () { return 65; }), borderColor: css("--low"),
      borderDash: [4, 4], borderWidth: 1, pointRadius: 0 });
    if (chart) chart.destroy();
    chart = new window.Chart(document.getElementById("d-chart"), {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { boxWidth: 12, color: css("--muted") } } },
        scales: {
          x: { ticks: { maxTicksLimit: 6, color: css("--muted") }, grid: { display: false } },
          y: { min: 0, max: 100, ticks: { callback: function (v) { return v + "%"; }, color: css("--muted") }, grid: { color: css("--line") } }
        }
      }
    });

    document.getElementById("d-stops").innerHTML = stops.length ? stops.map(function (e) {
      return '<li class="' + (e.long ? "long" : "") + '"><span class="when">' + esc(time(e.start)) + "</span><span>" +
        t(e.reason_label.en, e.reason_label.id) + '</span><span class="mins">' + esc(e.minutes) + " min</span></li>";
    }).join("") : '<li class="empty">' + t("No stops recorded.", "Tidak ada henti tercatat.") + "</li>";
  }

  function renderPareto(rows) {
    paretoData = rows || [];
    if (!window.Chart) return;
    if (paretoChart) paretoChart.destroy();
    paretoChart = new window.Chart(document.getElementById("pareto-chart"), {
      data: {
        labels: paretoData.map(function (p) { return lang(p.label); }),
        datasets: [
          { type: "bar", label: root.dataset.lang === "id" ? "Menit" : "Minutes", yAxisID: "y", backgroundColor: css("--accent"),
            borderRadius: 4, data: paretoData.map(function (p) { return p.minutes; }) },
          { type: "line", label: root.dataset.lang === "id" ? "Kumulatif %" : "Cumulative %", yAxisID: "y1",
            borderColor: css("--ink"), backgroundColor: css("--ink"), borderWidth: 2, pointRadius: 3,
            data: paretoData.map(function (p) { return +(p.cumulative * 100).toFixed(1); }) }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { boxWidth: 12, color: css("--muted") } } },
        scales: {
          x: { ticks: { color: css("--muted"), autoSkip: false, maxRotation: 45 }, grid: { display: false } },
          y: { position: "left", title: { display: true, text: "min" }, grid: { color: css("--line") } },
          y1: { position: "right", min: 0, max: 100, ticks: { callback: function (v) { return v + "%"; } }, grid: { display: false } }
        }
      }
    });
  }

  function renderShifts(shifts) {
    document.getElementById("shifts").innerHTML = shifts.map(function (s) {
      var w = s.oee == null ? 0 : Math.min(100, s.oee * 100);
      return '<div class="shift-row"><div class="head">' + t(s.label.en, s.label.id) + "<b>" + pct(s.oee) + "</b></div>" +
        '<div class="bar" style="--sc:var(--' + (s.band || "line") + ')"><i style="width:' + w + '%"></i>' +
        '<span class="mark" style="left:65%"></span><span class="mark" style="left:85%"></span></div>' +
        '<div class="apq">A ' + pct(s.availability) + " · P " + pct(s.performance) + " · Q " + pct(s.quality) +
        " · " + t("down ", "henti ") + num(s.downtime_minutes) + " min · " + t("rejects ", "reject ") + num(s.reject_count) + "</div></div>";
    }).join("") + '<div class="legend muted">' + t("Marks at 65% (floor) and 85% (world class).",
      "Tanda di 65% (batas bawah) dan 85% (kelas dunia).") + "</div>";
  }

  // ---- wiring -----------------------------------------------------------
  var linesCache = [];

  function select(id) {
    selected = id;
    var l = linesCache.find(function (x) { return x.id === id; });
    if (!l) return;
    document.querySelectorAll("#line-rows tr").forEach(function (tr) { tr.classList.toggle("selected", tr.dataset.id === id); });
    renderDetail(l);
    document.dispatchEvent(new CustomEvent("oee:selected", { detail: l }));
  }

  document.getElementById("line-rows").addEventListener("click", function (e) {
    var tr = e.target.closest("tr");
    if (tr) select(tr.dataset.id);
  });
  document.addEventListener("oee:select", function (e) { select(e.detail); });

  async function refresh() {
    var results = await Promise.all([api("lines"), api("summary"), api("downtime/pareto?hours=24"), api("shifts?hours=24")]);
    linesCache = results[0];
    renderKpis(results[1]);
    renderTable(linesCache);
    renderPareto(results[2]);
    renderShifts(results[3]);
    var latest = results[1].latest;
    document.getElementById("updated").textContent = latest ?
      new Date(new Date(latest).getTime() + 3600000).toLocaleString() : "–";
    if (!selected && results[1].worst) selected = results[1].worst.line_id;
    select(selected);
    document.dispatchEvent(new CustomEvent("oee:data", { detail: { lines: linesCache, api: api } }));
  }

  refresh();
  setInterval(function () { if (!demo) refresh(); }, 60000);
})();
