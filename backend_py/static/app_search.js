/* Global helper for authenticated app autocomplete (/api/app/search). */
(function () {
  function getCookie(name) {
    var cookie = String(document.cookie || "");
    var parts = cookie.split(";").map(function (s) { return s.trim(); });
    var prefix = String(name || "") + "=";
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].indexOf(prefix) === 0) return decodeURIComponent(parts[i].slice(prefix.length));
    }
    return "";
  }

  function getActiveClientId() {
    var ls = "";
    try { ls = String(localStorage.getItem("camarad_client_id") || "").trim(); } catch (e) {}
    var ck = String(getCookie("camarad_client_id") || "").trim();
    var txt = ls || ck;
    if (!txt) return "";
    if (!/^[1-9][0-9]*$/.test(txt)) return "";
    return txt;
  }

  function init(opts) {
    opts = opts || {};
    var inputEl = opts.inputEl;
    var suggestEl = opts.suggestEl;
    if (!inputEl || !suggestEl) return null;

    var debounceMs = Number(opts.debounceMs || 140);
    var onInput = typeof opts.onInput === "function" ? opts.onInput : null;
    var fallbackUrl = typeof opts.fallbackUrl === "function" ? opts.fallbackUrl : null;
    var redirectOn401 = opts.redirectOn401 !== false;
    var onUnauthorized = typeof opts.onUnauthorized === "function" ? opts.onUnauthorized : null;
    var onClientScopeMissing = typeof opts.onClientScopeMissing === "function" ? opts.onClientScopeMissing : null;
    var hintEl = opts.clientHintEl || null;
    var hintLinkEl = opts.clientHintLinkEl || null;
    var hintHref = String(opts.clientHintHref || "/settings").trim();
    var hintText = String(opts.clientHintText || "Select a client to search.").trim();
    var timer = null;

    function setHint(show) {
      if (!hintEl) return;
      hintEl.style.display = show ? "" : "none";
      hintEl.textContent = show ? hintText : "";
      if (hintLinkEl) {
        hintLinkEl.style.display = show ? "" : "none";
        if (show && hintHref) hintLinkEl.setAttribute("href", hintHref);
      }
    }

    function hideSuggest() {
      suggestEl.style.display = "none";
      suggestEl.innerHTML = "";
    }

    function renderSuggest(rows) {
      if (!Array.isArray(rows) || !rows.length) {
        hideSuggest();
        return;
      }
      suggestEl.innerHTML = "";
      var frag = document.createDocumentFragment();
      rows.forEach(function (r) {
        var type = String((r && r.type) || "").trim();
        var name = String((r && r.name) || "").trim();
        var subtitle = String((r && r.subtitle) || "").trim();
        var url = String((r && r.url) || "").trim();
        if (!url) return;

        var btn = document.createElement("button");
        btn.type = "button";
        btn.setAttribute("data-url", url);

        var typeEl = document.createElement("span");
        typeEl.className = "app-search-type";
        typeEl.textContent = type;
        btn.appendChild(typeEl);

        var strong = document.createElement("strong");
        strong.textContent = name;
        btn.appendChild(strong);

        if (subtitle) {
          var sub = document.createElement("span");
          sub.className = "app-search-sub";
          sub.textContent = subtitle;
          btn.appendChild(sub);
        }
        frag.appendChild(btn);
      });
      suggestEl.appendChild(frag);
      suggestEl.style.display = "block";
      setHint(false);
      suggestEl.querySelectorAll("button[data-url]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var url = String(btn.getAttribute("data-url") || "").trim();
          if (url) window.location.href = url;
        });
      });
    }

    function requestAppSearch(queryText) {
      var q = String(queryText || "").trim();
      if (q.length < 2) {
        hideSuggest();
        return;
      }
      var clientId = getActiveClientId();
      if (!clientId) {
        hideSuggest();
        setHint(true);
        if (onClientScopeMissing) onClientScopeMissing();
        return;
      }
      // Scope is resolved server-side from auth/session cookie.
      var qsx = new URLSearchParams({ q: q });
      fetch("/api/app/search?" + qsx.toString(), { credentials: "same-origin" })
        .then(function (r) {
          if (r.status === 401) {
            if (onUnauthorized) onUnauthorized();
            if (redirectOn401) window.location.href = "/signup?next=/app";
            throw new Error("auth");
          }
          if (r.status === 400) {
            hideSuggest();
            setHint(true);
            if (onClientScopeMissing) onClientScopeMissing();
            return [];
          }
          if (!r.ok) return [];
          return r.json();
        })
        .then(function (rows) {
          if (Array.isArray(rows) && rows.length) setHint(false);
          return rows;
        })
        .then(renderSuggest)
        .catch(function () {
          hideSuggest();
        });
    }

    inputEl.addEventListener("input", function () {
      if (onInput) onInput(inputEl.value);
      setHint(false);
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { requestAppSearch(inputEl.value); }, debounceMs);
    });

    inputEl.addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter") return;
      var first = suggestEl.querySelector("button[data-url]");
      if (first) {
        ev.preventDefault();
        first.click();
        return;
      }
      if (fallbackUrl) {
        var url = String(fallbackUrl(String(inputEl.value || "").trim()) || "").trim();
        if (url) {
          ev.preventDefault();
          window.location.href = url;
        }
      }
    });

    document.addEventListener("click", function (ev) {
      if (!inputEl.contains(ev.target) && !suggestEl.contains(ev.target)) hideSuggest();
    });

    setHint(false);
    return { hide: hideSuggest };
  }

  window.CamaradAppSearch = {
    init: init,
    getActiveClientId: getActiveClientId
  };
})();
