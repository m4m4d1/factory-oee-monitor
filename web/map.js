// Plant map and alerts panel. Listens to the dashboard's events from app.js.
(function () {
  "use strict";
  var LABELS = {
    world_class: ["World class (85%+)", "Kelas dunia (85%+)"], acceptable: ["Acceptable (65-85%)", "Cukup (65-85%)"],
    low: ["Low (below 65%)", "Rendah (di bawah 65%)"], down: ["Line stopped now", "Lini berhenti sekarang"]
  };
  var map = null;
  var markers = {};

  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
  function t(en, id) { return '<span class="t-en">' + esc(en) + '</span><span class="t-id">' + esc(id) + "</span>"; }
  function pct(v) { return v == null ? "–" : (v * 100).toFixed(1) + "%"; }
  function color(key) { return getComputedStyle(document.documentElement).getPropertyValue("--" + (key || "muted")).trim(); }

  function drawMap(plants) {
    if (!window.L) return;
    if (!map) {
      map = window.L.map("map", { scrollWheelZoom: false }).setView([-4, 108], 5);
      window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 15, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      }).addTo(map);
      map.fitBounds(plants.map(function (p) { return [p.lat, p.lon]; }), { padding: [30, 30] });
      document.getElementById("legend").innerHTML = Object.keys(LABELS).map(function (k) {
        return '<span class="status s-' + k + '">' + t(LABELS[k][0], LABELS[k][1]) + "</span>";
      }).join("");
    }
    plants.forEach(function (p) {
      var d = p.last_24h;
      var fill = color(d.band);
      var ring = p.lines_down ? color("down") : fill;
      var popup = "<b>" + esc(p.name) + "</b><br>" + esc(p.estate) + ", " + esc(p.city) + "<br>" +
        t(p.sector.en, p.sector.id) + " · " + p.lines + t(" lines", " lini") +
        "<br>OEE 24h <b>" + pct(d.oee) + "</b> (A " + pct(d.availability) + " · P " + pct(d.performance) + " · Q " + pct(d.quality) + ")" +
        (p.worst_line ? "<br>" + t("Lowest: ", "Terendah: ") + esc(p.worst_line.name) + " " + pct(p.worst_line.oee) : "") +
        (p.lines_down ? '<br><b class="bad">' + p.lines_down + t(" line(s) stopped now", " lini berhenti sekarang") + "</b>" : "");
      if (markers[p.id]) {
        markers[p.id].setStyle({ color: ring, fillColor: fill }).setPopupContent(popup);
      } else {
        markers[p.id] = window.L.circleMarker([p.lat, p.lon], { radius: 10, color: ring, fillColor: fill, fillOpacity: 0.8, weight: 3 })
          .bindPopup(popup).addTo(map)
          .on("click", function () {
            if (p.worst_line) document.dispatchEvent(new CustomEvent("oee:select", { detail: p.worst_line.line_id }));
          });
      }
    });
  }

  function drawAlerts(alerts, lines) {
    var names = {};
    lines.forEach(function (l) { names[l.id] = l.name + " · " + l.plant; });
    document.getElementById("alert-count").textContent = alerts.length;
    var list = document.getElementById("alerts");
    if (!alerts.length) {
      list.innerHTML = '<li class="empty">' + t("No shift below 65% OEE and no stop over 30 minutes in the last 24 hours.",
        "Tidak ada shift dengan OEE di bawah 65% dan tidak ada henti lebih dari 30 menit dalam 24 jam terakhir.") + "</li>";
      return;
    }
    list.innerHTML = alerts.slice(0, 60).map(function (a) {
      var head, what;
      if (a.type === "low_oee") {
        head = '<span class="status s-low">' + t("OEE below 65%", "OEE di bawah 65%") + "</span> · " + pct(a.oee);
        what = "Shift " + esc(a.shift) + " · A " + pct(a.availability) + " · P " + pct(a.performance) + " · Q " + pct(a.quality);
      } else {
        head = '<span class="status s-down">' + t("Stopped " + a.minutes + " min", "Berhenti " + a.minutes + " menit") + "</span>";
        what = t(a.reason_label.en, a.reason_label.id);
      }
      return '<li data-id="' + esc(a.line_id) + '"><span class="when">' + esc(new Date(a.timestamp).toLocaleString()) + "</span>" +
        "<span><b>" + esc(names[a.line_id] || a.line_id) + "</b> " + head + "</span>" +
        '<span class="what">' + what + "</span></li>";
    }).join("");
  }

  document.getElementById("alerts").addEventListener("click", function (e) {
    var li = e.target.closest("li[data-id]");
    if (li) document.dispatchEvent(new CustomEvent("oee:select", { detail: li.dataset.id }));
  });

  document.addEventListener("oee:data", async function (e) {
    var results = await Promise.all([e.detail.api("plants"), e.detail.api("alerts?hours=24")]);
    drawMap(results[0] || []);
    drawAlerts(results[1] || [], e.detail.lines);
  });

  document.addEventListener("oee:selected", function (e) {
    var m = markers[e.detail.plant_id];
    if (m && map) map.panTo(m.getLatLng());
  });
})();
