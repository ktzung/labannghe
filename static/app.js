(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const PAGE = document.body.dataset.page;
  const GROUP_COLORS = {
    programming: "#2563EB",
    data: "#0F766E",
    web: "#7C3AED",
    cloud: "#0284C7",
    tools: "#64748B",
    design: "#DB2777",
    engineering: "#B45309",
    business: "#059669",
    soft: "#B42318",
    language: "#4F46E5"
  };
  const TYPE_COLORS = {
    state: "#B42318",
    fdi: "#2563EB",
    private: "#0F766E",
    agency: "#B45309",
    unknown: "#64748B"
  };

  const state = {
    scope: "vn",
    days: 30,
    role: "all",
    q: "",
    forum: "all"
  };

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function safeUrl(value) {
    try {
      const url = new URL(String(value || ""), window.location.origin);
      return (url.protocol === "http:" || url.protocol === "https:") ? url.href : "#";
    } catch (e) {
      return "#";
    }
  }

  const fmtNum = new Intl.NumberFormat("vi-VN");
  const fmtPct = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });

  function fmtDate(value) {
    if (!value) return "—";
    const d = String(value).slice(0, 10).split("-");
    return d.length === 3 ? d[2] + "/" + d[1] + "/" + d[0] : String(value);
  }

  function fmtDateTime(value) {
    if (!value) return "chưa có";
    const date = new Date(value);
    if (isNaN(date.getTime())) return String(value);
    return date.toLocaleString("vi-VN", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
    });
  }

  function deltaHtml(value, suffix) {
    if (value == null) return '<span class="delta flat">chưa đủ kỳ trước</span>';
    const cls = value > 0 ? "up" : value < 0 ? "down" : "flat";
    const sign = value > 0 ? "+" : "";
    return '<span class="delta ' + cls + '">' + sign + fmtPct.format(value) + (suffix || " đ") + "</span>";
  }

  function groupDot(group) {
    const color = GROUP_COLORS[group] || "#5B6B84";
    return '<span class="group-dot" style="background:' + color + '"></span>';
  }

  function errorHtml(message) {
    return '<div class="error-box">Không tải được dữ liệu: ' + esc(message) + '. Kiểm tra rằng server đang chạy và đã chạy <code>ingest</code>.</div>';
  }

  function staticKey(path, params) {
    const pairs = Object.keys(params || {})
      .filter(function (key) { return params[key] !== undefined && params[key] !== null && params[key] !== ""; })
      .sort()
      .map(function (key) { return encodeURIComponent(key) + "=" + encodeURIComponent(params[key]); });
    return path + (pairs.length ? "?" + pairs.join("&") : "");
  }

  function staticFallback(path, params) {
    const p = Object.assign({}, params || {});
    if (path === "/api/skills") {
      p.role = "all";
      p.q = "";
      return staticKey(path, p);
    }
    if (path.indexOf("/api/skill/") === 0 || path.indexOf("/api/role/") === 0) {
      return staticKey(path, { scope: "vn", days: 30 });
    }
    if (path === "/api/social/overview") {
      return staticKey(path, { days: 30, forum: "all" });
    }
    return staticKey(path, { scope: "vn", days: 30 });
  }

  async function api(path, params) {
    const staticConfig = window.LABAN_STATIC;
    if (staticConfig && staticConfig.files) {
      let key = staticKey(path, params);
      let file = staticConfig.files[key];
      if (!file) {
        key = staticFallback(path, params);
        file = staticConfig.files[key];
      }
      if (!file) throw new Error("Bản tĩnh không có dữ liệu cho yêu cầu này");
      const root = staticConfig.root || "/";
      const response = await fetch(new URL("api-static/" + file, window.location.origin + root).toString(), {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }
    const url = new URL(path, window.location.origin);
    Object.keys(params || {}).forEach(function (key) {
      if (params[key] !== undefined && params[key] !== null && params[key] !== "") {
        url.searchParams.set(key, params[key]);
      }
    });
    const response = await fetch(url.toString(), { headers: { "Accept": "application/json" } });
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }

  function readState() {
    const params = new URLSearchParams(window.location.search);
    const scope = params.get("scope");
    const days = parseInt(params.get("days"), 10);
    if (scope === "global" || scope === "vn") state.scope = scope;
    if (days === 7 || days === 30 || days === 90) state.days = days;
    const q = params.get("q");
    if (q) state.q = q;
    const role = params.get("role");
    if (role) state.role = role;
    const forum = params.get("forum");
    if (forum) state.forum = forum;
  }

  function writeState(extra) {
    const params = new URLSearchParams(window.location.search);
    params.set("scope", state.scope);
    params.set("days", String(state.days));
    if (state.q) params.set("q", state.q); else params.delete("q");
    if (state.role && state.role !== "all") params.set("role", state.role); else params.delete("role");
    Object.keys(extra || {}).forEach(function (key) {
      if (extra[key]) params.set(key, extra[key]); else params.delete(key);
    });
    const next = window.location.pathname + "?" + params.toString();
    window.history.replaceState(null, "", next);
  }

  function syncControls() {
    $$("#scope-toggle button").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.value === state.scope);
    });
    const days = $("#days-select");
    if (days) days.value = String(state.days);
    const search = $("#skill-search");
    if (search && document.activeElement !== search) search.value = state.q;
  }

  function bindControls(reload) {
    const toggle = $("#scope-toggle");
    if (toggle) {
      toggle.addEventListener("click", function (event) {
        const btn = event.target.closest("button[data-value]");
        if (!btn || btn.dataset.value === state.scope) return;
        state.scope = btn.dataset.value;
        syncControls();
        writeState();
        reload();
      });
    }
    const days = $("#days-select");
    if (days) {
      days.addEventListener("change", function () {
        state.days = parseInt(days.value, 10) || 30;
        syncControls();
        writeState();
        reload();
      });
    }
  }

  function monogram(name) {
    const parts = String(name || "?").trim().split(/\s+/);
    const first = parts[0] ? parts[0][0] : "?";
    const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
    return (first + last).toUpperCase();
  }

  function jobHtml(job) {
    const url = safeUrl(job.url);
    const tags = (job.skills || []).slice(0, 4).map(function (label, index) {
      const id = (job.skill_ids || [])[index];
      return '<button type="button" class="tag" data-skill="' + esc(id) + '">' + esc(label) + "</button>";
    }).join("");
    const meta = [
      esc(job.company || "Không rõ công ty"),
      esc(job.location || (job.remote ? "Remote" : "—")),
      esc(job.level_label || ""),
      job.posted_at ? fmtDate(job.posted_at) : ""
    ].filter(Boolean).join(" · ");
    return '<div class="job-item">' +
      '<div>' +
        '<a class="job-title" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(job.title) + "</a>" +
        '<div class="job-meta">' + meta + "</div>" +
        (tags ? '<div class="tag-row">' + tags + "</div>" : "") +
      "</div>" +
      '<div class="job-side"><div class="job-salary">' + esc(job.salary_text || "Thương lượng") + "</div>" +
        '<div class="job-date">' + esc(job.source || "") + "</div></div>" +
    "</div>";
  }

  function bindJobTags(root) {
    root.addEventListener("click", function (event) {
      const tag = event.target.closest("[data-skill]");
      if (!tag) return;
      event.preventDefault();
      event.stopPropagation();
      openSkill(tag.dataset.skill);
    });
  }

  function lineChart(data, options) {
    const opts = options || {};
    const width = 760;
    const height = opts.height || 220;
    const pad = { l: 34, r: 10, t: 14, b: 24 };
    const counts = data.map(function (d) { return d.count; });
    const max = Math.max.apply(null, counts.concat([1]));
    const step = Math.pow(10, Math.floor(Math.log10(max || 1)));
    const niceMax = Math.ceil(max / (step / 2 || 1)) * (step / 2) || 5;
    const innerW = width - pad.l - pad.r;
    const innerH = height - pad.t - pad.b;
    const x = function (i) { return pad.l + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW); };
    const y = function (v) { return pad.t + innerH - (v / niceMax) * innerH; };
    let line = "";
    let area = "";
    data.forEach(function (d, i) {
      const px = x(i), py = y(d.count);
      line += (i === 0 ? "M" : "L") + px.toFixed(1) + " " + py.toFixed(1) + " ";
      area += (i === 0 ? "M" : "L") + px.toFixed(1) + " " + py.toFixed(1) + " ";
    });
    if (data.length) {
      area += "L" + x(data.length - 1).toFixed(1) + " " + y(0).toFixed(1) + " L" + x(0).toFixed(1) + " " + y(0).toFixed(1) + " Z";
    }
    let grid = "";
    for (let g = 0; g <= 3; g += 1) {
      const value = Math.round((niceMax / 3) * g);
      const py = y(value);
      grid += '<line class="chart-grid-line" x1="' + pad.l + '" y1="' + py + '" x2="' + (width - pad.r) + '" y2="' + py + '"/>';
      grid += '<text class="chart-axis" x="' + (pad.l - 6) + '" y="' + (py + 3) + '" text-anchor="end">' + fmtNum.format(value) + "</text>";
    }
    const labelStep = Math.max(1, Math.ceil(data.length / 6));
    let labels = "";
    data.forEach(function (d, i) {
      if (i % labelStep !== 0 && i !== data.length - 1) return;
      const label = opts.week ? fmtDate(d.week || d.date) : fmtDate(d.date);
      labels += '<text class="chart-axis" x="' + x(i) + '" y="' + (height - 6) + '" text-anchor="middle">' + label + "</text>";
    });
    const dots = [];
    data.forEach(function (d, i) {
      dots.push('<circle class="chart-dot" cx="' + x(i) + '" cy="' + y(d.count) + '" r="2.6"><title>' + fmtDate(d.week || d.date) + ": " + fmtNum.format(d.count) + " " + (opts.unit || "tin") + "</title></circle>");
    });
    const gradientId = "areaGrad" + Math.random().toString(36).slice(2, 8);
    return '<div class="chart-wrap"><svg viewBox="0 0 ' + width + " " + height + '" role="img" aria-label="Biểu đồ ' + esc(opts.unit || "số tin") + ' theo thời gian">' +
      "<defs><linearGradient id=\"" + gradientId + "\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">" +
      '<stop offset="0%" stop-color="#2563EB" stop-opacity=".22"/><stop offset="100%" stop-color="#2563EB" stop-opacity="0"/>' +
      "</linearGradient></defs>" + grid +
      '<path d="' + area + '" fill="url(#' + gradientId + ')"/>' +
      '<path class="chart-line" d="' + line + '"/>' + dots.join("") + labels + "</svg></div>";
  }

  function drawerOpen(eyebrow, title, body) {
    const dialog = $("#drawer");
    $("#drawer-eyebrow").textContent = eyebrow;
    $("#drawer-title").textContent = title;
    $("#drawer-body").innerHTML = body || '<div class="skeleton"></div>';
    if (!dialog.open) dialog.showModal();
    document.body.style.overflow = "hidden";
  }

  function drawerClose() {
    const dialog = $("#drawer");
    if (dialog.open) dialog.close();
    document.body.style.overflow = "";
  }

  function initDrawer() {
    const dialog = $("#drawer");
    if (!dialog) return;
    $("#drawer-close").addEventListener("click", drawerClose);
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) drawerClose();
    });
    dialog.addEventListener("close", function () {
      document.body.style.overflow = "";
    });
    $("#drawer-body").addEventListener("click", function (event) {
      const tag = event.target.closest("[data-skill]");
      if (tag) openSkill(tag.dataset.skill);
      const role = event.target.closest("[data-role-link]");
      if (role) openRole(role.dataset.roleLink);
    });
  }

  async function openSkill(skillId) {
    if (!skillId) return;
    drawerOpen("Kỹ năng", "Đang tải…", '<div class="skeleton"></div>');
    try {
      const d = await api("/api/skill/" + encodeURIComponent(skillId), { scope: state.scope, days: state.days });
      const roles = (d.roles || []).map(function (r) {
        return '<button type="button" class="chip" data-role-link="' + esc(r.id) + '">' + esc(r.label) + " · " + fmtNum.format(r.jobs) + "</button>";
      }).join("");
      const companies = (d.companies || []).map(function (c) {
        return '<div class="company-item"><span class="monogram">' + esc(monogram(c.name)) + "</span><span>" + esc(c.name) + '</span><span class="count">' + fmtNum.format(c.jobs) + "</span></div>";
      }).join("");
      const jobs = (d.jobs_list || []).map(jobHtml).join("");
      const premium = d.salary_premium == null ? "—" : (d.salary_premium > 0 ? "+" : "") + fmtPct.format(d.salary_premium) + "%";
      const kindLabel = d.kind === "knowledge" ? "Kiến thức nền" : "Kỹ năng";
      const body =
        '<div class="stat-row">' +
          '<div class="stat-box"><strong>' + fmtNum.format(d.jobs) + "</strong><small>tin yêu cầu</small></div>" +
          '<div class="stat-box"><strong>' + fmtPct.format(d.share) + "%</strong><small>tỷ lệ trong phạm vi</small></div>" +
          '<div class="stat-box"><strong>' + esc(d.median_salary_text || "—") + "</strong><small>lương trung vị</small></div>" +
        "</div>" +
        (d.median_salary ? '<p class="tiny-note">So với trung vị lương chung: <strong>' + esc(premium) + "</strong>. Chỉ tính tin Việt Nam có công bố lương.</p>" : "") +
        '<div class="drawer-section"><h3>Xu hướng 12 tuần</h3>' + lineChart(d.trend || [], { week: true, height: 190 }) + "</div>" +
        '<div class="drawer-section"><h3>Vị trí dùng nhiều</h3><div class="tag-row">' + (roles || '<span class="drawer-empty">Chưa đủ dữ liệu</span>') + "</div></div>" +
        '<div class="drawer-section"><h3>Doanh nghiệp nhắc nhiều</h3>' + (companies || '<p class="drawer-empty">Chưa đủ dữ liệu</p>') + "</div>" +
        '<div class="drawer-section"><h3>Tin mẫu</h3>' + (jobs || '<p class="drawer-empty">Chưa có tin.</p>') + "</div>";
      drawerOpen(kindLabel, d.label, body);
    } catch (err) {
      drawerOpen("Kỹ năng", "Lỗi", errorHtml(err.message));
    }
  }

  async function openRole(roleId) {
    if (!roleId) return;
    drawerOpen("Vị trí", "Đang tải…", '<div class="skeleton"></div>');
    try {
      const d = await api("/api/role/" + encodeURIComponent(roleId), { scope: state.scope, days: state.days });
      const skills = (d.skills || []).map(function (s) {
        return '<button type="button" class="chip" data-skill="' + esc(s.id) + '">' + esc(s.label) + " · " + fmtPct.format(s.share) + "%</button>";
      }).join("");
      const knowledge = (d.knowledge || []).map(function (s) {
        return '<button type="button" class="chip" data-skill="' + esc(s.id) + '">' + esc(s.label) + " · " + fmtPct.format(s.share) + "%</button>";
      }).join("");
      const standards = ((d.standards || {}).items || []).map(function (s) {
        const evidence = (s.evidence || []).slice(0, 2).map(function (e) {
          const link = safeUrl(e.url);
          return '<blockquote class="evidence-quote">“' + esc(e.text) + '”' +
            '<a href="' + esc(link) + '" target="_blank" rel="noopener noreferrer">' + esc(e.job_title || "Tin gốc") + " ↗</a></blockquote>";
        }).join("");
        return '<div class="standard-item">' +
          '<div class="standard-head">' +
            '<button type="button" class="chip" data-skill="' + esc(s.id) + '">' + esc(s.label) + "</button>" +
            '<span class="standard-stat"><strong>' + fmtPct.format(s.strong_share) + "%</strong> có bằng chứng trong mô tả/yêu cầu</span>" +
          "</div>" +
          '<div class="standard-bar"><i style="width:' + Math.max(2, Math.min(100, s.strong_share)) + '%"></i></div>' +
          '<div class="standard-meta">' + fmtNum.format(s.strong_jobs) + "/" + fmtNum.format(d.jobs) + " tin nhắc tới kỹ năng này</div>" +
          (evidence || '<p class="drawer-empty">Chưa trích được câu yêu cầu cụ thể.</p>') +
        "</div>";
      }).join("");
      const plan = (d.plan || []).map(function (p) { return "<li>" + esc(p) + "</li>"; }).join("");
      const levels = (d.levels || []).map(function (l) {
        return '<div class="company-item"><span>' + esc(l.label) + '</span><span class="count">' + fmtNum.format(l.jobs) + "</span></div>";
      }).join("");
      const companies = (d.companies || []).map(function (c) {
        return '<div class="company-item"><span class="monogram">' + esc(monogram(c.name)) + "</span><span>" + esc(c.name) + "</span>" +
          (c.tier === 2 ? '<span class="tier-badge">top</span>' : "") +
          '<span class="count">' + fmtNum.format(c.jobs) + "</span></div>";
      }).join("");
      const cities = (d.cities || []).map(function (c) {
        return '<span class="chip">' + esc(c.name) + " · " + fmtNum.format(c.jobs) + "</span>";
      }).join("");
      const jobs = (d.jobs_list || []).map(jobHtml).join("");
      const body =
        '<div class="stat-row">' +
          '<div class="stat-box"><strong>' + fmtNum.format(d.jobs) + "</strong><small>tin</small></div>" +
          '<div class="stat-box"><strong>' + fmtPct.format(d.detail_coverage || 0) + "%</strong><small>tin có mô tả/yêu cầu</small></div>" +
          '<div class="stat-box"><strong>' + esc(d.median_salary_text || "—") + "</strong><small>lương trung vị</small></div>" +
        "</div>" +
        '<div class="drawer-section"><h3>Tiêu chuẩn nghề</h3>' +
          '<p class="tiny-note">Xếp theo số tin có bằng chứng trong phần mô tả công việc hoặc yêu cầu ứng viên, không chỉ theo tiêu đề.</p>' +
          '<div class="standard-list">' + (standards || '<p class="drawer-empty">Chưa đủ mô tả/yêu cầu để rút ra tiêu chuẩn.</p>') + "</div></div>" +
        '<div class="drawer-section"><h3>Kỹ năng được nhắc</h3><div class="tag-row">' + (skills || '<span class="drawer-empty">Chưa đủ dữ liệu</span>') + "</div></div>" +
        (knowledge ? '<div class="drawer-section"><h3>Kiến thức nền được nhắc</h3><div class="tag-row">' + knowledge + "</div></div>" : "") +
        '<div class="drawer-section"><h3>Ba sản phẩm cho 90 ngày</h3><ol class="plan-list">' + (plan || "<li>Chưa có gợi ý cho vị trí này.</li>") + "</ol></div>" +
        '<div class="drawer-section"><h3>Cấp bậc</h3>' + (levels || '<p class="drawer-empty">Chưa đủ dữ liệu</p>') + "</div>" +
        '<div class="drawer-section"><h3>Doanh nghiệp</h3>' + (companies || '<p class="drawer-empty">Chưa đủ dữ liệu</p>') + "</div>" +
        '<div class="drawer-section"><h3>Địa điểm</h3><div class="tag-row">' + (cities || '<span class="drawer-empty">Chưa đủ dữ liệu</span>') + "</div></div>" +
        '<div class="drawer-section"><h3>Tin mẫu</h3>' + (jobs || '<p class="drawer-empty">Chưa có tin.</p>') + "</div>";
      drawerOpen("Chọn theo nhiệm vụ", d.label, body);
    } catch (err) {
      drawerOpen("Vị trí", "Lỗi", errorHtml(err.message));
    }
  }

  function kpiCard(label, value, sub) {
    return '<div class="kpi-card"><div class="kpi-label">' + esc(label) + "</div>" +
      '<div class="kpi-value">' + value + "</div>" +
      '<div class="kpi-sub">' + sub + "</div></div>";
  }

  async function loadSocialTeaser() {
    const box = $("#social-teaser");
    if (!box) return;
    try {
      const d = await api("/api/social/overview", { days: state.days, forum: "all" });
      const k = d.kpis || {};
      const topics = (d.topics || []).slice(0, 3).map(function (t) {
        return '<div class="company-item"><span>' + esc(t.label) + '</span><span class="count">' + fmtNum.format(t.threads) + " chủ đề</span></div>";
      }).join("");
      const hot = (d.hot_threads || [])[0];
      box.innerHTML =
        '<div class="stat-row">' +
          '<div class="stat-box"><strong>' + fmtNum.format(k.threads || 0) + "</strong><small>chủ đề</small></div>" +
          '<div class="stat-box"><strong>' + fmtNum.format(k.discussions || 0) + "</strong><small>thảo luận</small></div>" +
          '<div class="stat-box"><strong>' + fmtNum.format(k.replies || 0) + "</strong><small>phản hồi</small></div>" +
        "</div>" +
        '<div class="company-list">' + (topics || '<div class="empty">Chưa đủ dữ liệu.</div>') + "</div>" +
        (hot ? '<p class="thread-excerpt"><a class="job-title" href="' + esc(safeUrl(hot.url)) + '" target="_blank" rel="noopener noreferrer">' + esc(hot.title) + "</a></p>" : "");
      if (d.last_ingest) $("#social-teaser-note").textContent = "RSS công khai · cập nhật " + fmtDateTime(d.last_ingest) + " · không lưu tên người đăng.";
    } catch (err) {
      box.innerHTML = '<div class="empty">Chưa tải được tín hiệu cộng đồng.</div>';
    }
  }

  async function initOverview() {
    const grid = $("#kpi-grid");
    if (!initOverview.bound) {
      initOverview.bound = true;
      $("#top-skills").addEventListener("click", function (event) {
        const row = event.target.closest("[data-skill]");
        if (row) openSkill(row.dataset.skill);
      });
      $("#rising-skills").addEventListener("click", function (event) {
        const row = event.target.closest("[data-skill]");
        if (row) openSkill(row.dataset.skill);
      });
      $("#role-list").addEventListener("click", function (event) {
        const row = event.target.closest("[data-role-link]");
        if (row) openRole(row.dataset.roleLink);
      });
      bindJobTags($("#latest-jobs"));
    }
    try {
      const d = await api("/api/overview", { scope: state.scope, days: state.days });
      const k = d.kpis;
      $("#hero-jobs").textContent = fmtNum.format(k.jobs);
      $("#hero-window").textContent = String(state.days);
      $("#hero-vn").textContent = fmtNum.format((d.db && d.db.vn) || 0);
      $("#hero-global").textContent = fmtNum.format((d.db && d.db.global) || 0);
      $("#hero-skills").textContent = fmtNum.format(k.skills_tracked);
      $("#hero-updated").textContent = d.last_ingest ? "Cập nhật " + fmtDateTime(d.last_ingest) : "Chưa có lần cập nhật";
      $("#window-note").textContent = d.window ? "Từ " + fmtDate(d.window.start) + " đến " + fmtDate(d.window.end) : "";

      let salaryHtml, salarySub;
      if (state.scope === "global") {
        salaryHtml = k.global_median_usd ? "$" + fmtNum.format(k.global_median_usd) + 'k<small>/năm</small>' : "—";
        salarySub = "Trung vị tin quốc tế có công bố lương";
      } else {
        salaryHtml = esc(k.vn_median_salary_text || "—");
        salarySub = "Trung vị tin Việt Nam · " + fmtPct.format(k.salary_coverage || 0) + "% tin có lương";
      }
      grid.innerHTML =
        kpiCard("Tin trong " + state.days + " ngày", fmtNum.format(k.jobs), deltaHtml(k.jobs_change, "%") + " so kỳ trước") +
        kpiCard("Doanh nghiệp", fmtNum.format(k.companies), "Số công ty khác nhau trong phạm vi") +
        kpiCard("Lương trung vị", salaryHtml, salarySub) +
        kpiCard("Tin mới hôm nay", fmtNum.format(k.new_today), "Tổng kho: " + fmtNum.format((d.db && d.db.total) || 0) + " tin");

      const maxShare = Math.max.apply(null, (d.top_skills || []).map(function (s) { return s.share; }).concat([1]));
      $("#top-skills").innerHTML = (d.top_skills || []).map(function (s) {
        return '<div class="bar-row" data-skill="' + esc(s.id) + '">' +
          '<div class="bar-label">' + groupDot(s.group) + esc(s.label) + "</div>" +
          '<div class="bar-track"><div class="bar-fill" style="width:' + Math.max(2, (s.share / maxShare) * 100) + "%\"></div></div>" +
          '<div class="bar-value"><strong>' + fmtPct.format(s.share) + "%</strong></div></div>";
      }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>';
      $("#skills-note").textContent = fmtNum.format(d.top_skills && d.top_skills.length ? d.top_skills[0].jobs : 0) + " tin cho kỹ năng dẫn đầu";

      const details = d.details || {};
      $("#detail-coverage-note").textContent = fmtPct.format(details.any_coverage || 0) + "% tin có mô tả/yêu cầu";
      const standards = d.top_standards || [];
      const standardMax = Math.max.apply(null, standards.map(function (s) { return s.strong_share; }).concat([1]));
      $("#top-standards").innerHTML = standards.map(function (s) {
        return '<div class="bar-row" data-skill="' + esc(s.id) + '">' +
          '<div class="bar-label">' + groupDot(s.group) + esc(s.label) + "</div>" +
          '<div class="bar-track"><div class="bar-fill" style="width:' + Math.max(2, (s.strong_share / standardMax) * 100) + '%"></div></div>' +
          '<div class="bar-value"><strong>' + fmtPct.format(s.strong_share) + "%</strong><small>" + fmtNum.format(s.strong_jobs) + " tin</small></div></div>";
      }).join("") || '<div class="empty">Chưa đủ mô tả/yêu cầu để rút ra tiêu chuẩn.</div>';
      if (!initOverview.standardsBound) {
        initOverview.standardsBound = true;
        $("#top-standards").addEventListener("click", function (event) {
          const row = event.target.closest("[data-skill]");
          if (row) openSkill(row.dataset.skill);
        });
      }
      loadSocialTeaser();

      $("#rising-skills").innerHTML = (d.rising || []).map(function (s) {
        return '<div class="rising-item" data-skill="' + esc(s.id) + '">' +
          '<div class="rising-name">' + esc(s.label) + '</div><div class="rising-delta">+' + fmtPct.format(s.delta) + " đ</div>" +
          '<div class="rising-meta">' + esc(s.group_label) + " · " + fmtNum.format(s.jobs) + " tin</div></div>";
      }).join("") || '<div class="empty">Cần thêm dữ liệu kỳ trước để tính xu hướng.</div>';

      $("#top-companies").innerHTML = (d.top_companies || []).map(function (c) {
        return '<div class="company-item"><span class="monogram">' + esc(monogram(c.name)) + "</span><span>" + esc(c.name) + "</span>" +
          (c.tier === 2 ? '<span class="tier-badge">top</span>' : "") +
          '<span class="count">' + fmtNum.format(c.jobs) + "</span></div>";
      }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>';

      $("#daily-chart").innerHTML = lineChart(d.daily || []);

      $("#role-list").innerHTML = (d.roles || []).map(function (r) {
        return '<div class="role-mini" data-role-link="' + esc(r.id) + '">' +
          '<span class="role-mini-name">' + esc(r.label) + "</span>" +
          '<span class="role-mini-count">' + fmtNum.format(r.jobs) + " · " + fmtPct.format(r.share) + "%</span></div>";
      }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>';

      const locations = d.top_locations || {};
      $("#locations-note").textContent = state.scope === "global"
        ? "Chỉ phân tích tin Việt Nam"
        : fmtPct.format(locations.coverage || 0) + "% tin có địa điểm";
      const locationMax = Math.max.apply(null, (locations.items || []).map(function (x) { return x.share; }).concat([1]));
      $("#top-locations").innerHTML = (locations.items || []).map(function (x) {
        return '<div class="bar-row static">' +
          '<div class="bar-label"><span class="group-dot" style="background:#0284C7"></span>' + esc(x.name) + "</div>" +
          '<div class="bar-track"><div class="bar-fill" style="width:' + Math.max(2, (x.share / locationMax) * 100) + '%"></div></div>' +
          '<div class="bar-value"><strong>' + fmtNum.format(x.jobs) + "</strong></div></div>";
      }).join("") || '<div class="empty">' + (state.scope === "global" ? "Chuyển sang Việt Nam để xem địa bàn." : "Chưa có tin gắn địa điểm.") + "</div>";

      const types = d.company_types || {};
      $("#company-types-note").textContent = state.scope === "global"
        ? "Chỉ phân tích tin Việt Nam"
        : fmtPct.format(types.coverage || 0) + "% tin xác định được";
      const typeMax = Math.max.apply(null, (types.items || []).map(function (x) { return x.jobs; }).concat([1]));
      $("#company-types").innerHTML = (types.items || []).map(function (x) {
        const color = TYPE_COLORS[x.id] || "#64748B";
        return '<div class="bar-row static" title="' + esc(x.label + " · lương trung vị " + (x.median_salary_text || "—")) + '">' +
          '<div class="bar-label"><span class="group-dot" style="background:' + color + '"></span>' + esc(x.short_label || x.label) + "</div>" +
          '<div class="bar-track"><div class="bar-fill" style="width:' + Math.max(2, (x.jobs / typeMax) * 100) + '%;background:' + color + '"></div></div>' +
          '<div class="bar-value"><strong>' + fmtNum.format(x.jobs) + "</strong></div></div>";
      }).join("") || '<div class="empty">' + (state.scope === "global" ? "Chuyển sang Việt Nam để xem cơ cấu." : "Chưa đủ dữ liệu.") + "</div>";

      $("#latest-jobs").innerHTML = (d.latest_jobs || []).map(jobHtml).join("") || '<div class="empty">Chưa có tin.</div>';
    } catch (err) {
      grid.innerHTML = errorHtml(err.message);
    }
  }

  function renderSkillRows(items) {
    const body = $("#skills-body");
    if (!items.length) {
      body.innerHTML = '<tr><td colspan="7"><div class="empty">Không tìm thấy kỹ năng phù hợp.</div></td></tr>';
      return;
    }
    const maxShare = Math.max.apply(null, items.map(function (s) { return s.share; }).concat([1]));
    body.innerHTML = items.map(function (s) {
      const premium = s.salary_premium == null ? '<span class="zero">—</span>' :
        '<span class="' + (s.salary_premium >= 0 ? "pos" : "neg") + '">' + (s.salary_premium > 0 ? "+" : "") + fmtPct.format(s.salary_premium) + "%</span>";
      const delta = s.delta == null ? '<span class="zero">—</span>' :
        '<span class="' + (s.delta >= 0 ? "pos" : "neg") + '">' + (s.delta > 0 ? "+" : "") + fmtPct.format(s.delta) + " đ</span>";
      return '<tr data-skill="' + esc(s.id) + '">' +
        '<td><div class="skill-name">' + groupDot(s.group) + " " + esc(s.label) + "</div><div class=\"skill-group\">" + esc(s.group_label) + "</div></td>" +
        '<td class="skill-group">' + esc(s.group_label) + "</td>" +
        '<td class="num">' + fmtNum.format(s.jobs) + "</td>" +
        '<td class="num" title="' + fmtNum.format(s.strong_jobs || 0) + ' tin có bằng chứng trong thẻ, mô tả hoặc yêu cầu"><span class="mini-bar"><i style="width:' + Math.max(3, (s.share / maxShare) * 100) + '%"></i></span>' + fmtPct.format(s.share) + "%</td>" +
        '<td class="num">' + delta + "</td>" +
        '<td class="num">' + esc(s.median_salary_text || "—") + "</td>" +
        '<td class="num">' + premium + "</td></tr>";
    }).join("");
  }

  function renderKnowledgeRows(items) {
    const body = $("#knowledge-body");
    if (!body) return;
    if (!items.length) {
      body.innerHTML = '<tr><td colspan="6"><div class="empty">Không tìm thấy kiến thức phù hợp.</div></td></tr>';
      return;
    }
    const maxShare = Math.max.apply(null, items.map(function (s) { return s.share; }).concat([1]));
    body.innerHTML = items.map(function (s) {
      const premium = s.salary_premium == null ? '<span class="zero">—</span>' :
        '<span class="' + (s.salary_premium >= 0 ? "pos" : "neg") + '">' + (s.salary_premium > 0 ? "+" : "") + fmtPct.format(s.salary_premium) + "%</span>";
      return '<tr data-skill="' + esc(s.id) + '">' +
        '<td><div class="skill-name">' + groupDot(s.group) + " " + esc(s.label) + "</div><div class=\"skill-group\">" + esc(s.group_label) + "</div></td>" +
        '<td class="skill-group">' + esc(s.group_label) + "</td>" +
        '<td class="num">' + fmtNum.format(s.jobs) + "</td>" +
        '<td class="num"><span class="mini-bar"><i style="width:' + Math.max(3, (s.share / maxShare) * 100) + '%"></i></span>' + fmtPct.format(s.share) + "%</td>" +
        '<td class="num">' + esc(s.median_salary_text || "—") + "</td>" +
        '<td class="num">' + premium + "</td></tr>";
    }).join("");
  }

  async function initSkills() {
    const search = $("#skill-search");
    const roleSelect = $("#role-filter");
    let timer = null;

    async function load() {
      $("#skills-count").textContent = "Đang tải…";
      if ($("#knowledge-count")) $("#knowledge-count").textContent = "Đang tải…";
      try {
        const [d, knowledgeData] = await Promise.all([
          api("/api/skills", { scope: state.scope, days: state.days, role: state.role, q: state.q, limit: 300, kind: "skill" }),
          api("/api/skills", { scope: state.scope, days: state.days, role: state.role, q: state.q, limit: 120, kind: "knowledge" })
        ]);
        renderSkillRows(d.items || []);
        renderKnowledgeRows(knowledgeData.items || []);
        $("#skills-count").textContent = fmtNum.format((d.items || []).length) + " kỹ năng";
        if ($("#knowledge-count")) {
          $("#knowledge-count").textContent = fmtNum.format((knowledgeData.items || []).length) + " kiến thức nền";
        }
        if (roleSelect && roleSelect.options.length <= 1) {
          (d.roles || []).forEach(function (r) {
            const option = document.createElement("option");
            option.value = r.id;
            option.textContent = r.label;
            roleSelect.appendChild(option);
          });
          roleSelect.value = state.role;
        }
      } catch (err) {
        $("#skills-body").innerHTML = '<tr><td colspan="8">' + errorHtml(err.message) + "</td></tr>";
        if ($("#knowledge-body")) {
          $("#knowledge-body").innerHTML = '<tr><td colspan="6">' + errorHtml(err.message) + "</td></tr>";
        }
        $("#skills-count").textContent = "";
        if ($("#knowledge-count")) $("#knowledge-count").textContent = "";
      }
    }

    if (roleSelect) {
      roleSelect.value = state.role;
      roleSelect.addEventListener("change", function () {
        state.role = roleSelect.value;
        writeState();
        load();
      });
    }
    if (search) {
      search.value = state.q;
      search.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
          state.q = search.value.trim();
          writeState();
          load();
        }, 260);
      });
    }
    $("#skills-body").addEventListener("click", function (event) {
      const row = event.target.closest("[data-skill]");
      if (row) openSkill(row.dataset.skill);
    });
    if ($("#knowledge-body")) {
      $("#knowledge-body").addEventListener("click", function (event) {
        const row = event.target.closest("[data-skill]");
        if (row) openSkill(row.dataset.skill);
      });
    }
    bindControls(load);
    await load();
  }

  async function initRoles() {
    const grid = $("#role-grid");
    if (!initRoles.bound) {
      initRoles.bound = true;
      grid.addEventListener("click", function (event) {
        const card = event.target.closest("[data-role-link]");
        if (!card) return;
        writeState({ role: card.dataset.roleLink });
        openRole(card.dataset.roleLink);
      });
    }
    let firstLoad = true;
    async function load() {
      try {
        const d = await api("/api/roles", { scope: state.scope, days: state.days });
        $("#roles-note").textContent = fmtNum.format(d.total_jobs) + " tin đã phân loại";
        grid.innerHTML = (d.items || []).map(function (r) {
          const standards = (r.standard_skills || []).slice(0, 3).map(function (s) {
            return '<span class="chip chip-standard">' + esc(s.label) + " · " + fmtPct.format(s.strong_share) + "%</span>";
          }).join("");
          return '<article class="role-card" data-role-link="' + esc(r.id) + '">' +
            "<h3>" + esc(r.label) + "</h3>" +
            '<div class="role-count">' + fmtNum.format(r.jobs) + " tin · " + fmtPct.format(r.share) + "% phạm vi</div>" +
            '<div class="role-share"><div class="track"><i style="width:' + Math.min(100, r.share * 2.2) + '%"></i></div><span>' + fmtPct.format(r.share) + "%</span></div>" +
            '<div class="role-skills">' + (standards || '<span class="chip">Chưa đủ dữ liệu</span>') + "</div>" +
            '<div class="role-coverage">' + fmtPct.format(r.detail_coverage || 0) + "% tin có mô tả/yêu cầu · " + fmtNum.format(r.detail_jobs || 0) + " tin" + "</div>" +
            '<div class="role-salary">Lương trung vị: <strong>' + esc(r.median_salary_text || "—") + "</strong></div>" +
          "</article>";
        }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>';
        if (firstLoad) {
          firstLoad = false;
          const params = new URLSearchParams(window.location.search);
          if (params.get("role")) openRole(params.get("role"));
        }
      } catch (err) {
        grid.innerHTML = errorHtml(err.message);
      }
    }
    bindControls(load);
    await load();
  }

  function socialTagBars(items, color) {
    const max = Math.max.apply(null, items.map(function (x) { return x.threads; }).concat([1]));
    return items.map(function (x) {
      const delta = x.delta == null ? "" : '<span class="tag-delta">' + (x.delta > 0 ? "+" : "") + fmtPct.format(x.delta) + " đ</span>";
      return '<div class="bar-row static">' +
        '<div class="bar-label"><span class="group-dot" style="background:' + color + '"></span>' + esc(x.label) + delta + "</div>" +
        '<div class="bar-track"><div class="bar-fill" style="width:' + Math.max(3, (x.threads / max) * 100) + "%;background:" + color + '"></div></div>' +
        '<div class="bar-value"><strong>' + fmtNum.format(x.threads) + "</strong><small>" + fmtPct.format(x.share) + "%</small></div></div>";
    }).join("") || '<div class="empty">Chưa đủ dữ liệu trong phạm vi.</div>';
  }

  function socialThreadHtml(t) {
    const url = safeUrl(t.url);
    const marks = (t.topics || []).concat(t.issues || []).slice(0, 4).map(function (label) {
      return '<span class="chip chip-small">' + esc(label) + "</span>";
    }).join("");
    return '<div class="thread-item">' +
      '<a class="job-title" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(t.title) + "</a>" +
      '<div class="job-meta">' + esc(t.forum) + " · " + fmtNum.format(t.replies) + " phản hồi · " + fmtDate(t.posted_at) + "</div>" +
      (t.excerpt ? '<p class="thread-excerpt">' + esc(t.excerpt) + "</p>" : "") +
      (marks ? '<div class="tag-row">' + marks + "</div>" : "") +
    "</div>";
  }

  async function initSocial() {
    const kpis = $("#social-kpis");
    const topics = $("#social-topics");
    const issues = $("#social-issues");
    const threads = $("#social-threads");
    const skillBody = $("#social-skills tbody");
    const chart = $("#social-chart");
    const forumToggle = $("#social-forum");
    const daysSelect = $("#social-days");

    function syncSocialControls() {
      $$("#social-forum button").forEach(function (btn) {
        btn.classList.toggle("active", btn.dataset.value === state.forum);
      });
      if (daysSelect) daysSelect.value = String(state.days);
    }

    async function load() {
      $("#social-mode").textContent = "Đang tải…";
      try {
        const d = await api("/api/social/overview", { days: state.days, forum: state.forum });
        const k = d.kpis || {};
        kpis.innerHTML =
          kpiCard("Chủ đề trong " + state.days + " ngày", fmtNum.format(k.threads || 0), fmtNum.format(k.forums || 0) + " diễn đàn") +
          kpiCard("Thảo luận", fmtNum.format(k.discussions || 0), "Đã tách " + fmtNum.format(k.job_ads || 0) + " tin tuyển dụng") +
          kpiCard("Lượt phản hồi", fmtNum.format(k.replies || 0), "Tổng phản hồi ghi nhận từ RSS") +
          kpiCard("Có nhắc kỹ năng", fmtNum.format(k.with_skills || 0), "Chủ đề khớp với danh mục kỹ năng");
        $("#social-mode").textContent = (d.mode === "file" ? "Nguồn: RSS snapshot" : d.mode === "http" ? "Nguồn: RSS trực tiếp" : "Nguồn: RSS") +
          (d.last_ingest ? " · cập nhật " + fmtDateTime(d.last_ingest) : " · chưa có lần chạy");

        topics.innerHTML = socialTagBars(d.topics || [], "#2563EB");
        issues.innerHTML = socialTagBars(d.issues || [], "#B42318");
        threads.innerHTML = (d.hot_threads || []).map(socialThreadHtml).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>';
        chart.innerHTML = lineChart(d.daily || [], { unit: "chủ đề" });

        const skills = d.skills || [];
        skillBody.innerHTML = skills.map(function (s) {
          const gap = s.gap == null ? '<span class="zero">—</span>' :
            '<span class="' + (s.gap > 0 ? "pos" : s.gap < 0 ? "neg" : "zero") + '">' + (s.gap > 0 ? "+" : "") + fmtPct.format(s.gap) + " đ</span>";
          return '<tr data-skill="' + esc(s.id) + '">' +
            '<td><div class="skill-name">' + groupDot(s.group) + " " + esc(s.label) + "</div></td>" +
            '<td class="skill-group">' + esc(s.group_label) + "</td>" +
            '<td class="num">' + fmtNum.format(s.threads) + "</td>" +
            '<td class="num">' + fmtPct.format(s.share) + "%</td>" +
            '<td class="num">' + fmtPct.format(s.job_share || 0) + "%</td>" +
            '<td class="num">' + gap + "</td></tr>";
        }).join("") || '<tr><td colspan="6"><div class="empty">Chưa đủ dữ liệu.</div></td></tr>';
      } catch (err) {
        kpis.innerHTML = errorHtml(err.message);
        $("#social-mode").textContent = "";
      }
    }

    if (forumToggle) {
      forumToggle.addEventListener("click", function (event) {
        const btn = event.target.closest("button[data-value]");
        if (!btn || btn.dataset.value === state.forum) return;
        state.forum = btn.dataset.value;
        syncSocialControls();
        writeState({ forum: state.forum === "all" ? "" : state.forum });
        load();
      });
    }
    if (daysSelect) {
      daysSelect.addEventListener("change", function () {
        state.days = parseInt(daysSelect.value, 10) || 30;
        writeState({ forum: state.forum === "all" ? "" : state.forum });
        load();
      });
    }
    skillBody.addEventListener("click", function (event) {
      const row = event.target.closest("[data-skill]");
      if (row) openSkill(row.dataset.skill);
    });
    syncSocialControls();
    await load();
  }

  async function initSources() {
    try {
      const d = await api("/api/method");
      $("#source-cards").innerHTML = (d.source_list || []).map(function (s) {
        const link = safeUrl(s.url);
        return '<article class="source-card">' +
          '<div class="src-top"><span class="monogram">' + esc(monogram(s.label)) + "</span>" +
          '<h3><a href="' + esc(link) + '" target="_blank" rel="noopener noreferrer">' + esc(s.label) + " ↗</a></h3></div>" +
          "<p>" + esc(s.note) + "</p>" +
          '<div class="src-meta"><span>' + (s.last_run ? fmtDateTime(s.last_run) : "chưa chạy") + "</span><span>" + fmtNum.format(s.fetched) + " tin</span></div>" +
        "</article>";
      }).join("");
      $("#source-runs").innerHTML = (d.source_list || []).map(function (s) {
        return "<tr><td><strong>" + esc(s.label) + '</strong><div class="skill-group">' + esc(s.id) + "</div></td>" +
          '<td class="skill-group">' + esc(s.note) + "</td>" +
          '<td class="num">' + fmtNum.format(s.fetched) + "</td>" +
          '<td class="num">' + (s.errors ? '<span class="neg">' + s.errors + "</span>" : '<span class="zero">0</span>') + "</td>" +
          "<td>" + (s.last_run ? fmtDateTime(s.last_run) : "—") + "</td></tr>";
      }).join("");
      $("#unavailable-sources").innerHTML = (d.unavailable_sources || []).map(function (s) {
        return "<li><a href=\"" + esc(safeUrl(s.url)) + "\" target=\"_blank\" rel=\"noopener noreferrer\">" +
          esc(s.label) + " ↗</a> — " + esc(s.reason) + "</li>";
      }).join("");
      const db = d.db || {};
      $("#db-stats").innerHTML =
        "<div><strong>" + fmtNum.format(db.total || 0) + "</strong><small>tin đã lưu</small></div>" +
        "<div><strong>" + fmtNum.format(db.vn || 0) + "</strong><small>tin Việt Nam</small></div>" +
        "<div><strong>" + fmtNum.format(db.global || 0) + "</strong><small>tin toàn cầu</small></div>" +
        "<div><strong>" + fmtNum.format(db.companies || 0) + "</strong><small>doanh nghiệp</small></div>";
      $("#last-run").textContent = d.last_ingest ? "Lần chạy gần nhất: " + fmtDateTime(d.last_ingest) : "Chưa chạy lần nào.";
      const social = d.social || {};
      if (social.db && social.db.threads) {
        $("#last-run").textContent += " · Cộng đồng: " + fmtNum.format(social.db.threads) + " chủ đề, " + fmtNum.format(social.db.discussions) + " thảo luận.";
      }
    } catch (err) {
      $("#source-cards").innerHTML = errorHtml(err.message);
    }
  }

  async function initReport() {
    async function load() {
      try {
        const d = await api("/api/export", { scope: state.scope, days: state.days });
        const k = d.kpis;
        const scopeLabel = state.scope === "global" ? "toàn cầu" : "Việt Nam";
        const details = d.details || {};
        const standards = d.top_standards || d.top_skills || [];
        $("#slide-title").textContent = "Kỹ năng có bằng chứng trong mô tả tuyển dụng";
        $("#slide-sub").textContent = "Phân tích " + fmtNum.format(k.jobs) + " tin " + scopeLabel + " trong " + state.days + " ngày; " + fmtPct.format(details.any_coverage || 0) + "% tin có mô tả/yêu cầu chi tiết. Cập nhật " + fmtDate(d.last_ingest) + ".";
        $("#slide-kpis").innerHTML =
          "<div><strong>" + fmtNum.format(k.jobs) + "</strong><small>tin tuyển dụng</small></div>" +
          "<div><strong>" + fmtNum.format(k.companies) + "</strong><small>doanh nghiệp</small></div>" +
          "<div><strong>" + fmtPct.format(details.any_coverage || 0) + "%</strong><small>tin có mô tả/yêu cầu</small></div>" +
          "<div><strong>" + fmtPct.format((standards[0] || {}).strong_share || 0) + "%</strong><small>kỹ năng dẫn đầu</small></div>";
        const top = standards;
        const maxShare = Math.max.apply(null, top.map(function (s) { return s.strong_share || s.share || 0; }).concat([1]));
        $("#slide-chart-title").textContent = "Tỷ lệ tin có bằng chứng trong mô tả/yêu cầu";
        $("#slide-skills").innerHTML = top.slice(0, 7).map(function (s) {
          const share = s.strong_share == null ? s.share : s.strong_share;
          return '<div class="slide-bar"><span>' + esc(s.label) + '</span><span class="track"><i style="width:' + Math.max(3, (share / maxShare) * 100) + '%"></i></span><span>' + fmtPct.format(share) + "%</span></div>";
        }).join("");
        $("#slide-rising").innerHTML = (d.rising || []).slice(0, 5).map(function (s) {
          return "<span>" + esc(s.label) + " +" + fmtPct.format(s.delta) + " đ</span>";
        }).join("") || "<span>chưa đủ dữ liệu</span>";
        $("#slide-roles").innerHTML = (d.roles || []).slice(0, 5).map(function (r) {
          return "<div><b>" + esc(r.label) + "</b> · " + fmtNum.format(r.jobs) + " tin</div>";
        }).join("");
        const lead = top[0];
        const rise = (d.rising || [])[0];
        const leadShare = lead ? (lead.strong_share == null ? lead.share : lead.strong_share) : 0;
        $("#slide-reading").innerHTML = lead ?
          "<strong>Đọc nhanh:</strong> " + esc(lead.label) + " xuất hiện trong " + fmtPct.format(leadShare) + "% tin có mô tả/yêu cầu chi tiết." +
          (rise ? " " + esc(rise.label) + " tăng " + fmtPct.format(rise.delta) + " điểm phần trăm so với kỳ trước." : "") +
          " Dùng bảng này để chọn 3 kỹ năng cần tích luỹ bằng chứng trong 90 ngày."
          : "Chưa đủ dữ liệu.";
        $("#slide-source-text").textContent = "17 nguồn tuyển dụng công khai; kỹ năng chỉ tính khi có trong thẻ, mô tả hoặc yêu cầu. Lương chỉ tính tin Việt Nam có công bố mức lương.";
        $("#slide-foot-meta").textContent = "Cập nhật " + fmtDate(d.last_ingest) + " · " + fmtNum.format((d.db || {}).total || 0) + " tin trong kho";
      } catch (err) {
        $("#slide-sub").textContent = "Không tải được dữ liệu: " + err.message;
      }
    }
    $("#print-btn").addEventListener("click", function () { window.print(); });
    bindControls(load);
    await load();
  }

  async function initFlipbook() {
    const live = $("#fb-page");
    const book = $("#fb-book");
    const dots = $("#fb-dots");
    const counter = $("#fb-counter");
    const prevBtn = $("#fb-prev");
    const nextBtn = $("#fb-next");
    if (!live || !book) return;

    const TOTAL = 7;
    let pages = [];
    let index = 0;
    let busy = false;
    let loaded = false;

    const scopeLabel = function () { return state.scope === "global" ? "toàn cầu" : "Việt Nam"; };
    const shareOf = function (s) { return s.strong_share == null ? (s.share || 0) : s.strong_share; };
    const foot = function (no, label, meta) {
      return '<div class="fb-foot"><span>' + esc(label) + '</span><span>Trang ' + no + ' / ' + TOTAL + " · " + esc(meta) + "</span></div>";
    };
    const kpi = function (value, label) {
      return '<div class="fb-kpi"><strong>' + esc(value) + "</strong><small>" + esc(label) + "</small></div>";
    };
    const barRow = function (label, pct, valueText) {
      return '<div class="fb-bar"><span class="fb-bar-label">' + esc(label) + "</span>" +
        '<span class="fb-bar-track"><i style="width:' + Math.max(3, Math.min(100, pct)) + '%"></i></span>' +
        '<span class="fb-bar-value">' + esc(valueText) + "</span></div>";
    };
    const listRow = function (name, meta, pct) {
      return '<div class="fb-list-row"><span class="name">' + esc(name) + '</span><span class="count">' + esc(meta) + "</span>" +
        '<div class="fb-meter"><i style="width:' + Math.max(2, Math.min(100, pct)) + '%"></i></div></div>';
    };
    const spark = function (daily) {
      const items = (daily || []).slice(-14);
      if (!items.length) return '<div class="empty">Chưa đủ dữ liệu theo ngày.</div>';
      const max = Math.max.apply(null, items.map(function (x) { return x.count; }).concat([1]));
      return '<div class="fb-spark">' + items.map(function (x) {
        return '<i style="height:' + Math.max(3, Math.round((x.count / max) * 100)) + '%" title="' + esc(x.date) + ": " + x.count + ' tin"></i>';
      }).join("") + "</div>" +
        '<div class="fb-spark-label"><span>' + esc(items[0].date) + "</span><span>" + esc(items[items.length - 1].date) + "</span></div>";
    };

    function buildPages(d) {
      const k = d.kpis || {};
      const det = d.details || {};
      const standards = (d.top_standards && d.top_standards.length ? d.top_standards : d.top_skills) || [];
      const rising = d.rising || [];
      const roles = d.roles || [];
      const locations = (d.top_locations || {}).items || [];
      const types = (d.company_types || {}).items || [];
      const social = d.social || {};
      const sk = social.kpis || {};
      const updated = fmtDate(d.last_ingest);
      const sourceCount = ((d.method || {}).source_list || []).length || 17;
      const coverage = det.any_coverage || 0;
      const salaryText = state.scope === "global"
        ? (k.global_median_usd ? fmtNum.format(k.global_median_usd) + " USD" : "—")
        : (k.vn_median_salary_text || "—");
      const salaryLabel = state.scope === "global" ? "lương trung vị/năm (tin USD)" : "lương trung vị/tháng (tin công bố)";

      const cover = {
        cover: true,
        title: "Bìa",
        html:
          '<div class="fb-cover-top"><span>PHẦN 6 · HƯỚNG ĐI &amp; VIỆC LÀM</span><span class="fb-brandmark">La Bàn Nghề</span></div>' +
          '<div class="fb-cover-main">' +
            "<h1>Đọc thị trường tuyển dụng như một cuốn sách.</h1>" +
            "<p>Dữ liệu công khai từ " + sourceCount + " nguồn tuyển dụng, chuẩn hoá kỹ năng và vị trí để sinh viên chọn hướng đi có bằng chứng. Phạm vi " + scopeLabel() + ", cửa sổ " + state.days + " ngày.</p>" +
            '<div class="fb-cover-stats">' +
              "<div><strong>" + fmtNum.format(k.jobs || 0) + "</strong><small>tin tuyển dụng</small></div>" +
              "<div><strong>" + fmtNum.format(k.companies || 0) + "</strong><small>doanh nghiệp</small></div>" +
              "<div><strong>" + fmtPct.format(coverage) + "%</strong><small>tin có mô tả/yêu cầu</small></div>" +
              "<div><strong>" + esc(salaryText) + "</strong><small>" + esc(salaryLabel) + "</small></div>" +
            "</div>" +
          "</div>" +
          '<div class="fb-foot"><span>TLU · Tập huấn sinh viên 2026</span><span>Cập nhật ' + esc(updated) + " · " + sourceCount + " nguồn</span></div>",
      };

      const market = {
        title: "Thị trường",
        html:
          '<div class="fb-head"><span class="fb-kicker">Trang 2 · Toàn cảnh</span><h2>Thị trường trong ' + state.days + " ngày</h2>" +
          '<p class="fb-sub">Đơn vị phân tích là tin tuyển dụng đang hoạt động, có ngày đăng trong cửa sổ đã chọn. Tin trùng giữa các nguồn được gộp theo tiêu đề, công ty, địa điểm và tháng.</p></div>' +
          '<div class="fb-kpis">' +
            kpi(fmtNum.format(k.jobs || 0), "tin trong phạm vi") +
            kpi(fmtNum.format(k.companies || 0), "doanh nghiệp") +
            kpi(fmtPct.format(coverage) + "%", "tin có mô tả/yêu cầu") +
            kpi(esc(salaryText), salaryLabel) +
          "</div>" +
          '<div class="fb-section-title">Tin ghi nhận theo ngày · 14 ngày gần nhất</div>' +
          spark(d.daily) +
          '<p class="fb-note">Kho hiện có ' + fmtNum.format((d.db || {}).total || 0) + " tin; " + fmtNum.format(k.new_today || 0) +
          " tin mới trong hôm nay. Chênh lệch kỳ trước chỉ hiện khi mẫu kỳ trước đủ lớn, tránh mức tăng ảo sau khi bổ sung nguồn.</p>" +
          foot(2, "Toàn cảnh thị trường", "Cập nhật " + updated),
      };

      const maxSkill = Math.max.apply(null, standards.slice(0, 8).map(shareOf).concat([1]));
      const skills = {
        title: "Kỹ năng",
        html:
          '<div class="fb-head"><span class="fb-kicker">Trang 3 · Tiêu chuẩn nghề</span><h2>Kỹ năng có bằng chứng trong mô tả tuyển dụng</h2>' +
          '<p class="fb-sub">Chỉ tính kỹ năng xuất hiện trong thẻ, mô tả hoặc mục yêu cầu. Tiêu đề chỉ là tín hiệu phụ, không đủ để tạo thành tiêu chuẩn nghề.</p></div>' +
          '<div class="fb-bars">' + (standards.slice(0, 8).map(function (s) {
            return barRow(s.label, (shareOf(s) / maxSkill) * 100, fmtPct.format(shareOf(s)) + "%");
          }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>') + "</div>" +
          '<p class="fb-note">Tỷ lệ = số tin có kỹ năng / tổng tin trong phạm vi. Cột "bằng chứng mạnh" đếm tin có kỹ năng trong thẻ, mô tả hoặc yêu cầu; đọc kèm độ phủ chi tiết ' +
          fmtPct.format(coverage) + "% để biết mẫu văn bản đáng tin đến đâu.</p>" +
          foot(3, "Kỹ năng dẫn đầu", "Phạm vi " + scopeLabel()),
      };

      const maxRole = Math.max.apply(null, roles.slice(0, 5).map(function (r) { return r.share || 0; }).concat([1]));
      const rolesPage = {
        title: "Vị trí",
        html:
          '<div class="fb-head"><span class="fb-kicker">Trang 4 · Nhóm vị trí</span><h2>Vị trí đang tuyển và tiêu chuẩn đi kèm</h2>' +
          '<p class="fb-sub">Mỗi vị trí đi kèm các kỹ năng có nhiều bằng chứng mạnh nhất. Dùng để chọn một hướng gần với mục tiêu học tập, không phải danh sách ưu tiên cá nhân.</p></div>' +
          '<div class="fb-list">' + (roles.slice(0, 5).map(function (r) {
            const chips = (r.standard_skills || []).slice(0, 3).map(function (s) {
              return '<span class="chip chip-small">' + esc(s.label) + " · " + fmtPct.format(s.strong_share || 0) + "%</span>";
            }).join("");
            return '<div class="fb-list-row"><span class="name">' + esc(r.label) + '</span><span class="count">' + fmtNum.format(r.jobs) + " tin · " + fmtPct.format(r.share || 0) + "%</span>" +
              '<div class="fb-meter"><i style="width:' + Math.max(3, ((r.share || 0) / maxRole) * 100) + '%"></i></div>' +
              '<div class="fb-chips" style="grid-column:1/-1;margin-top:6px">' + (chips || '<span class="chip">Chưa đủ dữ liệu</span>') + "</div></div>";
          }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>') + "</div>" +
          '<p class="fb-note">Còn ' + Math.max(0, roles.length - 5) + " nhóm vị trí khác trong trang Vị trí. Phân loại theo quy tắc từ khoá, có thể nhầm với chức danh viết tắt hoặc tiêu đề mơ hồ.</p>" +
          foot(4, "Nhóm vị trí", "Tiêu chuẩn có dẫn chứng"),
      };

      const maxLoc = Math.max.apply(null, locations.map(function (x) { return x.share || 0; }).concat([1]));
      const places = {
        title: "Địa bàn",
        html:
          '<div class="fb-head"><span class="fb-kicker">Trang 5 · Nơi tuyển</span><h2>Địa bàn và loại hình doanh nghiệp</h2>' +
          '<p class="fb-sub">Địa bàn lấy từ trường địa điểm của tin; một tin nhiều tỉnh/thành được tính cho từng nơi. Loại hình doanh nghiệp là phân loại tham chiếu theo tên.</p></div>' +
          '<div class="fb-columns">' +
            "<div><div class=\"fb-section-title\">Tỉnh/thành nhiều tin</div>" +
              (locations.length ? locations.slice(0, 6).map(function (x) {
                return listRow(x.name, fmtNum.format(x.jobs) + " tin", ((x.share || 0) / maxLoc) * 100);
              }).join("") : '<div class="empty">Chỉ phân tích tin Việt Nam.</div>') +
              '<p class="fb-note">Độ phủ địa bàn ' + fmtPct.format((d.top_locations || {}).coverage || 0) + "%.</p>" +
            "</div>" +
            "<div><div class=\"fb-section-title\">Cơ cấu loại hình</div>" +
              (types.length ? types.map(function (x) {
                return listRow(x.label, fmtNum.format(x.jobs) + " tin · " + fmtPct.format(x.share || 0) + "%", x.share || 0);
              }).join("") : '<div class="empty">Chỉ phân tích tin Việt Nam.</div>') +
              '<p class="fb-note">Tỷ lệ xác định được loại hình ' + fmtPct.format((d.company_types || {}).coverage || 0) + "%. Nhóm chưa xác định được giữ riêng, không gán bừa.</p>" +
            "</div>" +
          "</div>" +
          foot(5, "Địa bàn & doanh nghiệp", "Chỉ tin Việt Nam"),
      };

      const socialPage = {
        title: "Cộng đồng",
        html:
          '<div class="fb-head"><span class="fb-kicker">Trang 6 · Tín hiệu cộng đồng</span><h2>Điều sinh viên đang bàn</h2>' +
          '<p class="fb-sub">RSS công khai của bốn chuyên mục Voz: tuyển dụng, CNTT, AI, ngoại ngữ. Chỉ đọc tiêu đề và đoạn trích; không lưu tên tác giả, không thu thập bình luận.</p></div>' +
          '<div class="fb-kpis">' +
            kpi(fmtNum.format(sk.threads || 0), "chủ đề") +
            kpi(fmtNum.format(sk.discussions || 0), "thảo luận") +
            kpi(fmtNum.format(sk.replies || 0), "lượt phản hồi") +
            kpi(fmtNum.format(sk.with_skills || 0), "chủ đề có nhắc kỹ năng") +
          "</div>" +
          '<div class="fb-columns">' +
            "<div><div class=\"fb-section-title\">Chủ đề được bàn nhiều</div><div class=\"fb-chips\">" +
              ((social.topics || []).slice(0, 6).map(function (t) {
                return '<span class="chip">' + esc(t.label) + " · " + fmtNum.format(t.threads) + "</span>";
              }).join("") || '<span class="chip">Chưa đủ dữ liệu</span>') +
            "</div></div>" +
            "<div><div class=\"fb-section-title\">Kỹ năng được nhắc và khoảng cách với tin tuyển dụng</div>" +
              ((social.skills || []).slice(0, 5).map(function (s) {
                const gap = s.gap == null ? "—" : (s.gap > 0 ? "+" : "") + fmtPct.format(s.gap) + " đ";
                return listRow(s.label, fmtPct.format(s.share || 0) + "% chủ đề · " + esc(gap), s.share || 0);
              }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>') +
            "</div>" +
          "</div>" +
          '<p class="fb-note">' + esc(social.caveat || "Mỗi chuyên mục chỉ có khoảng 20 thớt mới nhất trong RSS; mẫu không đại diện cho toàn bộ diễn đàn.") + "</p>" +
          foot(6, "Tín hiệu cộng đồng", "RSS công khai"),
      };

      const plan = {
        title: "Cách dùng",
        html:
          '<div class="fb-head"><span class="fb-kicker">Trang 7 · Cách dùng</span><h2>Từ số liệu đến kế hoạch 90 ngày</h2>' +
          '<p class="fb-sub">Dùng cuốn sách này như một bản đồ: đọc nhu cầu, chọn một hướng, rồi tạo bằng chứng cụ thể thay vì học tràn lan.</p></div>' +
          '<ol class="fb-steps">' +
            "<li><b>Chọn phạm vi và thời gian.</b> Việt Nam hoặc toàn cầu, 30 hoặc 90 ngày. Ghi lại mốc thời gian khi trích dẫn số liệu.</li>" +
            "<li><b>Chọn một vị trí gần mục tiêu.</b> Đọc 5 kỹ năng có bằng chứng mạnh nhất và 3 kỹ năng đang lên; mở tin mẫu để đối chiếu ngữ cảnh.</li>" +
            "<li><b>Đối chiếu với cộng đồng.</b> Xem khoảng cách giữa điều sinh viên bàn và điều nhà tuyển dụng yêu cầu để chọn chủ đề học có nhu cầu thật.</li>" +
            "<li><b>Chọn 3 kỹ năng, tạo 3 bằng chứng.</b> Mỗi kỹ năng gắn với một dự án, chứng chỉ, bài viết hoặc sản phẩm trong 90 ngày.</li>" +
          "</ol>" +
          '<p class="fb-note">Dữ liệu từ ' + sourceCount + " nguồn công khai, không đại diện toàn bộ thị trường. Tin ẩn lương và tin thiếu mô tả làm giảm độ chính xác. Phân loại vị trí, kỹ năng, địa bàn và loại hình doanh nghiệp là rule-based, cần đối chiếu trước khi dùng cho kết luận mạnh. Xem chi tiết tại trang <a class=\"text-link\" href=\"/nguon\">Nguồn &amp; phương pháp</a>.</p>" +
          '<div class="fb-chips" style="margin-top:14px">' +
            (rising.slice(0, 4).map(function (s) {
              return '<span class="chip chip-standard">' + esc(s.label) + " +" + fmtPct.format(s.delta) + " đ</span>";
            }).join("") || '<span class="chip">Chưa đủ dữ liệu kỳ trước</span>') +
          "</div>" +
          foot(7, "Kế hoạch 90 ngày", "La Bàn Nghề"),
      };

      return [cover, market, skills, rolesPage, places, socialPage, plan];
    }

    function render() {
      const p = pages[index];
      if (!p) return;
      live.className = "fb-page" + (p.cover ? " fb-cover" : "");
      live.innerHTML = p.html;
      if (counter) counter.textContent = "Trang " + (index + 1) + " / " + pages.length;
      if (prevBtn) prevBtn.disabled = index === 0;
      if (nextBtn) nextBtn.disabled = index === pages.length - 1;
      $$(".fb-dot", dots).forEach(function (dot, i) {
        dot.classList.toggle("active", i === index);
        dot.setAttribute("aria-current", i === index ? "true" : "false");
      });
    }

    function buildDots() {
      if (!dots) return;
      dots.innerHTML = pages.map(function (p, i) {
        return '<button type="button" class="fb-dot" data-page="' + i + '" aria-label="Trang ' + (i + 1) + ": " + esc(p.title) + '"></button>';
      }).join("");
    }

    function flipTo(target) {
      if (!loaded || busy || target < 0 || target >= pages.length || target === index) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        index = target;
        render();
        return;
      }
      busy = true;
      const forward = target > index;
      const source = forward ? pages[index] : pages[target];
      const sheet = document.createElement("article");
      sheet.className = "fb-page" + (source.cover ? " fb-cover" : "") + " fb-flip " + (forward ? "out" : "in");
      sheet.setAttribute("aria-hidden", "true");
      sheet.innerHTML = source.html;
      if (forward) {
        index = target;
        render();
      }
      book.appendChild(sheet);
      let done = false;
      const finish = function () {
        if (done) return;
        done = true;
        if (sheet.parentNode) sheet.parentNode.removeChild(sheet);
        busy = false;
        if (!forward) {
          index = target;
          render();
        }
      };
      sheet.addEventListener("animationend", finish);
      window.setTimeout(finish, 820);
    }

    if (prevBtn) prevBtn.addEventListener("click", function () { flipTo(index - 1); });
    if (nextBtn) nextBtn.addEventListener("click", function () { flipTo(index + 1); });
    if (dots) {
      dots.addEventListener("click", function (event) {
        const dot = event.target.closest(".fb-dot");
        if (dot) flipTo(parseInt(dot.dataset.page, 10));
      });
    }
    document.addEventListener("keydown", function (event) {
      const tag = (event.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "select" || tag === "textarea") return;
      if (event.key === "ArrowRight" || event.key === "PageDown") { flipTo(index + 1); }
      else if (event.key === "ArrowLeft" || event.key === "PageUp") { flipTo(index - 1); }
      else if (event.key === "Home") { flipTo(0); }
      else if (event.key === "End") { flipTo(pages.length - 1); }
    });
    let touchX = null;
    book.addEventListener("touchstart", function (event) {
      if (event.touches.length === 1) touchX = event.touches[0].clientX;
    }, { passive: true });
    book.addEventListener("touchend", function (event) {
      if (touchX == null) return;
      const dx = event.changedTouches[0].clientX - touchX;
      touchX = null;
      if (Math.abs(dx) > 48) flipTo(index + (dx < 0 ? 1 : -1));
    }, { passive: true });

    async function load() {
      loaded = false;
      busy = false;
      live.className = "fb-page";
      live.innerHTML = '<div class="skeleton card"></div>';
      try {
        const d = await api("/api/export", { scope: state.scope, days: state.days });
        pages = buildPages(d);
        loaded = true;
        index = 0;
        buildDots();
        render();
      } catch (err) {
        live.innerHTML = errorHtml(err.message);
        if (counter) counter.textContent = "";
      }
    }

    bindControls(load);
    await load();
  }

  function itBars(items, color) {
    const max = Math.max.apply(null, items.map(function (x) { return x.jobs; }).concat([1]));
    return items.map(function (x) {
      return '<div class="bar-row static">' +
        '<div class="bar-label">' + esc(x.label) + "</div>" +
        '<div class="bar-track"><div class="bar-fill" style="width:' + Math.max(2, (x.jobs / max) * 100) + "%;background:" + color + '"></div></div>' +
        '<div class="bar-value"><strong>' + fmtNum.format(x.jobs) + "</strong><small>" + fmtPct.format(x.share) + "%</small></div></div>";
    }).join("") || '<div class="empty">Chưa đủ dữ liệu trong phạm vi.</div>';
  }

  async function initIT() {
    const kpis = $("#it-kpis");
    const rolesGrid = $("#it-roles");
    const matrix = $("#it-matrix");
    const contents = $("#it-contents");
    const groups = $("#it-groups");
    const levels = $("#it-levels");
    const evidence = $("#it-evidence");
    const cities = $("#it-cities");
    const companies = $("#it-companies");

    if (!initIT.bound) {
      initIT.bound = true;
      rolesGrid.addEventListener("click", function (event) {
        const card = event.target.closest("[data-role-link]");
        if (card) openRole(card.dataset.roleLink);
      });
      matrix.addEventListener("click", function (event) {
        const row = event.target.closest("[data-skill]");
        if (row) openSkill(row.dataset.skill);
      });
    }

    async function load() {
      $("#it-note").textContent = "Đang tải…";
      try {
        const d = await api("/api/it", { scope: state.scope, days: state.days });
        const k = d.kpis || {};
        const scopeLabel = state.scope === "global" ? "toàn cầu" : "Việt Nam";
        kpis.innerHTML =
          kpiCard("Tin CNTT", fmtNum.format(k.jobs || 0), fmtPct.format(k.share_scope || 0) + "% tổng tin " + scopeLabel) +
          kpiCard("Có mô tả hoặc yêu cầu", fmtPct.format(k.detail_coverage || 0) + "%", fmtNum.format(k.detail_jobs || 0) + " tin đọc được nội dung") +
          kpiCard("Lương trung vị", esc(k.median_salary_text || "—"), fmtPct.format(k.salary_coverage || 0) + "% tin CNTT công bố lương") +
          kpiCard("Kỹ năng kỹ thuật nổi bật", esc(k.top_skill || "—"), fmtPct.format(k.top_skill_share || 0) + "% tin CNTT có yêu cầu");
        $("#it-note").textContent = fmtNum.format(k.total_scope || 0) + " tin trong phạm vi · " + fmtNum.format(k.jobs || 0) + " tin CNTT";

        rolesGrid.innerHTML = (d.roles || []).map(function (r) {
          const standards = (r.top_skills || []).map(function (s) {
            return '<span class="chip chip-standard">' + esc(s.label) + " · " + fmtPct.format(s.strong_share) + "%</span>";
          }).join("");
          return '<article class="role-card" data-role-link="' + esc(r.id) + '">' +
            "<h3>" + esc(r.label) + (r.thin ? ' <span class="thin-badge">ít tin</span>' : "") + "</h3>" +
            '<div class="role-count">' + fmtNum.format(r.jobs) + " tin · " + fmtPct.format(r.share_in_it) + "% tin CNTT</div>" +
            '<div class="role-share"><div class="track"><i style="width:' + Math.min(100, r.share_in_it * 2.4) + '%"></i></div><span>' + fmtPct.format(r.share_scope) + "% tổng</span></div>" +
            '<div class="role-skills">' + (standards || '<span class="chip">Chưa đủ dữ liệu</span>') + "</div>" +
            '<div class="role-coverage">' + fmtPct.format(r.detail_coverage || 0) + "% tin có mô tả/yêu cầu</div>" +
            '<div class="role-salary">Lương trung vị: <strong>' + esc(r.median_salary_text || "—") + "</strong></div>" +
          "</article>";
        }).join("") || '<div class="empty">Chưa đủ dữ liệu CNTT.</div>';

        const cols = d.matrix_roles || [];
        matrix.querySelector("thead").innerHTML = "<tr><th>Kỹ năng</th><th>Nhóm</th>" +
          cols.map(function (r) {
            return "<th>" + esc(r.label) + (r.jobs < 15 ? '<br><small>ít tin</small>' : "") + "</th>";
          }).join("") + "</tr>";
        matrix.querySelector("tbody").innerHTML = (d.matrix || []).map(function (m) {
          const cells = (m.cells || []).map(function (c) {
            const alpha = Math.min(0.72, (c.share / 55) * 0.72);
            const style = c.share ? "background:rgba(37,99,235," + alpha.toFixed(2) + ");color:" + (alpha > 0.42 ? "#fff" : "var(--ink)") : "";
            return '<td class="heat-cell" style="' + style + '" title="' + esc(m.label + " · " + c.strong + " tin có yêu cầu") + '">' + (c.share ? fmtPct.format(c.share) + "%" : "—") + "</td>";
          }).join("");
          return '<tr data-skill="' + esc(m.id) + '"><td><div class="skill-name">' + groupDot(m.group) + " " + esc(m.label) + "</div></td>" +
            '<td class="skill-group">' + esc(m.group_label) + "</td>" + cells + "</tr>";
        }).join("") || '<tr><td colspan="9"><div class="empty">Chưa đủ dữ liệu.</div></td></tr>';

        contents.innerHTML = itBars(d.contents || [], "#0F766E");
        groups.innerHTML = itBars(d.groups || [], "#2563EB");
        levels.innerHTML = itBars(d.levels || [], "#B45309");

        evidence.innerHTML = (d.evidence || []).map(function (e) {
          const quotes = (e.quotes || []).map(function (q) {
            return '<div class="quote-block">' +
              '<a class="quote-job" href="' + esc(safeUrl(q.url)) + '" target="_blank" rel="noopener noreferrer">' + esc(q.job_title || "Tin tuyển dụng") + "</a>" +
              (q.company ? '<div class="quote-company">' + esc(q.company) + "</div>" : "") +
              '<p class="quote-text">“' + esc(q.text) + '”</p></div>';
          }).join("");
          return '<article class="evidence-card">' +
            '<div class="evidence-head"><span class="evidence-skill">' + groupDot(e.group) + esc(e.label) + "</span>" +
            '<span class="evidence-share">' + fmtPct.format(e.strong_share) + "% tin CNTT</span></div>" + quotes + "</article>";
        }).join("") || '<div class="empty">Chưa đủ câu trích.</div>';

        cities.innerHTML = (d.cities || []).map(function (c) {
          return '<div class="company-item"><span>' + esc(c.name) + '</span><span class="count">' + fmtNum.format(c.jobs) + "</span></div>";
        }).join("") || '<div class="empty">Chưa có địa điểm.</div>';
        companies.innerHTML = (d.companies || []).map(function (c) {
          return '<div class="company-item"><span class="monogram">' + esc(monogram(c.name)) + "</span><span>" + esc(c.name) + "</span>" +
            (c.tier === 2 ? '<span class="tier-badge">top</span>' : "") +
            '<span class="count">' + fmtNum.format(c.jobs) + "</span></div>";
        }).join("") || '<div class="empty">Chưa đủ dữ liệu.</div>';
      } catch (err) {
        $("#it-note").textContent = "";
        rolesGrid.innerHTML = errorHtml(err.message);
      }
    }

    bindControls(load);
    await load();
  }

  async function loadFooter() {
    try {
      const d = await api("/api/health");
      const text = d.last_ingest ? "cập nhật " + fmtDateTime(d.last_ingest) : "chưa có dữ liệu";
      const el = $("#footer-updated");
      if (el) el.textContent = text;
    } catch (err) {
      const el = $("#footer-updated");
      if (el) el.textContent = "chưa kết nối";
    }
  }

  function applyStaticMode() {
    const config = window.LABAN_STATIC;
    if (!config) return;
    const main = document.querySelector("main");
    if (main && !document.querySelector(".static-note")) {
      const note = document.createElement("div");
      note.className = "static-note wrap";
      note.innerHTML = "<strong>Bản công khai tĩnh.</strong> Số liệu được chụp" +
        (config.captured ? " ngày " + esc(config.captured) : "") +
        "; bộ lọc phạm vi/thời gian và API trực tiếp không chạy trên GitHub Pages." +
        (config.repo_url ? ' <a href="' + esc(config.repo_url) + '" target="_blank" rel="noopener noreferrer">Xem mã nguồn ↗</a>' : "");
      main.insertBefore(note, main.firstChild);
    }
    $$("#scope-toggle button, #social-forum button").forEach(function (btn) {
      btn.disabled = true;
    });
    $$("#days-select, #social-days, #skill-search, #role-filter").forEach(function (el) {
      el.disabled = true;
    });
    $$(".controls-bar").forEach(function (el) {
      el.classList.add("is-static");
    });
  }

  function init() {
    readState();
    syncControls();
    applyStaticMode();
    initDrawer();
    loadFooter();
    if (PAGE === "overview") {
      bindControls(initOverview);
      initOverview();
    } else if (PAGE === "skills") initSkills();
    else if (PAGE === "roles") initRoles();
    else if (PAGE === "it") initIT();
    else if (PAGE === "social") initSocial();
    else if (PAGE === "sources") initSources();
    else if (PAGE === "report") initReport();
    else if (PAGE === "flipbook") initFlipbook();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
