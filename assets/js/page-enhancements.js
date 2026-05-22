(function () {
  function normalizePath(path) {
    var value = String(path || "");
    value = value.replace(/[?#].*$/, "");
    value = value.replace(/\/+$/, "");
    return value || "/";
  }

  function normalizeBaseUrl(baseUrl) {
    var value = String(baseUrl || "").trim();
    if (!value || value === "/") {
      return "";
    }
    value = value.replace(/\/+$/, "");
    if (value.charAt(0) !== "/") {
      value = "/" + value;
    }
    return value;
  }

  function getSiteBaseUrl() {
    var body = document.body;
    if (!body || typeof body.getAttribute !== "function") {
      return "";
    }
    return normalizeBaseUrl(body.getAttribute("data-site-baseurl") || "");
  }

  function resolveSiteHref(path) {
    var value = String(path || "").trim();
    if (!value || value.charAt(0) === "#" || value.indexOf("{{") !== -1) {
      return value;
    }
    if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(value)) {
      return value;
    }
    if (value.charAt(0) !== "/") {
      return value;
    }
    var baseUrl = getSiteBaseUrl();
    if (!baseUrl) {
      return value;
    }
    if (value === baseUrl || value.indexOf(baseUrl + "/") === 0) {
      return value;
    }
    return baseUrl + value;
  }

  function parseCssPixels(value) {
    var parsed = parseFloat(String(value || "").trim());
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function readLocalStorage(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function writeLocalStorage(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      // Ignore storage write failures.
    }
  }

  function removeLocalStorage(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (err) {
      // Ignore storage write failures.
    }
  }

  function getUiString(name, fallback) {
    var attrName = "data-ui-" + String(name || "").replace(/_/g, "-");
    var body = document.body;
    var root = document.documentElement;
    var value = "";
    if (body && typeof body.getAttribute === "function") {
      value = String(body.getAttribute(attrName) || "").trim();
    }
    if (!value && root && typeof root.getAttribute === "function") {
      value = String(root.getAttribute(attrName) || "").trim();
    }
    return value || String(fallback || "");
  }

  function formatUiString(templateName, fallback, replacements) {
    var template = getUiString(templateName, fallback);
    return String(template || "").replace(/\{([a-z_]+)\}/gi, function (match, token) {
      if (!replacements || !Object.prototype.hasOwnProperty.call(replacements, token)) {
        return match;
      }
      return String(replacements[token] || "");
    });
  }

  function getAnchorOffsetPixels() {
    var root = document.documentElement;
    if (!root || !window.getComputedStyle) {
      return 0;
    }
    return parseCssPixels(window.getComputedStyle(root).getPropertyValue("--anchor-offset"));
  }

  function syncAnchorOffset() {
    var root = document.documentElement;
    var header = document.querySelector(".site-header");
    if (!root) {
      return 0;
    }
    if (!header || !window.getComputedStyle) {
      root.style.setProperty("--anchor-offset", "1rem");
      return 16;
    }

    var headerStyle = window.getComputedStyle(header);
    var isOverlayHeader = headerStyle && (headerStyle.position === "sticky" || headerStyle.position === "fixed");
    var headerHeight = Math.ceil(header.getBoundingClientRect().height || 0);
    var offsetPx = isOverlayHeader ? (headerHeight + 14) : 16;
    if (!Number.isFinite(offsetPx) || offsetPx < 16) {
      offsetPx = 16;
    }
    root.style.setProperty("--anchor-offset", String(offsetPx) + "px");
    return offsetPx;
  }

  function initAnchorOffsetSync() {
    syncAnchorOffset();
    window.addEventListener("resize", syncAnchorOffset);
    window.addEventListener("orientationchange", syncAnchorOffset);
    if (document.fonts && document.fonts.ready && typeof document.fonts.ready.then === "function") {
      document.fonts.ready.then(function () {
        syncAnchorOffset();
      }).catch(function () {
        // Ignore font load observer failures.
      });
    }
  }

  function markActiveSidebarLink() {
    var currentPath = normalizePath(window.location.pathname);
    var links = document.querySelectorAll(".sidebar-link, .sidebar-item a");
    Array.prototype.forEach.call(links, function (link) {
      var href = link.getAttribute("href");
      if (!href) {
        return;
      }
      var resolvedPath = "";
      try {
        resolvedPath = normalizePath(new URL(href, window.location.origin).pathname);
      } catch (err) {
        resolvedPath = normalizePath(href);
      }
      if (resolvedPath === currentPath) {
        link.classList.add("is-current");
      }
    });
  }

  function createSidebarTreeItem(item, level) {
    if (!item || !item.url) {
      return null;
    }

    var title = String(item.title_short || item.title || item.title_full || item.url).trim();
    var fullTitle = String(item.title_full || title).trim();
    var children = Array.isArray(item.children) ? item.children.filter(Boolean) : [];
    var hasChildren = children.length > 0;

    var li = document.createElement("li");
    li.className = "sidebar-item";
    li.setAttribute("data-sidebar-level", String(level));
    if (hasChildren) {
      li.classList.add("has-children", "is-collapsed");
    }

    if (hasChildren) {
      var button = document.createElement("button");
      button.className = "sidebar-toggle";
      button.type = "button";
      button.setAttribute("data-sidebar-toggle", "");
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-label", getUiString("expand-section", "Expand section") + ": " + fullTitle);
      button.setAttribute("title", getUiString("expand-section", "Expand section"));
      button.textContent = "+";
      li.appendChild(button);
    }

    var link = document.createElement("a");
    link.className = "sidebar-link";
    link.href = resolveSiteHref(item.url);
    link.title = fullTitle;
    link.setAttribute("aria-label", getUiString("open_report", "Open report") + ": " + fullTitle);
    link.setAttribute("data-sidebar-search", (title + " " + fullTitle).toLowerCase());
    link.textContent = title;
    li.appendChild(link);

    if (hasChildren) {
      var childWrapper = document.createElement("div");
      childWrapper.className = "sidebar-children";
      childWrapper.setAttribute("data-sidebar-children", "");
      var childNav = createSidebarTreeNav(children, level + 1);
      if (childNav) {
        childWrapper.appendChild(childNav);
      }
      li.appendChild(childWrapper);
    }

    return li;
  }

  function createSidebarTreeNav(items, level) {
    if (!Array.isArray(items) || !items.length) {
      return null;
    }

    var sidebarItems = items;
    if (level === 1 && items.length === 1) {
      var singleRoot = items[0];
      if (singleRoot && Array.isArray(singleRoot.children) && singleRoot.children.length) {
        sidebarItems = singleRoot.children;
      }
    }

    var nav = document.createElement("nav");
    nav.className = "sidebar-nav";
    nav.setAttribute("aria-label", getUiString("topic_tree_navigation", "Topic tree navigation"));
    nav.setAttribute("data-sidebar-nav", "");

    var list = document.createElement("ul");
    list.className = "sidebar-list";
    list.setAttribute("data-sidebar-level", String(level));

    sidebarItems.forEach(function (item) {
      var child = createSidebarTreeItem(item, level);
      if (child) {
        list.appendChild(child);
      }
    });

    nav.appendChild(list);
    return nav;
  }

  function initSidebarHydration() {
    var roots = document.querySelectorAll("[data-sidebar-root][data-sidebar-source]");
    if (!roots.length || !window.fetch) {
      return Promise.resolve();
    }

    return Promise.all(Array.prototype.map.call(roots, function (root) {
      var source = String(root.getAttribute("data-sidebar-source") || "").trim();
      if (!source) {
        return Promise.resolve();
      }

      return window.fetch(source, { credentials: "same-origin" })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("Sidebar navigation request failed");
          }
          return response.json();
        })
        .then(function (items) {
          root.innerHTML = "";
          var nav = createSidebarTreeNav(items, 1);
          if (nav) {
            root.appendChild(nav);
          }
        })
        .catch(function () {
          root.innerHTML = "";
          var fallback = document.createElement("p");
          fallback.className = "sidebar-loading";
          fallback.innerHTML = '<a href="' + resolveSiteHref('/sitemap/') + '">Open sitemap</a>';
          root.appendChild(fallback);
        });
    }));
  }

  function setSidebarItemExpanded(item, expanded) {
    if (!item || !item.classList || !item.classList.contains("has-children")) {
      return;
    }
    var toggle = item.querySelector("[data-sidebar-toggle]");
    var link = item.querySelector(".sidebar-link");
    var label = String((link && (link.getAttribute("title") || link.textContent)) || "section").trim();
    var isExpanded = Boolean(expanded);
    item.classList.toggle("is-collapsed", !isExpanded);
    item.classList.toggle("is-expanded", isExpanded);
    if (toggle) {
      toggle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
      toggle.textContent = isExpanded ? "-" : "+";
      toggle.setAttribute("title", isExpanded ? getUiString("collapse-section", "Collapse section") : getUiString("expand-section", "Expand section"));
      toggle.setAttribute("aria-label", (isExpanded ? getUiString("collapse-section", "Collapse section") : getUiString("expand-section", "Expand section")) + ": " + label);
    }
  }

  function getRootSidebarNavs() {
    var navs = document.querySelectorAll("[data-sidebar-nav]");
    return Array.prototype.filter.call(navs, function (nav) {
      return !nav.parentElement || !nav.parentElement.closest("[data-sidebar-nav]");
    });
  }

  function initSidebarCollapsingForNav(nav) {
    if (!nav) {
      return;
    }
    var sidebarRoot = nav.closest(".sidebar") || nav.parentElement || document;

    /* Auto-collapse sidebar L3+ when tree has >20 items */
    var allSidebarItems = nav.querySelectorAll(".sidebar-item[data-sidebar-level]");
    if (allSidebarItems.length > 20) {
      for (var si = 0; si < allSidebarItems.length; si++) {
        var lvl = parseInt(allSidebarItems[si].getAttribute("data-sidebar-level") || "1", 10);
        if (lvl >= 3 && allSidebarItems[si].classList.contains("is-expanded")) {
          setSidebarItemExpanded(allSidebarItems[si], false);
        }
      }
    }

    var items = nav.querySelectorAll(".sidebar-item.has-children");
    var pathParts = normalizePath(window.location.pathname).split("/").filter(Boolean);
    var siteScope = pathParts.length ? pathParts[0] : "root";
    var storageKey = "phoenix-sidebar-expanded-v2-" + siteScope;
    var persistedState = {};
    try {
      var rawPersisted = String(readLocalStorage(storageKey) || "").trim();
      if (rawPersisted) {
        var parsedPersisted = JSON.parse(rawPersisted);
        if (parsedPersisted && typeof parsedPersisted === "object") {
          persistedState = parsedPersisted;
        }
      }
    } catch (err) {
      persistedState = {};
    }

    var getItemStorageKey = function (item) {
      if (!item) {
        return "";
      }
      var link = item.querySelector(".sidebar-link");
      var href = String((link && link.getAttribute("href")) || "").trim();
      if (href) {
        try {
          return normalizePath(new URL(href, window.location.origin).pathname);
        } catch (err) {
          return normalizePath(href);
        }
      }
      var label = String((link && (link.getAttribute("title") || link.textContent)) || "").trim().toLowerCase();
      if (label) {
        return "label:" + label.replace(/\s+/g, " ");
      }
      return "";
    };

    var savePersistedState = function () {
      try {
        writeLocalStorage(storageKey, JSON.stringify(persistedState));
      } catch (err) {
        // Ignore serialization/storage failures.
      }
    };

    var setExpandedWithPersistence = function (item, expanded, persistChoice) {
      setSidebarItemExpanded(item, expanded);
      if (!persistChoice) {
        return;
      }
      var key = getItemStorageKey(item);
      if (!key) {
        return;
      }
      persistedState[key] = expanded ? 1 : 0;
      savePersistedState();
    };

    var setAllExpandedWithPersistence = function (expanded, persistChoice) {
      Array.prototype.forEach.call(items, function (item) {
        setExpandedWithPersistence(item, expanded, persistChoice);
      });
    };

    var getSidebarLevel = function (item) {
      var parsed = parseInt(String((item && item.getAttribute("data-sidebar-level")) || "1"), 10);
      return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
    };

    var expandCurrentBranch = function (currentLink) {
      if (!currentLink) {
        return;
      }
      var currentItem = currentLink.closest(".sidebar-item");
      while (currentItem) {
        if (currentItem.classList.contains("has-children")) {
          setExpandedWithPersistence(currentItem, true, false);
        }
        var parentList = currentItem.parentElement;
        currentItem = parentList ? parentList.closest(".sidebar-item") : null;
      }
    };

    var scrollSidebarToCurrent = function (currentLink) {
      if (!currentLink || !currentLink.getBoundingClientRect) {
        return;
      }
      var scrollHost = nav.closest(".sidebar");
      if (!scrollHost || !scrollHost.getBoundingClientRect) {
        return;
      }
      var hostRect = scrollHost.getBoundingClientRect();
      var linkRect = currentLink.getBoundingClientRect();
      var pad = Math.max(24, Math.round(scrollHost.clientHeight * 0.16));
      var upperBound = hostRect.top + pad;
      var lowerBound = hostRect.bottom - pad;
      if (linkRect.top >= upperBound && linkRect.bottom <= lowerBound) {
        return;
      }
      var delta = (linkRect.top - hostRect.top) - Math.round(scrollHost.clientHeight * 0.32);
      scrollHost.scrollTop = Math.max(0, scrollHost.scrollTop + delta);
      if (typeof currentLink.scrollIntoView === "function") {
        try {
          currentLink.scrollIntoView({ block: "center", inline: "nearest" });
        } catch (err) {
          // Ignore unsupported scrollIntoView options.
        }
      }
    };

    var expandLevelTwoWhenTopLevelSparse = function () {
      var topLevelVisible = nav.querySelectorAll('.sidebar-item[data-sidebar-level="1"]:not(.is-filtered-out)');
      if (topLevelVisible.length >= 3) {
        return;
      }
      Array.prototype.forEach.call(items, function (item) {
        if (getSidebarLevel(item) === 1) {
          setExpandedWithPersistence(item, true, false);
        }
      });
    };

    Array.prototype.forEach.call(items, function (item) {
      var key = getItemStorageKey(item);
      var storedToken = key ? persistedState[key] : null;
      var hasStoredState = storedToken === 0 || storedToken === 1 || storedToken === true || storedToken === false;
      var initialExpanded = hasStoredState ? (storedToken === 1 || storedToken === true) : !item.classList.contains("is-collapsed");
      setSidebarItemExpanded(item, initialExpanded);
      var toggle = item.querySelector("[data-sidebar-toggle]");
      if (!toggle) {
        return;
      }
      toggle.addEventListener("click", function (event) {
        event.preventDefault();
        var shouldExpand = item.classList.contains("is-collapsed");
        setExpandedWithPersistence(item, shouldExpand, true);
      });
    });

    var currentLink = nav.querySelector(".sidebar-link.is-current");
    if (currentLink) {
      expandCurrentBranch(currentLink);
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(function () {
          scrollSidebarToCurrent(currentLink);
          window.setTimeout(function () {
            scrollSidebarToCurrent(currentLink);
          }, 120);
        });
      } else {
        scrollSidebarToCurrent(currentLink);
      }
    }

    var controlsRoot = nav.parentElement || sidebarRoot;
    var expandAllButton = controlsRoot.querySelector("[data-sidebar-expand-all]");
    if (expandAllButton) {
      expandAllButton.addEventListener("click", function () {
        setAllExpandedWithPersistence(true, true);
      });
    }

    var collapseAllButton = controlsRoot.querySelector("[data-sidebar-collapse-all]");
    if (collapseAllButton) {
      collapseAllButton.addEventListener("click", function () {
        setAllExpandedWithPersistence(false, true);
      });
    }
  }

  function initSidebarCollapsing() {
    var navs = getRootSidebarNavs();
    if (!navs.length) {
      return;
    }
    Array.prototype.forEach.call(navs, function (nav) {
      initSidebarCollapsingForNav(nav);
    });
  }

  function normalizeSearchText(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/['’]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function getSearchTokens(value) {
    var normalized = normalizeSearchText(value);
    return normalized ? normalized.split(/\s+/).filter(Boolean) : [];
  }

  function matchesSearchQuery(query, haystack) {
    var normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) {
      return true;
    }

    var normalizedHaystack = normalizeSearchText(haystack);
    if (!normalizedHaystack) {
      return false;
    }

    if (normalizedHaystack.indexOf(normalizedQuery) !== -1) {
      return true;
    }

    var queryTokens = getSearchTokens(normalizedQuery);
    var haystackTokens = getSearchTokens(normalizedHaystack);
    if (!queryTokens.length || !haystackTokens.length) {
      return false;
    }

    return queryTokens.every(function (queryToken) {
      return haystackTokens.some(function (haystackToken) {
        if (haystackToken === queryToken || haystackToken.indexOf(queryToken) === 0) {
          return true;
        }
        if (queryToken.length >= 4 && haystackToken.indexOf(queryToken) !== -1) {
          return true;
        }
        if (haystackToken.length >= 4 && queryToken.indexOf(haystackToken) === 0) {
          return true;
        }
        return false;
      });
    });
  }

  function countSearchTokenMatches(text, tokens) {
    var normalizedText = normalizeSearchText(text);
    if (!normalizedText || !Array.isArray(tokens) || !tokens.length) {
      return 0;
    }
    var seen = {};
    var count = 0;
    tokens.forEach(function (token) {
      if (!token || seen[token]) {
        return;
      }
      if (
        normalizedText === token
        || normalizedText.indexOf(token + " ") === 0
        || normalizedText.indexOf(" " + token + " ") !== -1
        || normalizedText.lastIndexOf(" " + token) === normalizedText.length - token.length - 1
        || normalizedText.indexOf(token) !== -1
      ) {
        seen[token] = true;
        count += 1;
      }
    });
    return count;
  }

  function matchesArchiveSearchEntry(query, item) {
    var normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) {
      return true;
    }
    var tokens = getSearchTokens(normalizedQuery);
    var title = normalizeSearchText(item && (item.title_text || item.title));
    var urlText = normalizeSearchText(item && (item.url_text || item.url));
    var section = normalizeSearchText(item && (item.section_text || item.section));
    var summary = normalizeSearchText(item && (item.summary_text || item.summary));
    var tags = normalizeSearchText(item && (item.tags_text || (item.tags ? item.tags.join(" ") : "")));
    var headings = normalizeSearchText(item && item.headings_text);
    var body = normalizeSearchText(item && item.body_text);
    var metadataHaystack = normalizeSearchText([title, urlText, section, summary, tags, headings].join(" "));

    if (!metadataHaystack && !body) {
      return false;
    }

    if (
      title === normalizedQuery
      || urlText === normalizedQuery
      || tags === normalizedQuery
      || title.indexOf(normalizedQuery) !== -1
      || urlText.indexOf(normalizedQuery) !== -1
      || section.indexOf(normalizedQuery) !== -1
      || summary.indexOf(normalizedQuery) !== -1
      || tags.indexOf(normalizedQuery) !== -1
      || headings.indexOf(normalizedQuery) !== -1
    ) {
      return true;
    }

    if (matchesSearchQuery(normalizedQuery, metadataHaystack)) {
      return true;
    }

    if (tokens.length === 1 && body.indexOf(tokens[0]) !== -1) {
      return true;
    }

    return false;
  }

  function initSidebarFilterForNav(nav) {
    if (!nav) {
      return;
    }
    var sidebarRoot = nav.closest(".sidebar") || nav.parentElement || document;
    var input = sidebarRoot.querySelector("[data-sidebar-filter]");
    var status = sidebarRoot.querySelector("[data-sidebar-filter-status]");
    var clearButton = sidebarRoot.querySelector("[data-sidebar-filter-clear]");
    if (!input) {
      return;
    }
    var items = nav.querySelectorAll(".sidebar-item");
    var totalReports = nav.querySelectorAll(".sidebar-link").length;
    var applyFilter = function () {
      var query = String(input.value || "").trim().toLowerCase();
      if (!query) {
        Array.prototype.forEach.call(items, function (item) {
          item.classList.remove("is-filtered-out");
          var resetLinkNode = item.querySelector(".sidebar-link");
          if (resetLinkNode) {
            resetLinkNode.classList.remove("is-search-match");
          }
        });
        var currentLink = nav.querySelector(".sidebar-link.is-current");
        if (currentLink) {
          var currentItem = currentLink.closest(".sidebar-item");
          while (currentItem) {
            if (currentItem.classList.contains("has-children")) {
              setSidebarItemExpanded(currentItem, true);
            }
            var parentList = currentItem.parentElement;
            currentItem = parentList ? parentList.closest(".sidebar-item") : null;
          }
        }
        if (status) {
          status.setAttribute("data-state", "default");
        status.textContent = totalReports ? (String(totalReports) + " pages in this section.") : "";
        }
        if (clearButton) {
          clearButton.hidden = true;
        }
        return;
      }
      var visibleReports = 0;
      for (var i = items.length - 1; i >= 0; i -= 1) {
        var item = items[i];
        var labelNode = item.querySelector(".sidebar-link");
        var haystack = String((labelNode && labelNode.getAttribute("data-sidebar-search")) || item.textContent || "").toLowerCase();
        var selfMatch = matchesSearchQuery(query, haystack);
        var descendantMatch = Boolean(item.querySelector("[data-sidebar-children] .sidebar-item:not(.is-filtered-out)"));
        var visible = selfMatch || descendantMatch;
        item.classList.toggle("is-filtered-out", !visible);
        if (labelNode) {
          labelNode.classList.toggle("is-search-match", selfMatch);
        }
        if (visible && labelNode && !item.querySelector("[data-sidebar-children]")) {
          visibleReports += 1;
        }
        if (visible && item.classList.contains("has-children")) {
          setSidebarItemExpanded(item, true);
        }
      }
      if (status) {
        if (!visibleReports) {
          status.setAttribute("data-state", "empty");
          status.textContent = "No pages match \"" + query + "\" in this section.";
        } else {
          status.setAttribute("data-state", "active");
          status.textContent = "Showing " + String(visibleReports) + " of " + String(totalReports) + " pages for \"" + query + "\".";
        }
      }
      if (clearButton) {
        clearButton.hidden = false;
      }
    };
    input.addEventListener("input", applyFilter);
    input.addEventListener("keydown", function (event) {
      if (String(event.key || "") === "Escape" && String(input.value || "").trim()) {
        input.value = "";
        applyFilter();
        input.focus();
      }
    });
    if (clearButton) {
      clearButton.addEventListener("click", function () {
        input.value = "";
        applyFilter();
        input.focus();
      });
    }
    applyFilter();
  }

  function initSidebarFilter() {
    var navs = getRootSidebarNavs();
    if (!navs.length) {
      return;
    }
    Array.prototype.forEach.call(navs, function (nav) {
      initSidebarFilterForNav(nav);
    });
  }

  function initMobileSidebarMode() {
    var root = document.documentElement;
    var sidebar = document.querySelector("[data-mobile-sidebar-panel]");
    var openButtons = document.querySelectorAll("[data-mobile-sidebar-open]");
    var closeButtons = document.querySelectorAll("[data-mobile-sidebar-close]");
    if (!root || !sidebar || !openButtons.length) {
      return;
    }

    var sidebarMode = String(root.getAttribute("data-mobile-sidebar") || "static").toLowerCase();
    if (sidebarMode !== "collapsible") {
      return;
    }

    var defaultState = String(root.getAttribute("data-mobile-sidebar-default") || "closed").toLowerCase();
    var isOpen = defaultState === "open";
    var presentationMode = "contents";
    var titleNodes = sidebar.querySelectorAll(".mobile-sidebar-title, .sidebar-section-title");
    var presentationCloseButtons = sidebar.querySelectorAll("[data-mobile-sidebar-close], [data-sidebar-hide='right']");

    var getPresentationTitle = function (mode) {
      if (mode === "search") {
        return getUiString("search-panel-title", getUiString("search", "Search"));
      }
      return getUiString("website-contents", getUiString("contents", "Contents"));
    };

    var getTriggerLabel = function (mode) {
      if (mode === "search") {
        return getUiString("search", "Search");
      }
      return getUiString("contents", "Contents");
    };

    var getOpenLabel = function (mode) {
      if (mode === "search") {
        return getUiString("open-search", "Open search");
      }
      return getUiString("open-contents", "Open contents");
    };

    var getCloseLabel = function (mode) {
      if (mode === "search") {
        return getUiString("close-search", "Close search");
      }
      return getUiString("close-contents", "Close contents");
    };

    var applyPresentation = function (mode) {
      presentationMode = mode === "search" ? "search" : "contents";
      sidebar.setAttribute("data-mobile-sidebar-view", presentationMode);
      Array.prototype.forEach.call(titleNodes, function (node) {
        node.textContent = getPresentationTitle(presentationMode);
      });
      Array.prototype.forEach.call(presentationCloseButtons, function (button) {
        button.setAttribute("aria-label", getCloseLabel(presentationMode));
      });
    };

    Array.prototype.forEach.call(openButtons, function (button) {
      if (!button.hasAttribute("data-mobile-sidebar-label")) {
        button.setAttribute(
          "data-mobile-sidebar-label",
          String(button.textContent || "").trim() || getUiString("contents", "Contents")
        );
      }
    });

    var applyState = function (nextOpen) {
      isOpen = Boolean(nextOpen);
      if (!isOpen) {
        applyPresentation("contents");
      }
      document.body.classList.toggle("mobile-sidebar-open", isOpen);
      Array.prototype.forEach.call(openButtons, function (button) {
        button.setAttribute("aria-expanded", isOpen ? "true" : "false");
        button.setAttribute("aria-label", isOpen ? getCloseLabel(presentationMode) : getOpenLabel(presentationMode));
        button.textContent = isOpen
          ? getTriggerLabel(presentationMode)
          : (button.getAttribute("data-mobile-sidebar-label") || getUiString("contents", "Contents"));
      });
    };

    Array.prototype.forEach.call(openButtons, function (button) {
      button.addEventListener("click", function () {
        if (!isOpen) {
          applyPresentation("contents");
        }
        applyState(!isOpen);
      });
    });

    Array.prototype.forEach.call(closeButtons, function (button) {
      button.addEventListener("click", function () {
        applyState(false);
      });
    });

    Array.prototype.forEach.call(sidebar.querySelectorAll(".sidebar-link"), function (link) {
      link.addEventListener("click", function () {
        if (window.matchMedia && window.matchMedia("(max-width: 980px)").matches) {
          applyState(false);
        }
      });
    });

    document.addEventListener("keydown", function (event) {
      if (String(event.key || "") === "Escape") {
        applyState(false);
      }
    });

    document.body.__phoenixMobileSidebar = {
      isOpen: function () {
        return isOpen;
      },
      setOpen: function (nextOpen) {
        applyState(nextOpen);
      },
      setPresentation: function (mode) {
        applyPresentation(mode);
        if (isOpen) {
          applyState(true);
        }
      }
    };

    applyPresentation("contents");
    applyState(isOpen);
  }

  function initMobileQuickNav() {
    var quickSearchButtons = document.querySelectorAll("[data-quick-search]");
    if (!quickSearchButtons.length) {
      return;
    }

    var focusSearchInput = function () {
      var sidebarFilter = document.querySelector("[data-sidebar-filter]");
      if (sidebarFilter && typeof sidebarFilter.focus === "function") {
        sidebarFilter.focus();
        if (typeof sidebarFilter.select === "function") {
          sidebarFilter.select();
        }
        return;
      }
      var homeFilter = document.querySelector("[data-home-filter]");
      if (homeFilter && typeof homeFilter.focus === "function") {
        homeFilter.focus();
        return;
      }
      window.location.href = resolveSiteHref("/search/");
    };

    Array.prototype.forEach.call(quickSearchButtons, function (button) {
      button.addEventListener("click", function () {
        var sidebarController = document.body.__phoenixMobileSidebar || null;
        var openButton = document.querySelector("[data-mobile-sidebar-open]");
        var isMobile = Boolean(window.matchMedia && window.matchMedia("(max-width: 980px)").matches);
        var shouldOpenSidebar = Boolean(
          openButton
          && isMobile
          && (
            sidebarController
              ? !sidebarController.isOpen()
              : String(openButton.getAttribute("aria-expanded") || "false") !== "true"
          )
        );
        if (sidebarController && isMobile) {
          sidebarController.setPresentation("search");
        }
        if (shouldOpenSidebar) {
          if (sidebarController) {
            sidebarController.setOpen(true);
          } else {
            openButton.click();
          }
          window.setTimeout(focusSearchInput, 160);
          return;
        }
        focusSearchInput();
      });
    });
  }

  function initMobilePageTools() {
    var panel = document.querySelector("[data-mobile-page-tools]");
    var toc = document.querySelector("[data-mobile-page-toc]");
    var toggleButtons = document.querySelectorAll("[data-mobile-page-tools-toggle]");
    if (!panel || !toc) {
      return;
    }

    var mediaQuery = window.matchMedia ? window.matchMedia("(max-width: 980px)") : null;

    var syncState = function () {
      var hasToc = Boolean(toc.children.length);
      var isMobile = !mediaQuery || mediaQuery.matches;
      var isAvailable = hasToc && isMobile;
      panel.hidden = !isAvailable;
      if (!isAvailable) {
        panel.open = false;
      }
      Array.prototype.forEach.call(toggleButtons, function (button) {
        button.hidden = !isAvailable;
        button.setAttribute("aria-expanded", isAvailable && panel.open ? "true" : "false");
      });
    };

    Array.prototype.forEach.call(toggleButtons, function (button) {
      button.addEventListener("click", function () {
        syncState();
        if (panel.hidden) {
          return;
        }
        panel.open = !panel.open;
        button.setAttribute("aria-expanded", panel.open ? "true" : "false");
        if (panel.open && typeof panel.scrollIntoView === "function") {
          panel.scrollIntoView({ block: "start", behavior: "smooth" });
        }
      });
    });

    panel.addEventListener("toggle", function () {
      Array.prototype.forEach.call(toggleButtons, function (button) {
        button.setAttribute("aria-expanded", panel.open ? "true" : "false");
      });
    });

    if (mediaQuery) {
      if (typeof mediaQuery.addEventListener === "function") {
        mediaQuery.addEventListener("change", syncState);
      } else if (typeof mediaQuery.addListener === "function") {
        mediaQuery.addListener(syncState);
      }
    }

    document.addEventListener("phoenix-page-toc-built", syncState);
    syncState();
  }

  function initSidebarDocking() {
    var body = document.body;
    var root = document.documentElement;
    if (!body || !root) {
      return;
    }

    var sidePresent = {
      left: Boolean(document.querySelector("[data-page-tools]")),
      right: Boolean(document.querySelector("[data-mobile-sidebar-panel]"))
    };
    if (!sidePresent.left && !sidePresent.right) {
      return;
    }

    var sides = ["left", "right"];
    var classBySide = {
      left: "left-sidebar-collapsed",
      right: "right-sidebar-collapsed"
    };
    var storageBySide = {
      left: "phoenix-sidebar-left-collapsed",
      right: "phoenix-sidebar-right-collapsed"
    };
    var toastTimers = {
      left: null,
      right: null
    };
    var toastMs = parseInt(root.getAttribute("data-appearance-toast-ms"), 10);
    if (!Number.isFinite(toastMs) || toastMs < 1000) {
      toastMs = 5000;
    }

    function readStorage(key) {
      try {
        return window.localStorage.getItem(key);
      } catch (err) {
        return null;
      }
    }

    function writeStorage(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch (err) {
        // Ignore storage write failures.
      }
    }

    function hasStoredCollapsed(side) {
      return String(readStorage(storageBySide[side]) || "").trim() !== "";
    }

    function getDock(side) {
      return document.querySelector('[data-sidebar-dock="' + side + '"]');
    }

    function getDockToggle(side) {
      return document.querySelector('[data-sidebar-dock-toggle="' + side + '"]');
    }

    function getDockMenu(side) {
      return document.querySelector('[data-sidebar-dock-menu="' + side + '"]');
    }

    function getDockToast(side) {
      return document.querySelector('[data-sidebar-dock-toast="' + side + '"]');
    }

    function closeDockMenu(side) {
      var menu = getDockMenu(side);
      var toggle = getDockToggle(side);
      if (menu) {
        menu.hidden = true;
      }
      if (toggle) {
        toggle.setAttribute("aria-expanded", "false");
      }
    }

    function hideDockToast(side) {
      var toast = getDockToast(side);
      if (toast) {
        toast.hidden = true;
      }
      if (toastTimers[side]) {
        window.clearTimeout(toastTimers[side]);
        toastTimers[side] = null;
      }
    }

    function showDockToast(side) {
      var toast = getDockToast(side);
      if (!toast) {
        return;
      }
      hideDockToast(side);
      toast.hidden = false;
      toastTimers[side] = window.setTimeout(function () {
        toast.hidden = true;
        toastTimers[side] = null;
      }, toastMs);
    }

    function readCollapsed(side) {
      var token = String(readStorage(storageBySide[side]) || "").trim().toLowerCase();
      return token === "1" || token === "true" || token === "yes" || token === "on";
    }

    function getDefaultCollapsed(side) {
      if (!body.classList.contains("page-article")) {
        return false;
      }
      var isDesktop = !(window.matchMedia && window.matchMedia("(max-width: 980px)").matches);
      if (!isDesktop) {
        return false;
      }
      return side === "left" || side === "right";
    }

    function setCollapsed(side, shouldCollapse, options) {
      var opts = options || {};
      var className = classBySide[side];
      if (!className) {
        return;
      }
      var collapsed = Boolean(shouldCollapse && sidePresent[side]);
      body.classList.toggle(className, collapsed);
      var dock = getDock(side);
      if (dock) {
        dock.hidden = !collapsed;
      }
      if (!collapsed) {
        closeDockMenu(side);
        hideDockToast(side);
      } else if (opts.showToast) {
        showDockToast(side);
      }

      if (opts.persist) {
        writeStorage(storageBySide[side], collapsed ? "1" : "0");
      }
    }

    Array.prototype.forEach.call(document.querySelectorAll("[data-sidebar-hide]"), function (button) {
      var side = String(button.getAttribute("data-sidebar-hide") || "").trim().toLowerCase();
      if (!classBySide[side] || !sidePresent[side]) {
        button.hidden = true;
      }
    });

    Array.prototype.forEach.call(document.querySelectorAll("[data-sidebar-restore]"), function (button) {
      var side = String(button.getAttribute("data-sidebar-restore") || "").trim().toLowerCase();
      if (!classBySide[side] || !sidePresent[side]) {
        button.hidden = true;
      }
    });

    document.addEventListener("click", function (event) {
      var hideButton = event.target && event.target.closest ? event.target.closest("[data-sidebar-hide]") : null;
      if (hideButton) {
        var hideSide = String(hideButton.getAttribute("data-sidebar-hide") || "").trim().toLowerCase();
        if (classBySide[hideSide] && sidePresent[hideSide]) {
          event.preventDefault();
          event.stopPropagation();
          setCollapsed(hideSide, true, { persist: true, showToast: true });
        }
        return;
      }

      var restoreButton = event.target && event.target.closest ? event.target.closest("[data-sidebar-restore]") : null;
      if (restoreButton) {
        var restoreSide = String(restoreButton.getAttribute("data-sidebar-restore") || "").trim().toLowerCase();
        if (classBySide[restoreSide] && sidePresent[restoreSide]) {
          event.preventDefault();
          event.stopPropagation();
          setCollapsed(restoreSide, false, { persist: true });
        }
        return;
      }

      var dockToggleButton = event.target && event.target.closest ? event.target.closest("[data-sidebar-dock-toggle]") : null;
      if (dockToggleButton) {
        var dockSide = String(dockToggleButton.getAttribute("data-sidebar-dock-toggle") || "").trim().toLowerCase();
        if (classBySide[dockSide] && sidePresent[dockSide]) {
          event.preventDefault();
          event.stopPropagation();
          hideDockToast(dockSide);
          closeDockMenu(dockSide);
          setCollapsed(dockSide, false, { persist: true });
        }
        return;
      }
    });

    document.addEventListener("click", function (event) {
      var target = event.target;
      if (target && target.closest && target.closest("[data-sidebar-dock]")) {
        return;
      }
      Array.prototype.forEach.call(sides, function (side) {
        closeDockMenu(side);
      });
    });

    document.addEventListener("keydown", function (event) {
      if (String(event.key || "") !== "Escape") {
        return;
      }
      Array.prototype.forEach.call(sides, function (side) {
        closeDockMenu(side);
      });
    });

    Array.prototype.forEach.call(sides, function (side) {
      var collapsed = hasStoredCollapsed(side) ? readCollapsed(side) : getDefaultCollapsed(side);
      setCollapsed(side, collapsed, { persist: false, showToast: false });
    });
  }

  function initHomeResponsiveDisclosures() {
    var body = document.body;
    if (!body || !body.classList.contains("page-home")) {
      return;
    }

    var disclosures = document.querySelectorAll("[data-home-mobile-disclosure]");
    if (!disclosures.length) {
      return;
    }

    var requestCatalogMode = function () {
      try {
        document.dispatchEvent(
          new CustomEvent("phoenix-home-mode-request", {
            detail: {
              mode: "catalog",
              persist: true,
              syncUrl: true
            }
          })
        );
      } catch (err) {
        // Ignore custom event dispatch failures.
      }
    };

    var getCollapseThreshold = function (node) {
      var parsed = parseInt(String(node && node.getAttribute("data-home-mobile-collapse-threshold") || ""), 10);
      return Number.isFinite(parsed) && parsed > 0 ? parsed : 800;
    };

    var shouldCollapseDisclosure = function (node) {
      var threshold = getCollapseThreshold(node);
      return window.innerWidth <= threshold;
    };

    var shouldForceOpenDisclosure = function (node) {
      if (!node) {
        return false;
      }
      var currentHash = String(window.location.hash || "").trim();
      if (currentHash && node.id && currentHash === "#" + node.id) {
        return true;
      }
      var searchInput = node.querySelector("[data-home-filter]");
      return !!(searchInput && String(searchInput.value || "").trim());
    };

    var syncDisclosureState = function (node, force) {
      if (!node) {
        return;
      }
      if (!force && node.__homeMobileDisclosureTouched) {
        return;
      }
      var shouldCollapse = shouldCollapseDisclosure(node);
      var shouldOpen = !shouldCollapse || shouldForceOpenDisclosure(node);
      node.__homeMobileDisclosureSyncing = true;
      if (shouldOpen) {
        node.setAttribute("open", "open");
      } else {
        node.removeAttribute("open");
      }
      node.__homeMobileDisclosureSyncing = false;
      node.__homeMobileDisclosureViewport = shouldCollapse ? "mobile" : "desktop";
    };

    var syncAllDisclosures = function (force) {
      Array.prototype.forEach.call(disclosures, function (node) {
        syncDisclosureState(node, force);
      });
    };

    Array.prototype.forEach.call(disclosures, function (node) {
      if (!node.__homeMobileDisclosureBound) {
        node.__homeMobileDisclosureBound = true;
        node.addEventListener("toggle", function () {
          if (node.__homeMobileDisclosureSyncing) {
            return;
          }
          node.__homeMobileDisclosureTouched = true;
          var searchInput = node.querySelector("[data-home-filter]");
          if (node.hasAttribute("open") && searchInput) {
            requestCatalogMode();
            window.setTimeout(function () {
              if (typeof searchInput.focus === "function") {
                searchInput.focus();
              }
            }, 0);
          }
        });
        var searchInput = node.querySelector("[data-home-filter]");
        if (searchInput) {
          var openDisclosure = function () {
            node.setAttribute("open", "open");
          };
          var focusCatalogSearch = function () {
            openDisclosure();
            requestCatalogMode();
          };
          searchInput.addEventListener("focus", focusCatalogSearch);
          searchInput.addEventListener("input", focusCatalogSearch);
        }
      }
    });

    var lastMobileState = shouldCollapseDisclosure(disclosures[0]);
    syncAllDisclosures(false);

    window.addEventListener("hashchange", function () {
      Array.prototype.forEach.call(disclosures, function (node) {
        if (shouldForceOpenDisclosure(node)) {
          node.setAttribute("open", "open");
        }
      });
    });

    window.addEventListener("resize", function () {
      var currentMobileState = shouldCollapseDisclosure(disclosures[0]);
      if (currentMobileState === lastMobileState) {
        return;
      }
      lastMobileState = currentMobileState;
      syncAllDisclosures(false);
    });
  }

  function initHomeModeSwitcher() {
    var body = document.body;
    if (!body || !body.classList.contains("page-home")) {
      return;
    }

    var switcher = document.querySelector("[data-home-mode-switcher]");
    var panels = document.querySelectorAll("[data-home-mode-panel]");
    if (!switcher || !panels.length) {
      return;
    }

    var normalizeRawMode = function (value) {
      var token = String(value || "").trim().toLowerCase();
      return (token === "cluster" || token === "catalog") ? token : "";
    };

    var normalizePanelMode = function (value) {
      var token = String(value || "").trim().toLowerCase();
      return (token === "cluster" || token === "catalog") ? token : "";
    };

    var modeLabels = {
      cluster: "Tree view",
      catalog: "Catalog"
    };
    Array.prototype.forEach.call(panels, function (panel) {
      var panelMode = normalizePanelMode(panel.getAttribute("data-home-mode-panel"));
      var panelLabel = String(panel.getAttribute("data-home-mode-label") || "").trim();
      if (panelMode && panelLabel) {
        modeLabels[panelMode] = panelLabel;
      }
    });

    var configuredMode = normalizeRawMode(switcher.getAttribute("data-home-initial-mode")) || "catalog";
    var selectedMode = normalizePanelMode(switcher.getAttribute("data-home-selected-mode")) || "catalog";
    var buttons = switcher.querySelectorAll("[data-home-mode-btn]");
    var cycleButton = switcher.querySelector("[data-home-mode-cycle]");
    var summaryCurrentNodes = switcher.querySelectorAll("[data-home-mode-summary-current], [data-home-mode-summary-current-visual]");
    var pathParts = normalizePath(window.location.pathname).split("/").filter(Boolean);
    var siteScope = pathParts.length ? pathParts[0] : "root";
    var storageKey = "phoenix-home-mode-v1-" + siteScope;
    var clusterMinWidth = parseInt(String(switcher.getAttribute("data-home-cluster-min-width") || "980"), 10);
    if (!Number.isFinite(clusterMinWidth) || clusterMinWidth < 320) {
      clusterMinWidth = 980;
    }
    var panelAvailability = {};
    Array.prototype.forEach.call(panels, function (panel) {
      var panelMode = normalizePanelMode(panel.getAttribute("data-home-mode-panel"));
      if (panelMode) {
        panelAvailability[panelMode] = true;
      }
    });
    var rawModeSequence = String(switcher.getAttribute("data-home-mode-sequence") || "")
      .split(/\s+/)
      .map(normalizeRawMode)
      .filter(function (token, index, source) {
        return !!token && source.indexOf(token) === index && !!panelAvailability[token];
      });
    if (!rawModeSequence.length) {
      rawModeSequence = ["catalog"];
      if (panelAvailability.cluster) {
        rawModeSequence.push("cluster");
      }
    }

    function isClusterModeAvailable() {
      return !!panelAvailability.cluster && window.innerWidth >= clusterMinWidth;
    }

    var resolveEffectiveMode = function (rawMode) {
      var normalized = normalizeRawMode(rawMode);
      if (normalized === "cluster" && isClusterModeAvailable()) {
        return "cluster";
      }
      return "catalog";
    };

    var updateTopicJumpLinks = function (effectiveMode) {
      if (!effectiveMode) {
        return;
      }
      var jumpLinks = document.querySelectorAll("[data-home-topic-anchor]");
      Array.prototype.forEach.call(jumpLinks, function (link) {
        var anchorToken = String(link.getAttribute("data-home-topic-anchor") || "").trim();
        var clusterBase = String(link.getAttribute("data-home-cluster-base") || "").trim();
        if (effectiveMode === "cluster" && clusterBase) {
          link.setAttribute("href", "#home-cluster-map");
          link.setAttribute("data-home-cluster-jump", clusterBase);
          return;
        }
        if (link.hasAttribute("data-home-cluster-jump")) {
          link.removeAttribute("data-home-cluster-jump");
        }
        if (!anchorToken) {
          return;
        }
        link.setAttribute("href", "#topic-" + effectiveMode + "-" + anchorToken);
      });
    };

    var persistModeInUrl = function (rawMode) {
      if (!window.history || typeof window.history.replaceState !== "function") {
        return;
      }
      var hasUrlApi = typeof URL !== "undefined";
      if (!hasUrlApi) {
        return;
      }
      try {
        var url = new URL(window.location.href);
        var normalizedRaw = resolveEffectiveMode(rawMode);
        if (!isClusterModeAvailable() || !panelAvailability.cluster || !normalizedRaw || normalizedRaw === configuredMode) {
          url.searchParams.delete("home_mode");
        } else {
          url.searchParams.set("home_mode", normalizedRaw);
        }
        window.history.replaceState(null, "", url.toString());
      } catch (err) {
        // Ignore URL write failures.
      }
    };

    var updateSummaryCurrent = function (effectiveMode) {
      Array.prototype.forEach.call(summaryCurrentNodes, function (node) {
        node.textContent = modeLabels[effectiveMode] || "Catalog";
      });
    };

    var syncModeControls = function (effectiveMode) {
      var availableModes = rawModeSequence.filter(function (token) {
        return token === "catalog" || isClusterModeAvailable();
      });
      Array.prototype.forEach.call(buttons, function (button) {
        var buttonMode = normalizeRawMode(button.getAttribute("data-home-mode-btn"));
        var isAvailable = buttonMode === "catalog" || isClusterModeAvailable();
        button.hidden = !isAvailable;
        button.disabled = !isAvailable;
        if (isAvailable) {
          visibleCount += 1;
        }
        var isActiveButton = isAvailable && buttonMode === effectiveMode;
        button.classList.toggle("is-active", isActiveButton);
        button.setAttribute("aria-pressed", isActiveButton ? "true" : "false");
      });
      if (cycleButton) {
        var currentIndex = availableModes.indexOf(effectiveMode);
        if (currentIndex < 0) {
          currentIndex = 0;
        }
        var nextMode = availableModes[(currentIndex + 1) % Math.max(availableModes.length, 1)] || effectiveMode;
        var nextLabel = modeLabels[nextMode] || "Catalog";
        var currentLabel = modeLabels[effectiveMode] || "Catalog";
        var title = "Current view: " + currentLabel + ". Click to switch to " + nextLabel + ".";
        cycleButton.hidden = availableModes.length <= 1;
        cycleButton.disabled = availableModes.length <= 1;
        cycleButton.setAttribute("title", title);
        cycleButton.setAttribute("aria-label", title);
        cycleButton.setAttribute("data-home-next-mode", nextMode);
      }
      switcher.hidden = availableModes.length <= 1;
    };

    var activateMode = function (rawMode, options) {
      var normalizedRaw = normalizeRawMode(rawMode) || configuredMode || "catalog";
      var effectiveMode = resolveEffectiveMode(normalizedRaw);
      if (!effectiveMode) {
        effectiveMode = selectedMode;
      }
      normalizedRaw = effectiveMode;

      Array.prototype.forEach.call(panels, function (panel) {
        var panelMode = normalizePanelMode(panel.getAttribute("data-home-mode-panel"));
        var isActive = panelMode === effectiveMode;
        panel.hidden = !isActive;
        panel.classList.toggle("is-active", isActive);
      });

      switcher.setAttribute("data-home-mode-raw", normalizedRaw);
      switcher.setAttribute("data-home-mode-effective", effectiveMode);
      updateTopicJumpLinks(effectiveMode);
      updateSummaryCurrent(effectiveMode);
      syncModeControls(effectiveMode);

      var shouldPersist = (!options || options.persist !== false) && isClusterModeAvailable() && !!panelAvailability.cluster;
      if (shouldPersist) {
        writeLocalStorage(storageKey, normalizedRaw);
      } else {
        removeLocalStorage(storageKey);
      }
      var shouldSyncUrl = !options || options.syncUrl !== false;
      if (shouldSyncUrl) {
        persistModeInUrl(normalizedRaw);
      }

      try {
        document.dispatchEvent(
          new CustomEvent("phoenix-home-mode-changed", {
            detail: {
              rawMode: normalizedRaw,
              effectiveMode: effectiveMode,
              clusterAvailable: isClusterModeAvailable()
            }
          })
        );
      } catch (err) {
        // Ignore custom event dispatch failures.
      }
    };

    var queryMode = "";
    try {
      var params = new URLSearchParams(window.location.search || "");
      queryMode = normalizeRawMode(params.get("home_mode"));
    } catch (err) {
      queryMode = "";
    }
    var storedMode = normalizeRawMode(readLocalStorage(storageKey));
    var startMode = queryMode || storedMode || configuredMode || "catalog";

    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function () {
        var nextMode = normalizeRawMode(button.getAttribute("data-home-mode-btn")) || "catalog";
        activateMode(nextMode, { persist: true, syncUrl: true });
      });
    });
    if (cycleButton) {
      cycleButton.addEventListener("click", function () {
        var nextMode = normalizeRawMode(cycleButton.getAttribute("data-home-next-mode")) || "catalog";
        activateMode(nextMode, { persist: true, syncUrl: true });
      });
    }

    document.addEventListener("phoenix-home-mode-request", function (event) {
      var detail = event && event.detail ? event.detail : {};
      var requestedMode = normalizeRawMode(detail.mode);
      if (!requestedMode) {
        return;
      }
      activateMode(requestedMode, {
        persist: detail.persist !== false,
        syncUrl: detail.syncUrl !== false
      });
    });

    var lastClusterAvailability = isClusterModeAvailable();
    window.addEventListener("resize", function () {
      var nextClusterAvailability = isClusterModeAvailable();
      if (nextClusterAvailability === lastClusterAvailability) {
        return;
      }
      lastClusterAvailability = nextClusterAvailability;
      var currentRawMode = normalizeRawMode(switcher.getAttribute("data-home-mode-raw")) || startMode;
      activateMode(currentRawMode, { persist: true, syncUrl: true });
    });

    activateMode(startMode, { persist: true, syncUrl: true });
  }

  function initHomeFilter() {
    var input = document.querySelector("[data-home-filter]");
    var status = document.querySelector("[data-home-filter-status]");
    var clearButton = document.querySelector("[data-home-filter-clear]");
    var allCards = document.querySelectorAll(".topic-card[data-card-search]");
    if (!input || !allCards.length) {
      return;
    }
    var allDisclosures = document.querySelectorAll("[data-home-disclosure]");
    var pathParts = normalizePath(window.location.pathname).split("/").filter(Boolean);
    var siteScope = pathParts.length ? pathParts[0] : "root";
    var disclosureStorageKey = "phoenix-home-disclosure-state-v1-" + siteScope;
    var disclosureState = {};
    try {
      var rawDisclosureState = String(readLocalStorage(disclosureStorageKey) || "").trim();
      if (rawDisclosureState) {
        var parsedDisclosureState = JSON.parse(rawDisclosureState);
        if (parsedDisclosureState && typeof parsedDisclosureState === "object") {
          disclosureState = parsedDisclosureState;
        }
      }
    } catch (err) {
      disclosureState = {};
    }

    var getDisclosureKey = function (node, index) {
      if (!node) {
        return "";
      }
      var explicitKey = String(node.getAttribute("data-home-disclosure-key") || "").trim();
      if (explicitKey) {
        return explicitKey;
      }
      var summary = node.querySelector("summary");
      var label = String((summary && summary.textContent) || "").trim().toLowerCase();
      if (label) {
        return "home-" + slugify(label);
      }
      return "home-disclosure-" + String(index || 0);
    };

    var persistDisclosureState = function (node, index) {
      var key = getDisclosureKey(node, index);
      if (!key) {
        return;
      }
      disclosureState[key] = node.hasAttribute("open") ? 1 : 0;
      try {
        writeLocalStorage(disclosureStorageKey, JSON.stringify(disclosureState));
      } catch (err) {
        // Ignore storage write failures.
      }
    };

    var setDisclosureOpen = function (node, shouldOpen) {
      if (!node) {
        return;
      }
      if (shouldOpen) {
        node.setAttribute("open", "open");
      } else {
        node.removeAttribute("open");
      }
    };

    var restoreDisclosureDefaults = function (targetDisclosures) {
      Array.prototype.forEach.call(targetDisclosures || allDisclosures, function (node, index) {
        var disclosureKey = getDisclosureKey(node, index);
        var storedToken = disclosureKey ? disclosureState[disclosureKey] : null;
        var hasStoredState = storedToken === 0 || storedToken === 1 || storedToken === true || storedToken === false;
        var defaultOpen = String(node.getAttribute("data-default-open") || "").toLowerCase() === "true";
        setDisclosureOpen(node, hasStoredState ? (storedToken === 1 || storedToken === true) : defaultOpen);
      });
    };

    var getUniqueCount = function (nodeList) {
      var seen = Object.create(null);
      var fallbackCount = 0;
      Array.prototype.forEach.call(nodeList, function (card) {
        var baseKey = String(card.getAttribute("data-card-base") || "").trim();
        if (!baseKey) {
          fallbackCount += 1;
          return;
        }
        seen[baseKey] = true;
      });
      return Object.keys(seen).length + fallbackCount;
    };

    var getActiveModePanel = function () {
      return document.querySelector("[data-home-mode-panel].is-active") || document.querySelector("[data-home-mode-panel]");
    };

    var collectFilterContext = function () {
      var contextCards = [];
      var addCard = function (card) {
        if (!card || contextCards.indexOf(card) !== -1) {
          return;
        }
        contextCards.push(card);
      };

      var activePanel = getActiveModePanel();
      if (activePanel) {
        Array.prototype.forEach.call(activePanel.querySelectorAll(".topic-card[data-card-search]"), addCard);
      }
      Array.prototype.forEach.call(document.querySelectorAll(".home-featured .topic-card[data-card-search]"), addCard);

      if (!contextCards.length) {
        Array.prototype.forEach.call(allCards, addCard);
      }

      return {
        cards: contextCards,
        disclosures: activePanel ? activePanel.querySelectorAll("[data-home-disclosure]") : allDisclosures
      };
    };

    var applyFilter = function () {
      var query = String(input.value || "").trim().toLowerCase();
      var activePanelBeforeFilter = getActiveModePanel();
      var activeModeBeforeFilter = activePanelBeforeFilter
        ? String(activePanelBeforeFilter.getAttribute("data-home-mode-panel") || "").trim().toLowerCase()
        : "";
      if (query && activeModeBeforeFilter !== "catalog") {
        try {
          document.dispatchEvent(
            new CustomEvent("phoenix-home-mode-request", {
              detail: {
                mode: "catalog",
                persist: true,
                syncUrl: true
              }
            })
          );
        } catch (err) {
          // Ignore custom event dispatch failures.
        }
      }

      var context = collectFilterContext();
      var cards = context.cards;
      var disclosures = context.disclosures;
      var visibleCards = [];

      Array.prototype.forEach.call(allCards, function (card) {
        if (cards.indexOf(card) === -1) {
          card.classList.remove("is-filtered-out");
        }
      });

      Array.prototype.forEach.call(cards, function (card) {
        var haystack = String(card.getAttribute("data-card-search") || card.textContent || "").toLowerCase();
        var show = matchesSearchQuery(query, haystack);
        card.classList.toggle("is-filtered-out", !show);
        card.classList.toggle("is-search-match", Boolean(query && show));
        if (show) {
          visibleCards.push(card);
        }
      });

      if (query) {
        Array.prototype.forEach.call(disclosures, function (node) {
          var hasVisibleMatch = visibleCards.some(function (card) {
            return Boolean(node && card && node.contains(card));
          });
          setDisclosureOpen(node, hasVisibleMatch);
        });
      } else {
        restoreDisclosureDefaults(disclosures);
      }

      if (status) {
        var totalUniqueReports = getUniqueCount(cards);
        var visibleUnique = getUniqueCount(visibleCards);
        if (!query) {
          status.setAttribute("data-state", "default");
          status.textContent = "All " + String(totalUniqueReports) + " pages visible.";
        } else if (!visibleUnique) {
          status.setAttribute("data-state", "empty");
          status.textContent = "No pages match \"" + query + "\". Try a broader section or keyword.";
        } else {
          status.setAttribute("data-state", "active");
          status.textContent = "Showing " + String(visibleUnique) + " of " + String(totalUniqueReports) + " pages for \"" + query + "\".";
        }
      }

      if (clearButton) {
        clearButton.hidden = !query;
      }
    };
    input.addEventListener("input", applyFilter);
    input.addEventListener("keydown", function (event) {
      if (String(event.key || "") === "Escape" && String(input.value || "").trim()) {
        input.value = "";
        applyFilter();
      }
    });
    if (clearButton) {
      clearButton.addEventListener("click", function () {
        input.value = "";
        applyFilter();
        input.focus();
      });
    }
    Array.prototype.forEach.call(allDisclosures, function (node, index) {
      node.addEventListener("toggle", function () {
        if (String(input.value || "").trim()) {
          return;
        }
        persistDisclosureState(node, index);
      });
    });
    document.addEventListener("phoenix-home-mode-changed", function () {
      applyFilter();
    });
    applyFilter();
  }

  function scoreArchiveSearchResult(item, query) {
    var normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) {
      return 0;
    }
    var tokens = getSearchTokens(normalizedQuery);
    var title = normalizeSearchText(item && (item.title_text || item.title));
    var urlText = normalizeSearchText(item && (item.url_text || item.url));
    var section = normalizeSearchText(item && (item.section_text || item.section));
    var summary = normalizeSearchText(item && (item.summary_text || item.summary));
    var tags = normalizeSearchText(item && (item.tags_text || (item.tags ? item.tags.join(" ") : "")));
    var headings = normalizeSearchText(item && item.headings_text);
    var body = normalizeSearchText(item && item.body_text);
    var haystack = normalizeSearchText(item && item.search_text);
    var score = 0;
    var titleMatches = countSearchTokenMatches(title, tokens);
    var urlMatches = countSearchTokenMatches(urlText, tokens);
    var sectionMatches = countSearchTokenMatches(section, tokens);
    var summaryMatches = countSearchTokenMatches(summary, tokens);
    var tagMatches = countSearchTokenMatches(tags, tokens);
    var headingMatches = countSearchTokenMatches(headings, tokens);
    var bodyMatches = countSearchTokenMatches(body, tokens);
    var metadataMatches = countSearchTokenMatches([title, urlText, section, summary, tags, headings].join(" "), tokens);

    if (title === normalizedQuery) {
      score += 2400;
    } else if (title.indexOf(normalizedQuery) === 0) {
      score += 1500;
    } else if (title.indexOf(normalizedQuery) !== -1) {
      score += 900;
    }

    if (urlText === normalizedQuery) {
      score += 1800;
    } else if (urlText.indexOf(normalizedQuery) === 0) {
      score += 900;
    } else if (urlText.indexOf(normalizedQuery) !== -1) {
      score += 650;
    }

    if (tags === normalizedQuery) {
      score += 1100;
    } else if (tags.indexOf(normalizedQuery) !== -1) {
      score += 700;
    }

    if (headings.indexOf(normalizedQuery) !== -1) {
      score += 360;
    }

    if (section.indexOf(normalizedQuery) !== -1) {
      score += 240;
    }

    if (summary.indexOf(normalizedQuery) !== -1) {
      score += 180;
    }

    if (body.indexOf(normalizedQuery) !== -1) {
      score += 30;
    }

    score += titleMatches * 140;
    score += urlMatches * 115;
    score += tagMatches * 90;
    score += headingMatches * 54;
    score += sectionMatches * 38;
    score += summaryMatches * 24;
    score += bodyMatches * 4;

    if (tokens.length && titleMatches === tokens.length) {
      score += 1200;
    }
    if (tokens.length && (titleMatches + urlMatches) >= tokens.length) {
      score += 760;
    }
    if (tokens.length && (titleMatches + urlMatches + tagMatches) >= tokens.length) {
      score += 540;
    }
    if (tokens.length && metadataMatches === tokens.length) {
      score += 320;
    }
    if (tokens.length > 1 && summaryMatches === tokens.length) {
      score += 120;
    }

    if (haystack.indexOf(normalizedQuery) !== -1) {
      score += 40;
    }

    if ((item && item.kind) === "page") {
      score += 24;
    } else if ((item && item.kind) === "tag") {
      score += (tagMatches || tags.indexOf(normalizedQuery) !== -1) ? 20 : 4;
    } else if ((item && item.kind) === "section") {
      score += (sectionMatches || titleMatches) ? 12 : 6;
    }

    return score;
  }

  function createArchiveSearchResultCard(item) {
    var article = document.createElement("article");
    var hasPreview = Boolean(item && item.preview_image);
    article.className = hasPreview ? "fr-search-card fr-search-card-visual" : "fr-search-card";

    var mediaLink = document.createElement("a");
    mediaLink.className = hasPreview ? "fr-search-cover" : "fr-search-cover fr-search-cover-placeholder";
    mediaLink.href = resolveSiteHref(item && item.url ? item.url : "/search/");
    mediaLink.title = String(item && item.title || "Search result");

    if (hasPreview) {
      var image = document.createElement("img");
      image.src = resolveSiteHref(item.preview_image);
      image.alt = "Preview for " + String(item && item.title || "Search result");
      image.loading = "lazy";
      image.decoding = "async";
      image.referrerPolicy = "no-referrer";
      image.addEventListener("error", function () {
        mediaLink.classList.add("fr-search-cover-placeholder");
        mediaLink.textContent = "";
        var fallback = document.createElement("span");
        fallback.textContent = String((item && item.title || "?").charAt(0) || "?").toUpperCase();
        mediaLink.appendChild(fallback);
      }, { once: true });
      mediaLink.appendChild(image);
    } else {
      var placeholder = document.createElement("span");
      placeholder.textContent = String((item && item.title || "?").charAt(0) || "?").toUpperCase();
      mediaLink.appendChild(placeholder);
    }
    article.appendChild(mediaLink);

    var info = document.createElement("div");
    info.className = "fr-search-info";

    var kicker = document.createElement("p");
    kicker.className = "fr-search-kicker";
    kicker.textContent = String(item && item.kicker || "Page");
    info.appendChild(kicker);

    var title = document.createElement("h2");
    title.className = "fr-search-title";
    var titleLink = document.createElement("a");
    titleLink.href = resolveSiteHref(item && item.url ? item.url : "/search/");
    titleLink.textContent = String(item && item.title || "Untitled");
    title.appendChild(titleLink);
    info.appendChild(title);

    if (item && item.summary) {
      var summary = document.createElement("p");
      summary.className = "fr-search-desc";
      summary.textContent = String(item.summary);
      info.appendChild(summary);
    }

    var metaParts = [];
    if (item && item.section) {
      metaParts.push(String(item.section));
    }
    if (item && item.kind && item.kind !== "page") {
      metaParts.push(String(item.kind).charAt(0).toUpperCase() + String(item.kind).slice(1));
    }
    if (metaParts.length) {
      var meta = document.createElement("p");
      meta.className = "archive-search-meta";
      meta.textContent = metaParts.join(" · ");
      info.appendChild(meta);
    }

    if (item && item.tags && item.tags.length) {
      var tagRow = document.createElement("div");
      tagRow.className = "fr-search-tags";
      item.tags.slice(0, 6).forEach(function (label) {
        var chip = document.createElement("span");
        chip.className = "fr-search-tag";
        chip.textContent = String(label);
        tagRow.appendChild(chip);
      });
      info.appendChild(tagRow);
    }

    article.appendChild(info);
    return article;
  }

  function initArchiveSearch() {
    var root = document.querySelector("[data-archive-search]");
    if (!root) {
      return;
    }
    var source = String(root.getAttribute("data-search-source") || "").trim();
    var pageSize = Math.max(1, parseInt(root.getAttribute("data-search-page-size") || "48", 10) || 48);
    var form = root.querySelector("[data-archive-search-form]");
    var input = root.querySelector("[data-archive-search-input]");
    var clearButton = root.querySelector("[data-archive-search-clear]");
    var status = root.querySelector("[data-archive-search-status]");
    var results = root.querySelector("[data-archive-search-results]");
    if (!source || !form || !input || !results) {
      return;
    }

    var loadedEntries = [];
    var loadPromise = null;
    var inputTimer = 0;

    var setStatus = function (message, state) {
      if (!status) {
        return;
      }
      status.textContent = String(message || "");
      if (state) {
        status.setAttribute("data-state", state);
      } else {
        status.removeAttribute("data-state");
      }
    };

    var renderEmptyState = function (message) {
      results.innerHTML = "";
      var empty = document.createElement("div");
      empty.className = "archive-search-empty";
      var paragraph = document.createElement("p");
      paragraph.textContent = message;
      empty.appendChild(paragraph);
      results.appendChild(empty);
    };

    var syncUrl = function (query) {
      if (!window.history || typeof window.history.replaceState !== "function") {
        return;
      }
      var url = new URL(window.location.href);
      var normalized = String(query || "").trim();
      if (normalized) {
        url.searchParams.set("q", normalized);
      } else {
        url.searchParams.delete("q");
      }
      window.history.replaceState({}, "", url.toString());
    };

    var ensureLoaded = function () {
      if (loadPromise) {
        return loadPromise;
      }
      setStatus("Loading search index...", "loading");
      loadPromise = fetch(source, { credentials: "same-origin" })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("Search index request failed with " + String(response.status));
          }
          return response.json();
        })
        .then(function (payload) {
          loadedEntries = Array.isArray(payload) ? payload : [];
          return loadedEntries;
        });
      return loadPromise;
    };

    var applySearch = function () {
      var query = String(input.value || "").trim();
      syncUrl(query);
      if (clearButton) {
        clearButton.hidden = !query;
      }
      ensureLoaded()
        .then(function (entries) {
          if (!query) {
            setStatus("Loaded " + String(entries.length) + " archive entries. Enter keywords to search the archive.", "default");
            renderEmptyState("Enter a keyword to search across titles, summaries, headings, tags, and section labels.");
            return;
          }

          var matches = entries
            .filter(function (entry) {
              return matchesArchiveSearchEntry(query, entry);
            })
            .map(function (entry, index) {
              return {
                item: entry,
                score: scoreArchiveSearchResult(entry, query),
                index: index
              };
            })
            .sort(function (left, right) {
              if (right.score !== left.score) {
                return right.score - left.score;
              }
              var leftTitle = String(left.item && left.item.title || "");
              var rightTitle = String(right.item && right.item.title || "");
              if (leftTitle !== rightTitle) {
                return leftTitle.localeCompare(rightTitle);
              }
              return left.index - right.index;
            });

          results.innerHTML = "";
          if (!matches.length) {
            setStatus("No archive entries match \"" + query + "\". Try a broader year, person, tag, or case name.", "empty");
            renderEmptyState("No results for \"" + query + "\". Try a broader year, case, author, personality, place, or tag.");
            return;
          }

          matches.slice(0, pageSize).forEach(function (entry) {
            results.appendChild(createArchiveSearchResultCard(entry.item));
          });
          var visibleCount = Math.min(matches.length, pageSize);
          if (matches.length > visibleCount) {
            setStatus("Showing " + String(visibleCount) + " of " + String(matches.length) + " results for \"" + query + "\".", "active");
          } else {
            setStatus("Showing " + String(matches.length) + " results for \"" + query + "\".", "active");
          }
        })
        .catch(function () {
          setStatus("Search is temporarily unavailable because the archive index could not be loaded.", "empty");
          renderEmptyState("Search is temporarily unavailable because the archive index could not be loaded.");
        });
    };

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      applySearch();
    });
    input.addEventListener("input", function () {
      window.clearTimeout(inputTimer);
      inputTimer = window.setTimeout(applySearch, 120);
    });
    input.addEventListener("keydown", function (event) {
      if (String(event.key || "") === "Escape" && String(input.value || "").trim()) {
        input.value = "";
        applySearch();
      }
    });
    if (clearButton) {
      clearButton.addEventListener("click", function () {
        input.value = "";
        applySearch();
        input.focus();
      });
    }

    ensureLoaded()
      .then(function () {
        var params = new URLSearchParams(window.location.search || "");
        var initialQuery = String(params.get("q") || "").trim();
        if (initialQuery) {
          input.value = initialQuery;
        }
        applySearch();
      })
      .catch(function () {
        setStatus("Search is temporarily unavailable because the archive index could not be loaded.", "empty");
        renderEmptyState("Search is temporarily unavailable because the archive index could not be loaded.");
      });
  }

  function initHomeCardNavigation() {
    var body = document.body;
    if (!body || !body.classList.contains("page-home")) {
      return;
    }

    var cards = document.querySelectorAll(".topic-card");
    if (!cards.length) {
      return;
    }

    function isInteractiveTarget(node) {
      return Boolean(
        node
        && node.closest
        && node.closest("a, button, input, select, textarea, summary, label, [role='button'], [role='link']")
      );
    }

    Array.prototype.forEach.call(cards, function (card) {
      if (!card) {
        return;
      }
      var primaryLink = card.querySelector(".topic-card-link, h3 a, .topic-card-media");
      if (!primaryLink) {
        return;
      }
      var href = String(primaryLink.getAttribute("href") || "").trim();
      if (!href) {
        return;
      }

      if (!card.hasAttribute("tabindex")) {
        card.setAttribute("tabindex", "0");
      }
      card.setAttribute("role", "link");
      if (!card.getAttribute("aria-label")) {
        var label = String(
          primaryLink.getAttribute("aria-label")
          || primaryLink.getAttribute("title")
          || primaryLink.textContent
          || ""
        ).trim();
        if (label) {
          card.setAttribute("aria-label", label);
        }
      }

      var navigateToCard = function () {
        window.location.assign(href);
      };

      card.addEventListener("click", function (event) {
        if (isInteractiveTarget(event.target)) {
          return;
        }
        navigateToCard();
      });

      card.addEventListener("keydown", function (event) {
        if (isInteractiveTarget(event.target)) {
          return;
        }
        var key = String(event.key || "");
        if (key === "Enter" || key === " ") {
          event.preventDefault();
          navigateToCard();
        }
      });
    });
  }

  function initHierarchyGraphs() {
    var homeGraphContainers = document.querySelectorAll("[data-hierarchy-graph]");
    var articleGraphContainers = document.querySelectorAll("[data-branch-graph]");
    if (!homeGraphContainers.length && !articleGraphContainers.length) {
      return;
    }

    var svgNs = "http://www.w3.org/2000/svg";

    function createSvgNode(tagName) {
      return document.createElementNS(svgNs, tagName);
    }

    function clearSvg(svg) {
      while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
      }
    }

    function normalizeLabelText(text) {
      return String(text || "")
        .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .replace(/\s+/g, " ")
        .trim();
    }

    function truncateLabel(text, maxLength) {
      var value = normalizeLabelText(text);
      if (!value) {
        return "";
      }
      if (value.length <= maxLength) {
        return value;
      }
      return value.slice(0, Math.max(1, maxLength - 3)).trim() + "...";
    }

    function splitLabelLines(text, maxCharsPerLine, maxLines) {
      var value = normalizeLabelText(text);
      if (!value) {
        return [""];
      }
      var words = value.split(" ");
      if (words.length === 1) {
        return [truncateLabel(value, maxCharsPerLine)];
      }
      var lines = [];
      var current = "";
      for (var index = 0; index < words.length; index += 1) {
        var word = words[index];
        var proposed = current ? (current + " " + word) : word;
        if (proposed.length <= maxCharsPerLine || !current) {
          current = proposed;
        } else {
          lines.push(current);
          current = word;
        }
        if (lines.length === maxLines - 1) {
          if (index + 1 < words.length) {
            current = current + " " + words.slice(index + 1).join(" ");
          }
          break;
        }
      }
      if (current) {
        lines.push(current);
      }
      lines = lines.slice(0, Math.max(1, maxLines));
      if (lines.length === 2) {
        var stopwordPattern = /^(?:a|an|and|as|at|by|for|from|in|of|on|or|the|to|vs?)$/i;
        var firstWords = lines[0].split(" ").filter(Boolean);
        var secondWords = lines[1].split(" ").filter(Boolean);
        while (firstWords.length > 1) {
          var secondLineText = secondWords.join(" ");
          var weakSecondLine = secondWords.length <= 1 || secondLineText.length < 10;
          var weakFirstEnding = stopwordPattern.test(firstWords[firstWords.length - 1] || "");
          if (!weakSecondLine && !weakFirstEnding) {
            break;
          }
          var candidateSecondWords = [firstWords[firstWords.length - 1]].concat(secondWords);
          var candidateFirstWords = firstWords.slice(0, -1);
          var candidateFirst = candidateFirstWords.join(" ");
          var candidateSecond = candidateSecondWords.join(" ");
          if (!candidateFirst || candidateSecond.length > maxCharsPerLine) {
            break;
          }
          firstWords = candidateFirstWords;
          secondWords = candidateSecondWords;
        }
        lines = [firstWords.join(" "), secondWords.join(" ")].filter(Boolean);
      }
      return lines;
    }

    function getNodeLabelBudget(node) {
      var kind = String((node && node.kind) || "").trim().toLowerCase();
      if (kind === "root" || kind === "current") {
        return 26;
      }
      if (kind === "branch" || kind === "parent" || kind === "sibling") {
        return 22;
      }
      return 18;
    }

    function readNodeCount(node) {
      var explicit = parseInt(String((node && node.count) || 0), 10);
      if (Number.isFinite(explicit) && explicit > 0) {
        return explicit;
      }
      var rawLabel = String((node && node.label) || "").trim();
      var match = rawLabel.match(/^\+(\d+)/);
      if (match) {
        return parseInt(match[1], 10);
      }
      return 1;
    }

    function getNodeDimensions(node, isCompact) {
      var kind = String((node && node.kind) || "").trim().toLowerCase();
      if (kind === "current") {
        return { width: isCompact ? 224 : 264, height: 80 };
      }
      if (kind === "root") {
        return { width: isCompact ? 232 : 276, height: 84 };
      }
      if (kind.indexOf("cluster") !== -1) {
        return { width: isCompact ? 162 : 182, height: 70 };
      }
      if (kind === "parent") {
        return { width: isCompact ? 188 : 214, height: 72 };
      }
      if (kind === "branch" || kind === "sibling") {
        return { width: isCompact ? 186 : 210, height: 74 };
      }
      return { width: isCompact ? 164 : 184, height: 68 };
    }

    function buildSpreadPositions(count, minX, maxX, y) {
      var points = [];
      if (count <= 0) {
        return points;
      }
      if (count === 1) {
        points.push({ x: Math.round((minX + maxX) / 2), y: y });
        return points;
      }
      var step = (maxX - minX) / (count - 1);
      for (var i = 0; i < count; i += 1) {
        points.push({ x: Math.round(minX + (step * i)), y: y });
      }
      return points;
    }

    function appendEdge(svg, x1, y1, x2, y2, className, nodeId) {
      var path = createSvgNode("path");
      var controlX = Math.round((x1 + x2) / 2);
      var controlY = Math.round((y1 + y2) / 2);
      path.setAttribute("class", "branch-graph-edge hierarchy-graph-edge " + String(className || ""));
      path.setAttribute("d", "M " + x1 + " " + y1 + " Q " + controlX + " " + controlY + " " + x2 + " " + y2);
      if (nodeId) { path.setAttribute("data-edge-for", nodeId); }
      svg.appendChild(path);
    }

    function appendNode(svg, node, options) {
      var opts = options || {};
      var compact = Boolean(opts.compact);
      var dims = getNodeDimensions(node, compact);
      var width = dims.width;
      var height = dims.height;
      var group = createSvgNode("g");
      var kind = String(node.kind || "child").trim().toLowerCase();
      group.setAttribute(
        "class",
        "hierarchy-graph-node branch-graph-node branch-graph-node-" + kind + " hierarchy-graph-node-" + kind
      );
      group.setAttribute("transform", "translate(" + Math.round(node.x) + " " + Math.round(node.y) + ")");
      group.setAttribute("data-kind", kind);

      var card = createSvgNode("rect");
      card.setAttribute("class", "hierarchy-graph-card");
      card.setAttribute("x", String(-Math.round(width / 2)));
      card.setAttribute("y", String(-Math.round(height / 2)));
      card.setAttribute("width", String(width));
      card.setAttribute("height", String(height));
      card.setAttribute("rx", kind === "root" ? "18" : "16");
      card.setAttribute("ry", kind === "root" ? "18" : "16");
      group.appendChild(card);

      var accent = createSvgNode("rect");
      accent.setAttribute("class", "hierarchy-graph-accent");
      accent.setAttribute("x", String(-Math.round(width / 2)));
      accent.setAttribute("y", String(-Math.round(height / 2)));
      accent.setAttribute("width", "10");
      accent.setAttribute("height", String(height));
      accent.setAttribute("rx", "16");
      accent.setAttribute("ry", "16");
      group.appendChild(accent);

      var imageOffset = 0;
      if (node.image && width >= 184) {
        var thumb = createSvgNode("image");
        thumb.setAttribute("href", node.image);
        thumb.setAttribute("x", String(-Math.round(width / 2) + 16));
        thumb.setAttribute("y", String(-Math.round(height / 2) + 14));
        thumb.setAttribute("width", "34");
        thumb.setAttribute("height", "34");
        thumb.setAttribute("preserveAspectRatio", "xMidYMid slice");
        thumb.setAttribute("class", "hierarchy-graph-thumb");
        group.appendChild(thumb);
        imageOffset = 42;
      }

      var labelBudget = getNodeLabelBudget(node);
      var labelLines = splitLabelLines(String(node.label || node.full_label || ""), labelBudget, 2);
      var text = createSvgNode("text");
      text.setAttribute("class", "hierarchy-graph-label");
      text.setAttribute("x", String(-Math.round(width / 2) + 20 + imageOffset));
      text.setAttribute("y", labelLines.length > 1 ? "-6" : "0");
      text.setAttribute("text-anchor", "start");
      text.setAttribute("xml:space", "preserve");
      for (var lineIndex = 0; lineIndex < labelLines.length; lineIndex += 1) {
        var tspan = createSvgNode("tspan");
        tspan.setAttribute("x", String(-Math.round(width / 2) + 20 + imageOffset));
        tspan.setAttribute("dy", lineIndex === 0 ? "0" : "15");
        tspan.setAttribute("xml:space", "preserve");
        var lineText = truncateLabel(labelLines[lineIndex], labelBudget);
        if (lineIndex < labelLines.length - 1) {
          lineText += " ";
        }
        tspan.textContent = lineText;
        text.appendChild(tspan);
      }
      group.appendChild(text);

      var count = readNodeCount(node);
      if (count > 1 || kind.indexOf("cluster") !== -1) {
        var badgeWidth = Math.max(34, String(count).length * 9 + 20);
        var badgeRect = createSvgNode("rect");
        badgeRect.setAttribute("class", "hierarchy-graph-badge");
        badgeRect.setAttribute("x", String(Math.round(width / 2) - badgeWidth - 12));
        badgeRect.setAttribute("y", String(-Math.round(height / 2) + 12));
        badgeRect.setAttribute("width", String(badgeWidth));
        badgeRect.setAttribute("height", "22");
        badgeRect.setAttribute("rx", "11");
        badgeRect.setAttribute("ry", "11");
        group.appendChild(badgeRect);

        var badgeText = createSvgNode("text");
        badgeText.setAttribute("class", "hierarchy-graph-badge-text");
        badgeText.setAttribute("x", String(Math.round(width / 2) - badgeWidth / 2 - 12));
        badgeText.setAttribute("y", String(-Math.round(height / 2) + 27));
        badgeText.textContent = kind.indexOf("cluster") !== -1 ? ("+" + String(count)) : String(count);
        group.appendChild(badgeText);
      }

      var title = createSvgNode("title");
      title.textContent = String(node.full_label || node.label || "").trim() || "Node";
      group.appendChild(title);

      if (node.url) {
        var anchor = createSvgNode("a");
        anchor.setAttribute("href", node.url);
        anchor.setAttribute("data-node-id", String(node._edgeId || ""));
        anchor.setAttribute("class", "hierarchy-graph-anchor branch-graph-anchor");
        anchor.appendChild(group);
        svg.appendChild(anchor);
      } else {
        svg.appendChild(group);
      }
    }

    function renderArticleGraph(container) {
      var svg = container.querySelector("svg");
      if (!svg) {
        return;
      }

      var currentLabel = String(container.getAttribute("data-current-label") || "").trim();
      if (!currentLabel) {
        container.hidden = true;
        return;
      }

      var parentNode = null;
      var siblingNodes = [];
      var childNodes = [];
      Array.prototype.forEach.call(container.querySelectorAll("[data-graph-item]"), function (item) {
        var kind = String(item.getAttribute("data-kind") || "").trim().toLowerCase();
        var label = String(item.getAttribute("data-label") || "").trim();
        var url = String(item.getAttribute("data-url") || "").trim();
        var count = parseInt(String(item.getAttribute("data-count") || "1"), 10);
        if (!label) {
          return;
        }
        var graphNode = {
          kind: kind,
          label: label,
          full_label: label,
          url: url,
          count: Number.isFinite(count) ? count : 1
        };
        if (kind === "parent" && !parentNode) {
          parentNode = graphNode;
        } else if (kind === "sibling" || kind === "sibling-cluster") {
          siblingNodes.push(graphNode);
        } else if (kind === "child" || kind === "child-cluster") {
          childNodes.push(graphNode);
        }
      });

      if (!parentNode || (siblingNodes.length < 2 && childNodes.length < 2)) {
        container.hidden = true;
        return;
      }

      clearSvg(svg);
      var compact = Boolean(container.clientWidth && container.clientWidth < 700);
      var maxPerRow = compact ? 4 : 6;
      var siblingRows = Math.max(1, Math.ceil(siblingNodes.length / maxPerRow));
      var childRows = Math.max(1, Math.ceil(childNodes.length / maxPerRow));
      var width = compact ? 820 : 1080;
      var baseH = compact ? 340 : 300;
      var perRow = compact ? 100 : 90;
      var height = baseH + Math.max(0, siblingRows - 1) * perRow + Math.max(0, childRows - 1) * perRow;
      var centerX = Math.round(width / 2);
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);

      var currentNode = {
        kind: "current",
        label: currentLabel,
        full_label: currentLabel,
        url: String(container.getAttribute("data-current-url") || "").trim(),
        count: 1,
        x: centerX,
        y: compact ? 164 : 176
      };
      parentNode.x = centerX;
      parentNode.y = compact ? 62 : 58;

      /* Multi-row spread: wraps nodes to rows of maxPerRow */
      function buildMultiRowPositions(nodes, minX, maxX, startY, rowGap) {
        var positions = [];
        var total = nodes.length;
        for (var r = 0; r < Math.ceil(total / maxPerRow); r++) {
          var rStart = r * maxPerRow;
          var rCount = Math.min(maxPerRow, total - rStart);
          var rowPositions = buildSpreadPositions(rCount, minX, maxX, startY + r * rowGap);
          for (var p = 0; p < rowPositions.length; p++) {
            positions.push(rowPositions[p]);
          }
        }
        return positions;
      }
      var edgeMinX = compact ? 110 : 120;
      var edgeMaxX = compact ? width - 110 : width - 120;
      var siblingY = compact ? 266 : 126;
      var childY = (compact ? 346 : 294) + Math.max(0, siblingRows - 1) * perRow;
      var siblingPositions = buildMultiRowPositions(siblingNodes, edgeMinX, edgeMaxX, siblingY, perRow);
      var childPositions = buildMultiRowPositions(childNodes, edgeMinX, edgeMaxX, childY, perRow);
      for (var siblingIndex = 0; siblingIndex < siblingNodes.length; siblingIndex += 1) {
        siblingNodes[siblingIndex].x = siblingPositions[siblingIndex].x;
        siblingNodes[siblingIndex].y = siblingPositions[siblingIndex].y;
        siblingNodes[siblingIndex]._edgeId = "node-" + siblingIndex;
      }
      for (var childIndex = 0; childIndex < childNodes.length; childIndex += 1) {
        childNodes[childIndex].x = childPositions[childIndex].x;
        childNodes[childIndex].y = childPositions[childIndex].y;
        childNodes[childIndex]._edgeId = "node-child-" + childIndex;
      }

      appendEdge(svg, parentNode.x, parentNode.y + 30, currentNode.x, currentNode.y - 38, "branch-graph-edge-parent");
      siblingNodes.forEach(function (node) {
        appendEdge(svg, currentNode.x, currentNode.y - 16, node.x, node.y - 30, "branch-graph-edge-sibling", "node-" + siblingNodes.indexOf(node));
      });
      childNodes.forEach(function (node) {
        appendEdge(svg, currentNode.x, currentNode.y + 28, node.x, node.y - 32, "branch-graph-edge-child", "node-child-" + childNodes.indexOf(node));
      });

      appendNode(svg, parentNode, { compact: compact });
      appendNode(svg, currentNode, { compact: compact });
      siblingNodes.forEach(function (node) {
        appendNode(svg, node, { compact: compact });
      });
      childNodes.forEach(function (node) {
        appendNode(svg, node, { compact: compact });
      });

      /* Edge hover: highlight connected edges on node hover */
      Array.prototype.forEach.call(svg.querySelectorAll(".branch-graph-anchor"), function (anchor) {
        var nodeId = anchor.getAttribute("data-node-id") || "";
        if (!nodeId) { return; }
        anchor.addEventListener("mouseenter", function () {
          var allEdges = svg.querySelectorAll(".branch-graph-edge");
          for (var ei = 0; ei < allEdges.length; ei++) {
            var edgeFor = allEdges[ei].getAttribute("data-edge-for") || "";
            if (edgeFor === nodeId) {
              allEdges[ei].classList.add("edge-highlighted");
              allEdges[ei].classList.remove("edge-dimmed");
            } else if (edgeFor) {
              allEdges[ei].classList.add("edge-dimmed");
              allEdges[ei].classList.remove("edge-highlighted");
            }
          }
        });
        anchor.addEventListener("mouseleave", function () {
          var allEdges = svg.querySelectorAll(".branch-graph-edge");
          for (var ei = 0; ei < allEdges.length; ei++) {
            allEdges[ei].classList.remove("edge-highlighted");
            allEdges[ei].classList.remove("edge-dimmed");
          }
        });
      });
    }

    function createHtmlNode(tagName, className, text) {
      var node = document.createElement(tagName);
      if (className) {
        node.className = className;
      }
      if (text !== undefined && text !== null) {
        node.textContent = String(text);
      }
      return node;
    }

    function applyHomeClusterNodeMeta(element, node) {
      if (!element || !node) {
        return;
      }
      var densityTier = String(node.density_tier || "").trim().toLowerCase();
      var titleBucket = String(node.title_length_bucket || "").trim().toLowerCase();
      if (densityTier) {
        element.setAttribute("data-density-tier", densityTier);
        element.classList.add("is-tier-" + densityTier);
      }
      if (titleBucket) {
        element.setAttribute("data-title-bucket", titleBucket);
        element.classList.add("is-title-" + titleBucket);
      }
      if (node.semantic_level) {
        element.setAttribute("data-semantic-level", String(node.semantic_level));
      }
      if (node.render_hint) {
        element.setAttribute("data-render-hint", String(node.render_hint));
      }
      if (node.preferred_cluster_strategy) {
        element.setAttribute("data-preferred-cluster-strategy", String(node.preferred_cluster_strategy));
      }
      if (node.preferred_subtree_layout) {
        element.setAttribute("data-preferred-subtree-layout", String(node.preferred_subtree_layout));
      }
      if (node.subtree_shape && typeof node.subtree_shape === "object") {
        var subtreeShape = node.subtree_shape;
        var subtreeTotal = parseInt(String(subtreeShape.total_nodes || 0), 10);
        var subtreeDepth = parseInt(String(subtreeShape.max_depth || 0), 10);
        var subtreeBreadth = parseInt(String(subtreeShape.max_breadth || 0), 10);
        var subtreeChildCount = parseInt(String(subtreeShape.child_count || 0), 10);
        if (Number.isFinite(subtreeTotal)) {
          element.setAttribute("data-subtree-total", String(subtreeTotal));
        }
        if (Number.isFinite(subtreeDepth)) {
          element.setAttribute("data-subtree-depth", String(subtreeDepth));
        }
        if (Number.isFinite(subtreeBreadth)) {
          element.setAttribute("data-subtree-breadth", String(subtreeBreadth));
        }
        if (Number.isFinite(subtreeChildCount)) {
          element.setAttribute("data-subtree-child-count", String(subtreeChildCount));
        }
      }
    }

    function getHomeClusterTierRank(tier) {
      var normalized = String(tier || "balanced").trim().toLowerCase();
      if (normalized === "sparse") {
        return 0;
      }
      if (normalized === "balanced") {
        return 1;
      }
      if (normalized === "dense") {
        return 2;
      }
      return 3;
    }

    function chunkHomeClusterItems(items, pageSize) {
      var source = Array.isArray(items) ? items.slice() : [];
      var size = Math.max(1, parseInt(String(pageSize || 1), 10) || 1);
      var pages = [];
      for (var index = 0; index < source.length; index += size) {
        pages.push(source.slice(index, index + size));
      }
      return pages;
    }

    function getHomeClusterPageSize(kind, width, tier) {
      var rank = getHomeClusterTierRank(tier);
      if (kind === "l1-overview") {
        if (rank <= 1) {
          return width >= 1220 ? 12 : (width >= 860 ? 8 : 4);
        }
        if (rank === 2) {
          return width >= 1220 ? 8 : (width >= 860 ? 6 : 3);
        }
        return 0;
      }
      if (kind === "l1-focus") {
        if (width >= 1220) {
          return 8;
        }
        if (width >= 860) {
          return 6;
        }
        return 4;
      }
      if (kind === "l2-overview") {
        if (rank <= 1) {
          if (width >= 1220) {
            return 3;
          }
          if (width >= 860) {
            return 2;
          }
          return 1;
        }
        if (rank === 2) {
          return width >= 860 ? 1 : 0;
        }
        return 0;
      }
      if (kind === "l2-focus") {
        if (width >= 1220) {
          return 12;
        }
        if (width >= 860) {
          return 8;
        }
        return 5;
      }
      if (kind === "l3-focus") {
        if (width >= 1220) {
          return 16;
        }
        if (width >= 860) {
          return 12;
        }
        return 8;
      }
      if (kind === "group-overview") {
        return width >= 860 ? 2 : 1;
      }
      return 1;
    }

    function renderHomeClusterMap(container, payload, nodes) {

      var board = container.querySelector("[data-home-cluster-board]");

      var focusTray = container.querySelector("[data-home-cluster-focus]");

      if (!board) {

        container.hidden = true;

        return;

      }



      var width = Math.max(

        container.clientWidth || 0,

        document.documentElement ? (document.documentElement.clientWidth || 0) : 0,

        window.innerWidth || 0

      );

      var nodeById = {};

      var childrenByParent = {};

      var branchByBase = {};



      container.hidden = false;

      container.setAttribute("data-home-cluster-version", String(payload.home_cluster_version || 3));

      container.classList.add("home-cluster-tree-mode");



      nodes.forEach(function (node) {

        nodeById[node.id] = node;

        var parentId = String(node.parent_id || "").trim();

        if (parentId) {

          if (!childrenByParent[parentId]) {

            childrenByParent[parentId] = [];

          }

          childrenByParent[parentId].push(node);

        }

        if (String(node.semantic_level || "") === "l1" && node.basename) {

          branchByBase[String(node.basename)] = node.id;

        }

      });

      Object.keys(childrenByParent).forEach(function (parentId) {

        childrenByParent[parentId].sort(function (a, b) {

          var aSlot = parseInt(String(a.slot_index || 0), 10);

          var bSlot = parseInt(String(b.slot_index || 0), 10);

          if (Number.isFinite(aSlot) && Number.isFinite(bSlot) && aSlot !== bSlot) {

            return aSlot - bSlot;

          }

          return String(a.label || "").localeCompare(String(b.label || ""));

        });

      });

      var currentPath = normalizePath(window.location.pathname);
      var pathParts = currentPath.split("/").filter(Boolean);
      var siteScope = pathParts.length ? pathParts[0] : "root";
      var branchStorageKey = "phoenix-home-cluster-branch-v1-" + siteScope + "-" + currentPath.replace(/[^\w/-]+/g, "_");



      var rootNode = nodes.filter(function (node) {

        return parseInt(String(node.depth || 0), 10) === 0;

      })[0] || null;

      var allBranches = rootNode ? (childrenByParent[rootNode.id] || []) : [];

      if (!rootNode || !allBranches.length) {

        container.hidden = true;

        return;

      }



      /* --- Shape Analysis --- */

      var shape = payload.shape || {};

      var totalNodes = shape.total_nodes || nodes.length;

      var maxDepth = shape.max_depth || 0;

      var maxBreadth = shape.max_breadth || 0;

      var breadthByDepth = shape.breadth_by_depth || {};

      var rootBreadth = parseInt(String(breadthByDepth[0] || breadthByDepth["0"] || 0), 10);

      var l1Breadth = parseInt(String(breadthByDepth[1] || breadthByDepth["1"] || allBranches.length), 10);

      var l2Breadth = parseInt(String(breadthByDepth[2] || breadthByDepth["2"] || 0), 10);

      var l1Count = allBranches.length;

      var singleRootTree = !Number.isFinite(rootBreadth) || rootBreadth <= 1;

      var shallowFanoutEligible = singleRootTree && maxDepth <= 1 && l1Count >= 2 && l1Count <= 12;

      var hierarchyFirstTree = singleRootTree && maxDepth >= 2 && l1Count <= 8 && maxBreadth <= 28 && totalNodes <= 180;

      function getPreferredClusterStrategyHint(isMobile) {
        var mobileHint = String(payload.preferred_cluster_strategy_mobile || (rootNode && rootNode.preferred_cluster_strategy_mobile) || "").trim().toLowerCase();
        var desktopHint = String(payload.preferred_cluster_strategy || (rootNode && rootNode.preferred_cluster_strategy) || "").trim().toLowerCase();
        if (isMobile && (mobileHint === "fanout" || mobileHint === "cascade" || mobileHint === "tree" || mobileHint === "grid")) {
          return mobileHint;
        }
        if (desktopHint === "fanout" || desktopHint === "cascade" || desktopHint === "tree" || desktopHint === "grid") {
          return desktopHint;
        }
        return "";
      }



      /* --- Layout Strategy Selection --- */

      function autoSelectStrategy() {
        var vw = width || window.innerWidth || document.documentElement.clientWidth || 1200;
        var isMobile = vw <= 720;
        var hintedStrategy = getPreferredClusterStrategyHint(isMobile);
        var cascadeLimit = isMobile ? 20 : 40;
        var cascadeBreadth = isMobile ? 5 : 8;
        var gridNodeLimit = isMobile ? 100 : 200;
        var gridL1Limit = isMobile ? 10 : 15;
        if (hintedStrategy) {
          return hintedStrategy;
        }
        if (shallowFanoutEligible) {
          return "fanout";
        }
        if (hierarchyFirstTree) {
          return isMobile ? "cascade" : "tree";
        }
        if (totalNodes <= cascadeLimit && maxBreadth <= cascadeBreadth) {
          return "cascade";
        }
        if (l1Count >= gridL1Limit || totalNodes >= gridNodeLimit) {
          return "grid";
        }
        return "tree";
      }

      function selectLayoutStrategy() {

        var override = String(container.getAttribute("data-ct-strategy-override") || "").trim().toLowerCase();

        if (override === "fanout" || override === "cascade" || override === "tree" || override === "grid") {

          return override;

        }

        return autoSelectStrategy();

      }

      var strategy = selectLayoutStrategy();

      var autoStrategy = autoSelectStrategy();

      function getStrategyLabel(token) {
        return {
          fanout: "Branch map",
          cascade: "Stacked view",
          tree: "Tree view",
          grid: "Tile grid"
        }[token] || "Cluster diagram";
      }

      function syncClusterLabels(activeStrategy) {
        var label = getStrategyLabel(activeStrategy);
        var band = container.closest("[data-home-hierarchy-band]");
        var titleNode = band ? band.querySelector("[data-home-cluster-title]") : null;
        if (titleNode) {
          titleNode.textContent = label;
        }
        var switcher = document.querySelector("[data-home-mode-switcher]");
        if (switcher && String(switcher.getAttribute("data-home-mode-effective") || "").trim().toLowerCase() === "cluster") {
          var summaryCurrentNodes = switcher.querySelectorAll("[data-home-mode-summary-current], [data-home-mode-summary-current-visual]");
          Array.prototype.forEach.call(summaryCurrentNodes, function (node) {
            node.textContent = label;
          });
        }
      }



      /* --- State for expand/collapse --- */
      var state = container.__homeClusterState || {
        expandedBranches: {},
        expandedL2: {},
        selectedBranchId: "",
        hoveredBranchId: "",
        manualSelection: false
      };
      if (!state || typeof state !== "object") {
        state = {
          expandedBranches: {},
          expandedL2: {},
          selectedBranchId: "",
          hoveredBranchId: "",
          manualSelection: false
        };
      }
      if (!state.expandedBranches || typeof state.expandedBranches !== "object") {
        state.expandedBranches = {};
      }
      if (!state.expandedL2 || typeof state.expandedL2 !== "object") {
        state.expandedL2 = {};
      }
      state.selectedBranchId = String(state.selectedBranchId || "").trim();
      state.hoveredBranchId = String(state.hoveredBranchId || "").trim();
      state.manualSelection = !!state.manualSelection;
      if (!container.__homeClusterState && !state.selectedBranchId) {
        var persistedBranchBase = String(readLocalStorage(branchStorageKey) || "").trim();
        if (persistedBranchBase) {
          var restoredBranch = allBranches.filter(function (branchNode) {
            return String(branchNode && branchNode.basename || "").trim() === persistedBranchBase;
          })[0] || null;
          if (restoredBranch && restoredBranch.id) {
            state.selectedBranchId = String(restoredBranch.id || "").trim();
            state.manualSelection = true;
          }
        }
      }
      if (state.selectedBranchId && !nodeById[state.selectedBranchId]) {
        state.selectedBranchId = "";
        state.manualSelection = false;
      }
      if (state.hoveredBranchId && !nodeById[state.hoveredBranchId]) {
        state.hoveredBranchId = "";
      }
      /* Auto-expand all branches for small sites on first render */
      if (!container.__homeClusterState && totalNodes <= 30) {
        allBranches.forEach(function (b) { state.expandedBranches[b.id] = true; });
      }
      if (state.selectedBranchId && !Object.prototype.hasOwnProperty.call(state.expandedBranches, state.selectedBranchId)) {
        state.expandedBranches[state.selectedBranchId] = true;
      }
      container.__homeClusterState = state;
      var shouldPreferFocusedBranch = !!state.manualSelection || totalNodes > 24 || l1Count > 5;

      function getTopLevelBranchId(nodeOrId) {
        var current = typeof nodeOrId === "string" ? nodeById[String(nodeOrId || "").trim()] : nodeOrId;
        var guard = 0;
        while (current && guard < 16) {
          var currentDepth = parseInt(String(current.depth || 0), 10) || 0;
          if (currentDepth === 1) {
            return String(current.id || "").trim();
          }
          var parentId = String(current.parent_id || "").trim();
          if (!parentId) {
            break;
          }
          current = nodeById[parentId];
          guard += 1;
        }
        return "";
      }

      function isNodeInSelectedBranch(nodeOrId) {
        var selectedBranchId = String(state.selectedBranchId || "").trim();
        if (!selectedBranchId) {
          return false;
        }
        return getTopLevelBranchId(nodeOrId) === selectedBranchId;
      }

      function getEffectiveFocusBranchId() {
        var hoveredBranchId = String(state.hoveredBranchId || "").trim();
        if (hoveredBranchId && nodeById[hoveredBranchId]) {
          return hoveredBranchId;
        }
        var selectedBranchId = String(state.selectedBranchId || "").trim();
        if (selectedBranchId && nodeById[selectedBranchId]) {
          return selectedBranchId;
        }
        return "";
      }

      function getSelectedBranchNode() {
        var selectedBranchId = String(state.selectedBranchId || "").trim();
        return selectedBranchId && nodeById[selectedBranchId] ? nodeById[selectedBranchId] : null;
      }

      function isHoverPreviewActive() {
        var hoveredBranchId = String(state.hoveredBranchId || "").trim();
        var selectedBranchId = String(state.selectedBranchId || "").trim();
        return !!hoveredBranchId && !!nodeById[hoveredBranchId] && hoveredBranchId !== selectedBranchId;
      }

      function getFocusMode() {
        if (isHoverPreviewActive()) {
          return "preview";
        }
        if (state.manualSelection && getSelectedBranchNode()) {
          return "pinned";
        }
        return "guided";
      }

      function syncBranchAttention() {
        var effectiveFocusBranchId = getEffectiveFocusBranchId();
        var hoverPreviewActive = isHoverPreviewActive();
        var branchNodes = board.querySelectorAll("[data-branch-id]");
        Array.prototype.forEach.call(branchNodes, function (branchEl) {
          var branchId = String(branchEl.getAttribute("data-branch-id") || "").trim();
          var isSelected = !!branchId && branchId === String(state.selectedBranchId || "").trim();
          var isFocused = !!branchId && branchId === effectiveFocusBranchId;
          var shouldDim = !!effectiveFocusBranchId && hoverPreviewActive && branchId !== effectiveFocusBranchId;
          branchEl.classList.toggle("ct-selected", isSelected);
          branchEl.classList.toggle("ct-highlighted", isFocused);
          branchEl.classList.toggle("ct-dimmed", shouldDim);
        });
      }

      function persistSelectedBranchBase(baseName) {
        writeLocalStorage(branchStorageKey, String(baseName || "").trim());
      }

      function cancelPendingHoverClear() {
        if (container.__homeClusterHoverClearTimer) {
          window.clearTimeout(container.__homeClusterHoverClearTimer);
          container.__homeClusterHoverClearTimer = 0;
        }
      }

      function setSelectedBranch(branchId, options) {
        var nextBranchId = String(branchId || "").trim();
        var opts = options || {};
        if (!nextBranchId || !nodeById[nextBranchId]) {
          return false;
        }
        var nextBranchNode = nodeById[nextBranchId] || {};
        state.selectedBranchId = nextBranchId;
        state.manualSelection = Object.prototype.hasOwnProperty.call(opts, "manual")
          ? !!opts.manual
          : state.manualSelection;
        if (opts.clearHover !== false) {
          state.hoveredBranchId = "";
        }
        if (opts.collapseSiblings !== false) {
          Object.keys(state.expandedBranches).forEach(function (expandedId) {
            if (getTopLevelBranchId(expandedId) !== nextBranchId) {
              delete state.expandedBranches[expandedId];
            }
          });
        }
        state.expandedBranches[nextBranchId] = true;
        if (opts.persist === true || (opts.persist !== false && opts.manual === true)) {
          persistSelectedBranchBase(nextBranchNode.basename || "");
        }
        container.__homeClusterState = state;
        return true;
      }

      function clearSelectedBranch() {
        state.manualSelection = false;
        state.hoveredBranchId = "";
        state.selectedBranchId = "";
        state.expandedBranches = {};
        if (totalNodes <= 30) {
          allBranches.forEach(function (branchNode) {
            if (branchNode && branchNode.id) {
              state.expandedBranches[branchNode.id] = true;
            }
          });
        }
        persistSelectedBranchBase("");
        container.__homeClusterState = state;
        renderHomeClusterMap(container, payload, nodes);
      }

      function setHoveredBranch(branchId) {
        var nextBranchId = String(branchId || "").trim();
        if (!nextBranchId || !nodeById[nextBranchId]) {
          return;
        }
        cancelPendingHoverClear();
        if (state.hoveredBranchId === nextBranchId) {
          return;
        }
        state.hoveredBranchId = nextBranchId;
        container.__homeClusterPendingPreviewBranchId = nextBranchId;
        container.__homeClusterState = state;
        syncBranchAttention();
        renderFocusTrayFromState();
      }

      function clearHoveredBranch(branchId, options) {
        var targetBranchId = String(branchId || "").trim();
        var opts = options || {};
        if (targetBranchId && state.hoveredBranchId !== targetBranchId) {
          return;
        }
        if (!state.hoveredBranchId) {
          return;
        }
        var clearAction = function () {
          container.__homeClusterHoverClearTimer = 0;
          state.hoveredBranchId = "";
          container.__homeClusterPendingPreviewBranchId = "";
          container.__homeClusterState = state;
          syncBranchAttention();
          renderFocusTrayFromState();
        };
        cancelPendingHoverClear();
        if (opts.immediate) {
          clearAction();
          return;
        }
        container.__homeClusterPendingPreviewBranchId = state.hoveredBranchId;
        container.__homeClusterHoverClearTimer = window.setTimeout(clearAction, 160);
      }



      /* --- Helper functions --- */

      function getDisplayLabel(node) {

        return String((node && (node.display_label || node.label || node.full_label)) || "Untitled");

      }

      function getFullLabel(node) {

        return String((node && (node.full_label || node.display_label || node.label)) || "Untitled");

      }

      function getNodeImage(node) {

        return String((node && node.image) || "").trim();

      }

      function getTierRank(tier) {

        var t = String(tier || "balanced").trim().toLowerCase();

        if (t === "sparse") return 0;

        if (t === "balanced") return 1;

        if (t === "dense") return 2;

        return 3;

      }



      /* --- Progressive node sizing --- */

      function getNodeSizeClass(depth, strat) {

        if (depth <= 0) return "ct-node-root";

        if (strat === "fanout") {

          if (depth === 1) {

            if (width >= 1280 && l1Count <= 8) return "ct-node-xl";

            if (width >= 900) return "ct-node-lg";

            return "ct-node-md";

          }

          if (depth === 2) return width >= 1024 ? "ct-node-md" : "ct-node-sm";

          return "ct-node-sm";

        }

        if (strat === "cascade") {

          if (depth === 1) return "ct-node-lg";

          if (depth === 2) return "ct-node-md";

          if (depth === 3) return "ct-node-sm";

          return "ct-node-xs";

        }

        if (strat === "grid") {

          if (depth === 1) return "ct-node-sm";

          return "ct-node-xs";

        }

        /* tree strategy: scale by totalNodes */

        if (totalNodes < 60) {

          if (depth === 1) return "ct-node-lg";

          if (depth === 2) return "ct-node-md";

          if (depth === 3) return "ct-node-sm";

          return "ct-node-xs";

        }

        if (totalNodes < 120) {

          if (depth === 1 && width >= 1320 && l1Count <= 8) return "ct-node-xl";
          if (depth === 1) return "ct-node-md";

          if (depth === 2) return "ct-node-sm";

          return "ct-node-xs";

        }

        if (depth === 1) {
          if (width >= 1460 && l1Count <= 8) return "ct-node-lg";
          if (width >= 1180) return "ct-node-md";
          return "ct-node-sm";
        }

        if (depth === 2) {
          if (width >= 1460) return "ct-node-md";
          return "ct-node-sm";
        }

        if (depth === 3) {
          if (width >= 1520 && totalNodes < 320) return "ct-node-sm";
          return "ct-node-xs";
        }

        return "ct-node-xs";

      }



      /* --- Inline child limits by density and strategy --- */

      function getInlineChildLimit(tier, depth, strat, parentNode) {

        var rank = getTierRank(tier);
        var inSelectedBranch = !shouldPreferFocusedBranch || isNodeInSelectedBranch(parentNode);

        if (shouldPreferFocusedBranch && !inSelectedBranch) {
          return 0;
        }

        if (strat === "grid") {

          return 0; /* grid mode shows children only on expand */

        }

        if (strat === "cascade") {

          if (rank <= 0) return 999;

          if (rank === 1) return 8;

          if (rank === 2) return 4;

          return 2;

        }

        /* tree */

        if (rank <= 0) return 999;

        if (rank === 1) return width >= 960 ? (inSelectedBranch ? 8 : 6) : (inSelectedBranch ? 6 : 4);

        if (rank === 2) return width >= 960 ? (inSelectedBranch ? 5 : 3) : (inSelectedBranch ? 3 : 2);

        return inSelectedBranch ? 2 : 0;

      }



      function getInlineL3Limit(tier, strat, parentNode) {

        if (strat === "grid") return 0;

        var rank = getTierRank(tier);
        var inSelectedBranch = !shouldPreferFocusedBranch || isNodeInSelectedBranch(parentNode);

        if (shouldPreferFocusedBranch && !inSelectedBranch) {
          return 0;
        }

        if (strat === "cascade") {

          if (rank <= 0) return inSelectedBranch ? 8 : 6;

          if (rank === 1) return inSelectedBranch ? 4 : 3;

          return 0;

        }

        if (rank <= 0) return inSelectedBranch ? 6 : 4;

        if (rank === 1) return inSelectedBranch ? 3 : 2;

        return 0;

      }



      /* --- DOM builders --- */

      function makeNode(tag, cls, text) {

        var el = document.createElement(tag || "div");

        if (cls) el.className = cls;

        if (text) el.textContent = text;

        return el;

      }

      function pluralizeWord(value, singular, plural) {
        var numeric = Math.max(0, parseInt(String(value || 0), 10) || 0);
        return String(numeric) + " " + (numeric === 1 ? singular : (plural || singular + "s"));
      }

      function getNodeLevelLabel(node) {
        var explicit = String(node.level_label || "").trim();
        if (explicit) return explicit;
        var semantic = String(node.semantic_level || "").trim().toLowerCase();
        if (semantic === "root") return "Overview";
        if (semantic === "l1") return "Topic";
        if (semantic === "l2") return "Section";
        if (semantic === "l3") return "Page";
        return "Page";
      }

      function getNodeMetaLine(node) {
        var count = Math.max(0, parseInt(String(node.count || 0), 10) || 0);
        var childTotal = Math.max(0, parseInt(String(node.child_total || 0), 10) || 0);
        var semantic = String(node.semantic_level || "").trim().toLowerCase();

        if (semantic === "root") {
          return childTotal > 0
            ? (pluralizeWord(count, "page") + " across " + pluralizeWord(childTotal, "section"))
            : pluralizeWord(count, "page");
        }
        if (semantic === "l1") {
          return childTotal > 0
            ? (pluralizeWord(count, "page") + " in " + pluralizeWord(childTotal, "subtopic"))
            : pluralizeWord(count, "page");
        }
        if (semantic === "l2") {
          return childTotal > 0
            ? (pluralizeWord(count, "page") + " with " + pluralizeWord(childTotal, "page"))
            : pluralizeWord(count, "page");
        }
        return count > 1 ? pluralizeWord(count, "page") : "";
      }

      function getNodeSummary(node) {
        var explicit = String(node.summary || node.description || "").trim();
        if (explicit) return explicit;
        var semantic = String(node.semantic_level || "").trim().toLowerCase();
        var childTotal = Math.max(0, parseInt(String(node.child_total || 0), 10) || 0);
        if (semantic === "root" && childTotal > 0) {
          return "Start here, then open " + pluralizeWord(childTotal, "main section") + " and related pages.";
        }
        if (semantic === "l1" && childTotal > 0) {
          return "Open " + pluralizeWord(childTotal, "subtopic") + " from this section.";
        }
        if (semantic === "l2" && childTotal > 0) {
          return "This section opens into " + pluralizeWord(childTotal, "page") + ".";
        }
        return "";
      }

      function getRepresentativeSampleScore(node) {
        if (!node) {
          return -1;
        }
        var score = 0;
        var descendantTotal = Math.max(0, parseInt(String(node.descendant_total || 0), 10) || 0);
        var childTotal = Math.max(0, parseInt(String(node.child_total || 0), 10) || 0);
        var densityTier = String(node.density_tier || "balanced").trim().toLowerCase();
        var titleBucket = String(node.title_length_bucket || "").trim().toLowerCase();
        var semanticLevel = String(node.semantic_level || "").trim().toLowerCase();

        if (getNodeImage(node)) {
          score += 20;
        }
        score += Math.min(descendantTotal, 24) * 2;
        score += Math.min(childTotal, 8) * 5;
        score += getNodeSummary(node) ? 8 : 0;
        score += getTierRank(densityTier) * 4;

        if (semanticLevel === "l2") {
          score += 5;
        } else if (semanticLevel === "l3") {
          score += 2;
        }

        if (titleBucket === "medium") {
          score += 3;
        } else if (titleBucket === "long") {
          score += 2;
        } else if (titleBucket === "very-long") {
          score -= 2;
        }

        return score;
      }

      function getRankedRepresentativeNodes(items, limit) {
        var list = Array.prototype.slice.call(items || []);
        list.sort(function (a, b) {
          var scoreDelta = getRepresentativeSampleScore(b) - getRepresentativeSampleScore(a);
          if (scoreDelta !== 0) {
            return scoreDelta;
          }
          var descendantDelta = (parseInt(String(b && b.descendant_total || 0), 10) || 0)
            - (parseInt(String(a && a.descendant_total || 0), 10) || 0);
          if (descendantDelta !== 0) {
            return descendantDelta;
          }
          return String(getFullLabel(a || "")).localeCompare(String(getFullLabel(b || "")));
        });
        var maxItems = Math.max(0, parseInt(String(limit || list.length), 10) || list.length);
        return list.slice(0, maxItems);
      }

      function getOverflowNoun(parentNode, count) {
        var overflowCount = Math.max(0, parseInt(String(count || 0), 10) || 0);
        var semanticLevel = String(parentNode && parentNode.semantic_level || "").trim().toLowerCase();
        if (semanticLevel === "root") {
          return overflowCount === 1 ? "section" : "sections";
        }
        if (semanticLevel === "l1") {
          return overflowCount === 1 ? "subtopic" : "subtopics";
        }
        if (semanticLevel === "l2") {
          return overflowCount === 1 ? "page" : "pages";
        }
        return overflowCount === 1 ? "page" : "pages";
      }

      function applyExpandToggleState(toggle, expanded, node) {
        if (!toggle) {
          return;
        }
        var isExpanded = !!expanded;
        var labelBase = getDisplayLabel(node) || "this branch";
        var actionLabel = isExpanded ? "Hide subtopics" : "Expand subtopics";
        var icon = toggle.querySelector(".ct-expand-toggle-icon");
        var text = toggle.querySelector(".ct-expand-toggle-text");
        if (icon) {
          icon.textContent = isExpanded ? "\u2212" : "+";
        }
        if (text) {
          text.textContent = isExpanded ? "Hide" : "Expand";
        }
        toggle.title = actionLabel;
        toggle.setAttribute("aria-label", actionLabel + " for " + labelBase);
        toggle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
        toggle.setAttribute("data-toggle-state", isExpanded ? "expanded" : "collapsed");
      }

      function createExpandToggle(node, expanded) {
        var toggle = makeNode("button", "ct-expand-toggle");
        toggle.type = "button";
        toggle.appendChild(makeNode("span", "ct-expand-toggle-icon", expanded ? "\u2212" : "+"));
        toggle.appendChild(makeNode("span", "ct-expand-toggle-text", expanded ? "Hide" : "Expand"));
        applyExpandToggleState(toggle, expanded, node);
        return toggle;
      }

      function getOverflowLabel(parentNode, count, options) {
        var overflowCount = Math.max(0, parseInt(String(count || 0), 10) || 0);
        var opts = options || {};
        var noun = getOverflowNoun(parentNode, overflowCount);
        if (opts.compact) {
          return "+" + String(overflowCount) + " " + noun;
        }
        return String(overflowCount) + " more " + noun;
      }

      function buildClusterMedia(node) {
        var imageSrc = getNodeImage(node);
        var media = makeNode("a", "home-cluster-card-media");
        media.href = String(node.url || "#");
        media.title = getFullLabel(node);
        if (imageSrc) {
          var image = document.createElement("img");
          image.src = imageSrc;
          image.alt = "";
          image.loading = "lazy";
          image.decoding = "async";
          media.appendChild(image);
          return media;
        }
        media.classList.add("home-cluster-card-placeholder");
        media.appendChild(
          makeNode(
            "span",
            "home-cluster-card-initial",
            String(getFullLabel(node) || "U").slice(0, 1).toUpperCase()
          )
        );
        return media;
      }

      function buildFocusChildCard(node) {
        var card = makeNode("article", "home-cluster-card home-cluster-card-l2");
        var tier = String(node.density_tier || "").trim().toLowerCase();
        if (tier) {
          card.classList.add("is-tier-" + tier);
        }

        card.appendChild(buildClusterMedia(node));

        var metaRow = makeNode("div", "home-cluster-card-meta-row");
        var badgeText = parseInt(String(node.count || 0), 10) > 1
          ? pluralizeWord(node.count || 0, "page")
          : getNodeLevelLabel(node);
        metaRow.appendChild(makeNode("span", "home-cluster-count-badge", badgeText));
        metaRow.appendChild(makeNode("span", "home-cluster-card-meta", getNodeMetaLine(node) || getNodeLevelLabel(node)));
        card.appendChild(metaRow);

        var title = makeNode("h3", "home-cluster-card-title");
        var titleLink = makeNode("a", "home-cluster-title-link", getDisplayLabel(node));
        titleLink.href = String(node.url || "#");
        titleLink.title = getFullLabel(node);
        title.appendChild(titleLink);
        card.appendChild(title);

        var summary = getNodeSummary(node);
        if (summary) {
          card.appendChild(makeNode("p", "home-cluster-node-summary", summary));
        }

        var deepChildren = childrenByParent[node.id] || [];
        if (deepChildren.length > 0) {
          var deepList = makeNode("div", "home-cluster-l3-list");
          var deepLimit = width >= 1240 ? 4 : (width >= 900 ? 3 : 2);
          getRankedRepresentativeNodes(deepChildren, deepLimit).forEach(function (deepNode) {
            var deepLink = makeNode("a", "home-cluster-card-l3", getDisplayLabel(deepNode));
            deepLink.href = String(deepNode.url || "#");
            deepLink.title = getFullLabel(deepNode);
            deepList.appendChild(deepLink);
          });
          if (deepChildren.length > deepLimit) {
            deepList.appendChild(
              makeNode(
                "span",
                "home-cluster-card-l3",
                getOverflowLabel(node, deepChildren.length - deepLimit, { compact: true })
              )
            );
          }
          card.appendChild(deepList);
        }

        return card;
      }

      function renderFocusTrayFromState() {
        if (!focusTray) {
          return;
        }

        var focusBranchId = getEffectiveFocusBranchId();
        var focusBranch = focusBranchId ? nodeById[focusBranchId] : null;
        var selectedBranch = getSelectedBranchNode();
        var isPreview = isHoverPreviewActive();
        var isPinned = !!(state.manualSelection && selectedBranch && selectedBranch.id === focusBranchId && !isPreview);
        var focusMode = getFocusMode();
        if (!focusBranch || (!isPreview && !state.manualSelection)) {
          focusTray.innerHTML = "";
          focusTray.hidden = true;
          focusTray.removeAttribute("data-home-cluster-focus-mode");
          return;
        }

        focusTray.innerHTML = "";
        focusTray.hidden = false;
        focusTray.setAttribute("data-home-cluster-focus-mode", focusMode);

        var head = makeNode("div", "home-cluster-focus-head");
        var text = makeNode("div", "home-cluster-focus-text");
        var breadcrumbs = makeNode("nav", "home-cluster-focus-breadcrumbs");
        breadcrumbs.setAttribute("aria-label", getUiString("cluster-focus-path", "Cluster focus path"));
        var overviewCrumb = makeNode("button", "home-cluster-focus-crumb home-cluster-focus-crumb-button", getUiString("overview", "Overview"));
        overviewCrumb.type = "button";
        overviewCrumb.addEventListener("click", clearSelectedBranch);
        breadcrumbs.appendChild(overviewCrumb);
        if (selectedBranch) {
          breadcrumbs.appendChild(makeNode("span", "home-cluster-focus-crumb-sep", "/"));
          if (selectedBranch.id === focusBranchId && !isPreview) {
            breadcrumbs.appendChild(
              makeNode("span", "home-cluster-focus-crumb home-cluster-focus-crumb-current", getDisplayLabel(selectedBranch))
            );
          } else {
            var selectedCrumb = makeNode(
              "button",
              "home-cluster-focus-crumb home-cluster-focus-crumb-button home-cluster-focus-crumb-selected",
              getDisplayLabel(selectedBranch)
            );
            selectedCrumb.type = "button";
            selectedCrumb.addEventListener("click", function () {
              if (setSelectedBranch(selectedBranch.id, { manual: true })) {
                renderHomeClusterMap(container, payload, nodes);
              }
            });
            breadcrumbs.appendChild(selectedCrumb);
          }
        }
        if (!selectedBranch || selectedBranch.id !== focusBranchId) {
          breadcrumbs.appendChild(makeNode("span", "home-cluster-focus-crumb-sep", "/"));
          breadcrumbs.appendChild(
            makeNode("span", "home-cluster-focus-crumb home-cluster-focus-crumb-current", getDisplayLabel(focusBranch))
          );
        }
        text.appendChild(breadcrumbs);

        var modeLabel = getUiString("active-branch", "Active branch");
        if (isPreview) {
          modeLabel = isVertical ? getUiString("preview-branch", "Preview branch") : getUiString("hover-preview", "Hover preview");
        } else if (isPinned) {
          modeLabel = isVertical ? getUiString("selected-branch", "Selected branch") : getUiString("pinned-branch", "Pinned branch");
        } else if (state.manualSelection) {
          modeLabel = getUiString("selected-branch", "Selected branch");
        }
        var headKicker = makeNode(
          "p",
          "home-cluster-kicker",
          modeLabel
        );
        text.appendChild(headKicker);

        if (isPreview && selectedBranch) {
          text.appendChild(
            makeNode(
              "p",
              "home-cluster-focus-context",
              formatUiString(
                "previewing-focus-selected-template",
                "Previewing {focus} while {selected} stays selected.",
                {
                  focus: getDisplayLabel(focusBranch),
                  selected: getDisplayLabel(selectedBranch)
                }
              )
            )
          );
        } else if (isPinned) {
          text.appendChild(
            makeNode(
              "p",
              "home-cluster-focus-context",
              isVertical
          ? getUiString("vertical-selected-branch-hint", "Tap another branch to switch the selection, or open a page from this branch.")
                : getUiString("horizontal-pinned-branch-hint", "Click another branch to pin it, or hover to preview without leaving this branch.")
            )
          );
        } else {
          text.appendChild(
            makeNode(
              "p",
              "home-cluster-focus-context",
              isVertical
                ? getUiString("vertical-branch-card-hint", "Tap a branch card to open its subtopics here.")
                : getUiString("horizontal-branch-card-hint", "Hover to preview a branch, then click to pin it in place.")
            )
          );
        }

        var headTitle = makeNode("h3", "home-cluster-focus-title");
        var headTitleLink = makeNode("a", "home-cluster-title-link", getFullLabel(focusBranch));
        headTitleLink.href = String(focusBranch.url || "#");
        headTitleLink.title = getFullLabel(focusBranch);
        headTitle.appendChild(headTitleLink);
        text.appendChild(headTitle);

        var focusMeta = getNodeMetaLine(focusBranch);
        if (focusMeta) {
          text.appendChild(makeNode("p", "home-cluster-focus-meta", focusMeta));
        }
        head.appendChild(text);

        var actions = makeNode("div", "home-cluster-focus-actions");
        if (isPreview) {
          var pinButton = makeNode("button", "home-cluster-action", getUiString("pin-branch", "Pin Branch"));
          pinButton.type = "button";
          pinButton.addEventListener("click", function () {
            if (setSelectedBranch(focusBranch.id, { manual: true })) {
              renderHomeClusterMap(container, payload, nodes);
            }
          });
          actions.appendChild(pinButton);
        }
        if (isPreview && selectedBranch) {
          var backToPinnedButton = makeNode("button", "home-cluster-action", getUiString("back-to-pinned", "Back to Pinned"));
          backToPinnedButton.type = "button";
          backToPinnedButton.addEventListener("click", function () {
            clearHoveredBranch(focusBranch.id, { immediate: true });
          });
          actions.appendChild(backToPinnedButton);
        }
        if (state.manualSelection) {
          var closeButton = makeNode("button", "home-cluster-focus-close", getUiString("back-to-overview", "Back to Overview"));
          closeButton.type = "button";
          closeButton.addEventListener("click", clearSelectedBranch);
          actions.appendChild(closeButton);
        }
        if (actions.childNodes.length > 0) {
          head.appendChild(actions);
        }

        focusTray.appendChild(head);

        var focusSummary = getNodeSummary(focusBranch);
        if (focusSummary) {
          focusTray.appendChild(makeNode("p", "home-cluster-node-summary", focusSummary));
        }

        var focusChildren = childrenByParent[focusBranch.id] || [];
        if (!focusChildren.length) {
          return;
        }

        var focusGrid = makeNode("div", "home-cluster-focus-grid");
        var childLimit = width >= 1360 ? 4 : (width >= 980 ? 3 : 2);
        if (focusChildren.length <= childLimit + 1) {
          childLimit = focusChildren.length;
        }
        getRankedRepresentativeNodes(focusChildren, childLimit).forEach(function (childNode) {
          focusGrid.appendChild(buildFocusChildCard(childNode));
        });

        if (focusChildren.length > childLimit) {
          var overflow = makeNode(
            "a",
            "home-cluster-overflow home-cluster-overflow-l2",
            getOverflowLabel(focusBranch, focusChildren.length - childLimit, { compact: true })
          );
          overflow.href = String(focusBranch.url || "#");
          overflow.title = "Open " + getFullLabel(focusBranch) + " for " + getOverflowLabel(focusBranch, focusChildren.length - childLimit);
          overflow.setAttribute("aria-label", overflow.title);
          focusGrid.appendChild(overflow);
        }

        focusTray.appendChild(focusGrid);
      }

      function bindBranchInteractions(target, branchNode, options) {
        if (!target || !branchNode || !branchNode.id) {
          return;
        }
        var opts = options || {};
        var branchId = String(branchNode.id);

        target.addEventListener("mouseenter", function () {
          setHoveredBranch(branchId);
        });
        target.addEventListener("mouseleave", function () {
          clearHoveredBranch(branchId);
        });
        target.addEventListener("focusin", function () {
          setHoveredBranch(branchId);
        });
        target.addEventListener("focusout", function (event) {
          if (!target.contains(event.relatedTarget)) {
            clearHoveredBranch(branchId);
          }
        });

        if (!opts.selectOnClick) {
          return;
        }
        target.addEventListener("click", function (event) {
          if (event.target && event.target.closest) {
            if (event.target.closest("a") || event.target.closest("button.ct-expand-toggle")) {
              return;
            }
          }
          if (setSelectedBranch(branchId, { manual: true })) {
            renderHomeClusterMap(container, payload, nodes);
          }
        });
      }

      function shouldShowNodeKicker(node, sizeClass) {
        var semantic = String(node.semantic_level || "").trim().toLowerCase();
        return sizeClass === "ct-node-root"
          || sizeClass === "ct-node-xl"
          || (semantic === "l1" && sizeClass !== "ct-node-sm")
          || (semantic === "l2" && sizeClass === "ct-node-lg");
      }

      function shouldShowNodeSummary(node, sizeClass) {
        var semantic = String(node.semantic_level || "").trim().toLowerCase();
        if (sizeClass === "ct-node-root" || sizeClass === "ct-node-xl") return true;
        if (semantic === "l1") return sizeClass === "ct-node-lg" || sizeClass === "ct-node-md";
        if (semantic === "l2") return sizeClass === "ct-node-lg";
        return false;
      }

      function shouldShowNodeMeta(node, sizeClass) {
        var semantic = String(node.semantic_level || "").trim().toLowerCase();
        if (sizeClass === "ct-node-root" || sizeClass === "ct-node-xl" || sizeClass === "ct-node-lg") return true;
        if ((semantic === "l1" || semantic === "l2") && sizeClass === "ct-node-md") return true;
        return false;
      }

      function shouldShowCountLabel(node, sizeClass) {
        var semantic = String(node.semantic_level || "").trim().toLowerCase();
        if (sizeClass === "ct-node-root" || sizeClass === "ct-node-xl") return true;
        if ((semantic === "l1" || semantic === "l2") && sizeClass !== "ct-node-sm") return true;
        return false;
      }



      function buildTreeNodeBubble(node, sizeClass) {

        var bubble = makeNode("div", "ct-node " + (sizeClass || "ct-node-md"));

        applyHomeClusterNodeMeta(bubble, node);

        var link = makeNode("a", "ct-node-link");

        link.href = String(node.url || "#");

        link.title = getFullLabel(node);

        link.setAttribute("aria-label", "Open page: " + getFullLabel(node));



        /* thumbnail or initial */

        var imgSrc = getNodeImage(node);

        var showThumb = sizeClass !== "ct-node-xs";

        if (imgSrc && showThumb) {

          var thumb = makeNode("div", "ct-node-thumb");

          var img = document.createElement("img");

          img.src = imgSrc;

          img.alt = "";

          img.loading = "lazy";

          img.decoding = "async";

          thumb.appendChild(img);

          link.appendChild(thumb);

        } else if (showThumb) {

          var initial = makeNode("span", "ct-node-initial", String(getFullLabel(node) || "U").slice(0, 1).toUpperCase());

          link.appendChild(initial);

        }

        var content = makeNode("span", "ct-node-content");

        if (shouldShowNodeKicker(node, sizeClass)) {
          content.appendChild(makeNode("span", "ct-node-kicker", getNodeLevelLabel(node)));
        }



        var labelText = (sizeClass === "ct-node-root")
          ? getFullLabel(node)
          : getDisplayLabel(node);

        var label = makeNode("span", "ct-node-label", labelText);

        content.appendChild(label);

        var summaryText = getNodeSummary(node);
        if (summaryText && shouldShowNodeSummary(node, sizeClass)) {
          content.appendChild(makeNode("span", "ct-node-summary", summaryText));
        }

        var metaText = getNodeMetaLine(node);
        if (metaText && shouldShowNodeMeta(node, sizeClass)) {
          content.appendChild(makeNode("span", "ct-node-meta", metaText));
        }

        link.appendChild(content);

        bubble.appendChild(link);



        /* count badge */

        var count = parseInt(String(node.count || 0), 10);

        var childTotal = parseInt(String(node.child_total || 0), 10);

        if (count > 1 || childTotal > 0) {

          var badgeText = shouldShowCountLabel(node, sizeClass)
          ? pluralizeWord(count || 1, "page")
            : String(count || 1);
          var badge = makeNode("span", "ct-node-badge", badgeText);

        badge.title = getNodeMetaLine(node) || (String(count) + " pages in this section");
          badge.setAttribute("aria-label", badge.title);

          bubble.appendChild(badge);

        }



        /* node size encoding */

        var descendantTotal = parseInt(String(node.descendant_total || 0), 10);

        if (descendantTotal >= 20) {

          bubble.classList.add("ct-node-heavy");

        } else if (descendantTotal >= 8) {

          bubble.classList.add("ct-node-medium");

        }



        return bubble;

      }



      function buildClusterDot(count, parentUrl, parentNode, options) {

        var dot = makeNode("a", "ct-cluster-dot");
        var compactLabel = getOverflowLabel(parentNode, count, { compact: true });
        var fullLabel = getOverflowLabel(parentNode, count, options);

        dot.href = String(parentUrl || "#");

        dot.title = fullLabel;
        dot.setAttribute("aria-label", fullLabel);

        dot.textContent = compactLabel;

        return dot;

      }

      function getFanoutColumnCount(count, availableWidth) {

        var branchCount = Math.max(1, parseInt(String(count || 1), 10) || 1);

        var usableWidth = Math.max(320, parseInt(String(availableWidth || width || 0), 10) || 320);

        var minCardWidth = branchCount <= 4 ? 260 : (branchCount <= 8 ? 232 : 214);

        var columns = Math.max(1, Math.floor((usableWidth - 56) / minCardWidth));

        if (branchCount >= 9 && usableWidth >= 1480) {

          columns = Math.max(columns, 5);

        } else if (branchCount >= 6 && usableWidth >= 1180) {

          columns = Math.max(columns, 4);

        } else if (usableWidth >= 880) {

          columns = Math.max(columns, 3);

        } else if (usableWidth >= 620) {

          columns = Math.max(columns, 2);

        }

        if (branchCount <= 8) {

          columns = Math.min(columns, 4);

        } else if (branchCount <= 12) {

          columns = Math.min(columns, 5);

        }

        return Math.max(1, Math.min(branchCount, columns));

      }

      function buildFanoutCard(branchNode, index) {

        var item = makeNode("div", "ct-fanout-item");

        item.setAttribute("data-branch-id", branchNode.id);

        item.setAttribute("data-branch-index", String(index));

        var bubble = buildTreeNodeBubble(branchNode, getNodeSizeClass(1, "fanout"));

        bubble.classList.add("ct-fanout-node");

        item.appendChild(bubble);
        bindBranchInteractions(item, branchNode, { selectOnClick: true });

        return item;

      }

      function getTreeColumnCount(branchCount, usableWidth, options) {
        var total = Math.max(1, parseInt(String(branchCount || 1), 10) || 1);
        var widthValue = Math.max(320, parseInt(String(usableWidth || width || 0), 10) || 320);
        var opts = options || {};
        var focusedBranchMode = !!opts.focusedBranchMode;
        var deepTree = !!opts.deepTree;

        if (total <= 1) return 1;

        if (widthValue >= 1560) {
          if (focusedBranchMode) {
            return Math.min(total, total >= 7 ? 4 : 3);
          }
          if (!deepTree && total >= 8) {
            return Math.min(total, 4);
          }
          if (total >= 5) {
            return Math.min(total, 3);
          }
          return Math.min(total, 2);
        }

        if (widthValue >= 1280) {
          if (focusedBranchMode) {
            return Math.min(total, total >= 5 ? 3 : 2);
          }
          if (!deepTree && total >= 7) {
            return Math.min(total, 3);
          }
          if (total >= 4) {
            return 2;
          }
          return 1;
        }

        if (widthValue >= 1024) {
          if (focusedBranchMode && total >= 5) {
            return 2;
          }
          if (total >= 6 && !deepTree) {
            return 2;
          }
        }

        return 1;
      }

      function getTreeBranchSpan(branchNode, treeColumns) {
        var columns = Math.max(1, parseInt(String(treeColumns || 1), 10) || 1);
        if (columns <= 1 || !branchNode) {
          return "regular";
        }

        var branchId = String(branchNode.id || "").trim();
        var isSelectedBranch = branchId && branchId === String(state.selectedBranchId || "").trim();
        var childCount = (childrenByParent[branchId] || []).length;
        var subtreeShape = branchNode.subtree_shape && typeof branchNode.subtree_shape === "object"
          ? branchNode.subtree_shape
          : {};
        var subtreeDepth = Math.max(0, parseInt(String(subtreeShape.max_depth || 0), 10) || 0);

        if (isSelectedBranch && shouldPreferFocusedBranch && childCount > 0) {
          return "full";
        }

        if (columns >= 3 && childCount >= 5 && subtreeDepth >= 2) {
          return "wide";
        }

        return "regular";
      }

      function getSubtreeLayout(parentNode, childDepth, childCount) {

        var hintedLayout = String((parentNode && parentNode.preferred_subtree_layout) || "").trim().toLowerCase();
        if (hintedLayout === "card-grid" || hintedLayout === "chip-grid") {
          if (strategy === "grid") {
            return "tree";
          }
          return hintedLayout;
        }

        var total = Math.max(0, parseInt(String(childCount || ((parentNode && parentNode.subtree_shape && parentNode.subtree_shape.child_count) || 0)), 10) || 0);

        if (!total) return "tree";

        if (strategy === "grid") return "tree";

        var localDepth = parseInt(String((parentNode && parentNode.subtree_shape && parentNode.subtree_shape.max_depth) || 0), 10);
        var localBreadth = parseInt(String((parentNode && parentNode.subtree_shape && parentNode.subtree_shape.max_breadth) || total), 10);

        if (childDepth === 2) {

          if (total <= 4 && width >= 760) return "card-grid";

          if (total <= 8 && width >= 1080 && String(parentNode.semantic_level || "") === "l1") {

            return "card-grid";

          }

          if (localDepth >= 2 && localBreadth <= 12 && total <= 6 && width >= 1240) {

            return "card-grid";

          }

          if (total <= 12 && width >= 1320 && String(parentNode.semantic_level || "") === "l1") {

            return "card-grid";

          }

        }

        if (childDepth >= 3 && total <= 6 && localDepth <= 2 && width >= 900) {

          return "chip-grid";

        }

        return "tree";

      }

      function buildSubtreeChipList(parentNode, children, maxVisible) {

        var chipList = makeNode("div", "ct-subtree-chip-list");
        chipList.setAttribute("data-ct-subtree-layout", "chip-grid");
        if (parentNode && parentNode.id) {
          chipList.setAttribute("data-parent-id", String(parentNode.id));
        }

        var visible = Math.max(0, parseInt(String(maxVisible || children.length), 10) || children.length);

        children.slice(0, visible).forEach(function (child) {

          var chip = makeNode("a", "ct-subtree-chip", getDisplayLabel(child));

          chip.href = String(child.url || "#");

          chip.title = getFullLabel(child);

          chipList.appendChild(chip);

        });

        if (children.length > visible) {

          chipList.appendChild(buildClusterDot(children.length - visible, parentNode.url, parentNode));

        }

        return chipList;

      }

      function buildSubtreeGrid(parentNode, children, childDepth, expanded, tier) {

        var grid = makeNode("div", "ct-subtree-grid ct-subtree-grid-l" + Math.min(childDepth, 4));
        grid.setAttribute("data-ct-subtree-layout", "card-grid");
        if (parentNode && parentNode.id) {
          grid.setAttribute("data-parent-id", String(parentNode.id));
        }

        var inlineLimit = expanded ? children.length : Math.min(children.length, childDepth === 2 ? 8 : 6);

        children.slice(0, inlineLimit).forEach(function (child) {

          var card = makeNode("div", "ct-subtree-card");

          var cardBubble = buildTreeNodeBubble(child, childDepth === 2 ? (width >= 1120 ? "ct-node-md" : "ct-node-sm") : "ct-node-sm");

          cardBubble.classList.add("ct-subtree-node");

          card.appendChild(cardBubble);

          var subChildren = childrenByParent[child.id] || [];

          if (subChildren.length > 0) {

            var isChildExpanded = !!state.expandedBranches[child.id];

            var subToggle = createExpandToggle(child, isChildExpanded);

            (function (nodeId) {

              subToggle.addEventListener("click", function () {

                state.expandedBranches[nodeId] = !state.expandedBranches[nodeId];

                container.__homeClusterState = state;

                renderHomeClusterMap(container, payload, nodes);

              });

            })(child.id);

            cardBubble.appendChild(subToggle);

            if (isChildExpanded || subChildren.length <= getInlineL3Limit(tier, strategy, child)) {

              card.appendChild(buildSubtreeChipList(child, subChildren, isChildExpanded ? subChildren.length : 4));

            }

          }

          grid.appendChild(card);

        });

        if (children.length > inlineLimit && !expanded) {

          var overflowCard = makeNode("div", "ct-subtree-card ct-subtree-card-overflow");

          overflowCard.appendChild(buildClusterDot(children.length - inlineLimit, parentNode.url, parentNode));

          grid.appendChild(overflowCard);

        }

        return grid;

      }



      /* --- Recursive child builder for any depth --- */

      function buildChildrenRecursive(parentNode, depth, expanded) {

        var children = childrenByParent[parentNode.id] || [];

        if (!children.length) return null;

        var tier = String(parentNode.density_tier || "balanced");

        var limit;

        if (depth <= 2) {

          limit = expanded ? children.length : getInlineChildLimit(tier, depth, strategy, parentNode);

        } else {

          limit = expanded ? children.length : getInlineL3Limit(tier, strategy, parentNode);

        }

        if (limit <= 0 && !expanded) return null;



        var childDepthForLayout = parseInt(String(depth || 0), 10) + 1;

        var subtreeLayout = getSubtreeLayout(parentNode, childDepthForLayout, children.length);

        if (subtreeLayout === "card-grid") {

          return buildSubtreeGrid(parentNode, children, childDepthForLayout, expanded, tier);

        }

        if (subtreeLayout === "chip-grid") {

          return buildSubtreeChipList(parentNode, children, expanded ? children.length : Math.min(children.length, 6));

        }

        var groupClass = depth <= 2 ? "ct-l2-group" : "ct-l3-group";

        var wrap = makeNode("div", groupClass);
        wrap.setAttribute("data-ct-subtree-layout", "tree");
        wrap.setAttribute("data-ct-child-depth", String(childDepthForLayout));
        if (parentNode && parentNode.id) {
          wrap.setAttribute("data-parent-id", String(parentNode.id));
        }

        var shown = children.slice(0, Math.min(limit, children.length));



        shown.forEach(function (child) {

          var childDepth = parseInt(String(child.depth || depth + 1), 10);

          var sizeClass = getNodeSizeClass(childDepth, strategy);

          var childRow = makeNode("div", "ct-tree-row ct-tree-row-l" + Math.min(childDepth, 4));

          if (strategy !== "cascade") {

            childRow.appendChild(makeNode("span", "ct-connector ct-connector-h", ""));

          }

          var childBubble = buildTreeNodeBubble(child, sizeClass);

          childRow.appendChild(childBubble);



          /* recursively build grandchildren */

          var isChildExpanded = !!state.expandedBranches[child.id];

          var subChildren = childrenByParent[child.id] || [];

          if (subChildren.length > 0) {

            /* add expand toggle */

            var subToggle = createExpandToggle(child, isChildExpanded);

            (function (nodeId) {

              subToggle.addEventListener("click", function () {

                state.expandedBranches[nodeId] = !state.expandedBranches[nodeId];

                container.__homeClusterState = state;

                renderHomeClusterMap(container, payload, nodes);

              });

            })(child.id);

            childBubble.appendChild(subToggle);

          }



          if (isChildExpanded || (subChildren.length > 0 && subChildren.length <= getInlineL3Limit(tier, strategy, child))) {

            var subGroup = buildChildrenRecursive(child, childDepth, isChildExpanded);

            if (subGroup) {

              if (strategy !== "cascade") {

                childRow.appendChild(makeNode("span", "ct-connector ct-connector-h", ""));

              }

              childRow.appendChild(subGroup);

            }

          }



          wrap.appendChild(childRow);

        });



        if (children.length > limit && !expanded) {

          var overflowRow = makeNode("div", "ct-tree-row ct-tree-row-l" + Math.min(depth + 1, 4));

          if (strategy !== "cascade") {

            overflowRow.appendChild(makeNode("span", "ct-connector ct-connector-h", ""));

          }

          overflowRow.appendChild(buildClusterDot(children.length - limit, parentNode.url, parentNode));

          wrap.appendChild(overflowRow);

        }

        return wrap;

      }



      /* --- L1 branch row builder --- */

      function buildBranchRow(branchNode, index) {

        var isSelectedBranch = String(state.selectedBranchId || "").trim() === String(branchNode.id || "").trim();

        var sizeClass = getNodeSizeClass(1, strategy);

        var row = makeNode("div", "ct-tree-row ct-tree-row-l1");

        row.setAttribute("data-branch-id", branchNode.id);

        row.setAttribute("data-branch-index", String(index));



        if (strategy !== "cascade") {

          row.appendChild(makeNode("span", "ct-connector ct-connector-h ct-connector-root", ""));

        }



        var l1Bubble = buildTreeNodeBubble(branchNode, sizeClass);

        row.appendChild(l1Bubble);



        bindBranchInteractions(row, branchNode, { selectOnClick: true });



        return row;

      }



      /* --- Grid pill builder (compact grid mode) --- */

      function buildGridPill(branchNode, index) {
        var isSelectedBranch = String(state.selectedBranchId || "").trim() === String(branchNode.id || "").trim();
        var descendantTotal = parseInt(String(branchNode.descendant_total || 0), 10);

        /* tag-cloud sizing: heavy branches get bigger pills */
        var pillSizeClass = "";
        if (descendantTotal >= 20) {
          pillSizeClass = " ct-grid-pill-lg";
        } else if (descendantTotal >= 8) {
          pillSizeClass = " ct-grid-pill-md";
        }

        var pill = makeNode("div", "ct-grid-pill" + pillSizeClass + (isSelectedBranch ? " ct-grid-pill-selected" : ""));
        pill.setAttribute("data-branch-id", branchNode.id);

        /* use larger node for heavy pills */
        var sizeClass = descendantTotal >= 20 ? "ct-node-md" : getNodeSizeClass(1, strategy);
        var bubble = buildTreeNodeBubble(branchNode, sizeClass);
        pill.appendChild(bubble);
        bindBranchInteractions(pill, branchNode, { selectOnClick: true });

        return pill;
      }



      /* === RENDER === */

      board.innerHTML = "";
      board.classList.remove("ct-layout-fanout", "ct-layout-cascade", "ct-layout-grid", "ct-layout-tree", "ct-vertical", "ct-horizontal");

      if (focusTray) {

        focusTray.innerHTML = "";

        focusTray.hidden = true;

      }



      var isVertical = width < 720;

      container.setAttribute("data-ct-strategy", strategy);
      container.setAttribute("data-ct-auto-strategy", autoStrategy);
      syncClusterLabels(strategy);

      board.classList.toggle("ct-vertical", isVertical);

      board.classList.toggle("ct-horizontal", !isVertical);



      /* Root node (all modes) */

      var rootRow = makeNode("div", "ct-root-row");

      var rootBubble = buildTreeNodeBubble(rootNode, "ct-node-root");

      if (strategy === "fanout") {
        rootBubble.classList.add("ct-node-root-wide");
      }

      rootRow.appendChild(rootBubble);



      if (strategy === "fanout") {

        /* --- CENTERED ROOT + RESPONSIVE CHILD FANOUT --- */

        board.classList.add("ct-layout-fanout");

        rootRow.appendChild(makeNode("span", "ct-connector ct-connector-rail ct-connector-fanout", ""));

        board.appendChild(rootRow);

        var fanoutWrap = makeNode("div", "ct-fanout-wrap");

        var fanoutGrid = makeNode("div", "ct-fanout-grid");
        var fanoutColumns = getFanoutColumnCount(l1Count, width);
        fanoutGrid.style.setProperty("--ct-fanout-columns", String(fanoutColumns));
        fanoutGrid.setAttribute("data-ct-columns", String(fanoutColumns));
        fanoutGrid.setAttribute("data-ct-subtree-layout", "fanout-grid");

        allBranches.forEach(function (branchNode, index) {

          fanoutGrid.appendChild(buildFanoutCard(branchNode, index));

        });

        fanoutWrap.appendChild(fanoutGrid);

        board.appendChild(fanoutWrap);



      } else if (strategy === "cascade") {

        /* --- VERTICAL CASCADE --- */

        board.classList.add("ct-layout-cascade");

        rootRow.appendChild(makeNode("span", "ct-connector ct-connector-v", ""));

        board.appendChild(rootRow);

        var cascadeWrap = makeNode("div", "ct-cascade-levels");

        var branchLevel = makeNode("div", "ct-cascade-row");

        allBranches.forEach(function (branchNode, index) {

          var branchItem = makeNode("div", "ct-cascade-item");

          branchItem.appendChild(buildBranchRow(branchNode, index));

          branchLevel.appendChild(branchItem);

        });

        cascadeWrap.appendChild(branchLevel);

        board.appendChild(cascadeWrap);



      } else if (strategy === "grid") {

        /* --- COMPACT GRID --- */

        board.classList.add("ct-layout-grid");

        board.appendChild(rootRow);

        var gridWrap = makeNode("div", "ct-grid-wrap");
        gridWrap.setAttribute("data-ct-subtree-layout", "top-level-grid");

        var maxPills = l1Count <= 50 ? l1Count : Math.min(60, l1Count);

        var shownBranches = allBranches.slice(0, maxPills);

        shownBranches.forEach(function (branchNode, index) {

          gridWrap.appendChild(buildGridPill(branchNode, index));

        });

        if (allBranches.length > maxPills) {

          gridWrap.appendChild(buildClusterDot(allBranches.length - maxPills, rootNode.url, rootNode));

        }

        board.appendChild(gridWrap);



      } else {

        /* --- HORIZONTAL TREE --- */

        board.classList.add("ct-layout-tree");

        rootRow.appendChild(makeNode("span", "ct-connector ct-connector-rail", ""));

        board.appendChild(rootRow);

        var treeWrap = makeNode("div", "ct-tree-wrap");
        var treeGrid = makeNode("div", "ct-tree-grid");
        var treeColumns = getTreeColumnCount(l1Count, width, {
          focusedBranchMode: shouldPreferFocusedBranch,
          deepTree: maxDepth >= 3
        });
        var treeMaxWidthRem = treeColumns >= 4 ? 104 : (treeColumns === 3 ? 98 : 92);
        treeGrid.style.setProperty("--ct-tree-columns", String(treeColumns));
        treeGrid.setAttribute("data-ct-tree-columns", String(treeColumns));
        treeWrap.style.setProperty("--ct-tree-max-width", String(treeMaxWidthRem) + "rem");

        allBranches.forEach(function (branchNode, index) {

          var branchItem = makeNode("div", "ct-tree-branch-item");
          var branchSpan = getTreeBranchSpan(branchNode, treeColumns);
          branchItem.setAttribute("data-ct-branch-span", branchSpan);
          if (branchSpan === "full") {
            branchItem.classList.add("ct-tree-branch-item-full");
          } else if (branchSpan === "wide") {
            branchItem.classList.add("ct-tree-branch-item-wide");
          }
          branchItem.appendChild(buildBranchRow(branchNode, index));
          treeGrid.appendChild(branchItem);

        });

        treeWrap.appendChild(treeGrid);
        board.appendChild(treeWrap);

      }

      syncBranchAttention();
      renderFocusTrayFromState();
      container.classList.toggle(
        "home-cluster-mobile-detail",
        !!(isVertical && shouldPreferFocusedBranch && state.manualSelection && String(state.selectedBranchId || "").trim())
      );

      if (focusTray && !focusTray.__homeClusterPreviewBound) {
        focusTray.__homeClusterPreviewBound = true;
        focusTray.addEventListener("mouseenter", function () {
          cancelPendingHoverClear();
          var pendingBranchId = String(container.__homeClusterPendingPreviewBranchId || "").trim();
          if (pendingBranchId && nodeById[pendingBranchId] && state.hoveredBranchId !== pendingBranchId) {
            setHoveredBranch(pendingBranchId);
          }
        });
        focusTray.addEventListener("focusin", function () {
          cancelPendingHoverClear();
        });
        focusTray.addEventListener("mouseleave", function () {
          if (isHoverPreviewActive()) {
            clearHoveredBranch(state.hoveredBranchId);
          }
        });
        focusTray.addEventListener("focusout", function (event) {
          if (focusTray.contains(event.relatedTarget)) {
            return;
          }
          if (isHoverPreviewActive()) {
            clearHoveredBranch(state.hoveredBranchId);
          }
        });
      }



      /* resize handler */

      if (!container.__homeClusterResizeHandler) {

        container.__homeClusterResizeHandler = function () {

          renderHomeClusterMap(container, payload, nodes);

        };

        window.addEventListener("resize", container.__homeClusterResizeHandler);

      }



      /* jump-pill handler */

      if (!container.__homeClusterJumpHandler) {

        container.__homeClusterJumpHandler = function (event) {

          var trigger = event.target && event.target.closest ? event.target.closest("[data-home-cluster-jump]") : null;

          if (!trigger) return;

          var branchBase = String(trigger.getAttribute("data-home-cluster-jump") || "").trim();

          var targetId = branchByBase[branchBase] || "";

          if (!targetId) return;

          event.preventDefault();

          setSelectedBranch(targetId, { manual: true });

          renderHomeClusterMap(container, payload, nodes);

          var targetRow = board.querySelector("[data-branch-id=\"" + targetId + "\"]");

          if (targetRow && typeof targetRow.scrollIntoView === "function") {

            targetRow.scrollIntoView({ block: "start", behavior: "smooth" });

          } else if (typeof container.scrollIntoView === "function") {

            container.scrollIntoView({ block: "start", behavior: "smooth" });

          }

        };

        document.addEventListener("click", container.__homeClusterJumpHandler);

      }



      /* strategy sub-switcher buttons */

      var stratSwitcher = container.querySelector("[data-ct-strategy-switcher]");

      if (stratSwitcher) {

        var stratBtns = stratSwitcher.querySelectorAll("[data-ct-strategy-btn]");

        Array.prototype.forEach.call(stratBtns, function (btn) {

          var btnStrategy = String(btn.getAttribute("data-ct-strategy-btn") || "").trim().toLowerCase();

          var isActive = (!container.getAttribute("data-ct-strategy-override") && (
            btnStrategy === autoStrategy
            || (autoStrategy === "fanout" && btnStrategy === "adaptive")
          ))

            || (btnStrategy === strategy && container.getAttribute("data-ct-strategy-override"));

          btn.classList.toggle("is-active", isActive);

          btn.setAttribute("aria-pressed", isActive ? "true" : "false");

          if (!btn.__ctStrategyBound) {

            btn.__ctStrategyBound = true;

            btn.addEventListener("click", function () {

              var nextStrategy = String(btn.getAttribute("data-ct-strategy-btn") || "").trim().toLowerCase();

              if (nextStrategy === "adaptive") {

                container.removeAttribute("data-ct-strategy-override");

              } else {

                container.setAttribute("data-ct-strategy-override", nextStrategy);

              }

              renderHomeClusterMap(container, payload, nodes);

            });

          }

        });

      }

    }



    function renderHomeGraph(container) {
      var dataNode = container.querySelector("[data-hierarchy-graph-data]");
      if (!dataNode) {
        return;
      }

      var payload = {};
      try {
        payload = JSON.parse(String(dataNode.textContent || "{}"));
      } catch (err) {
        payload = {};
      }
      var nodes = Array.isArray(payload.nodes) ? payload.nodes.slice() : [];
      if (!nodes.length) {
        container.hidden = true;
        return;
      }

      var mode = String(payload.mode || container.getAttribute("data-hierarchy-mode") || "tree-diagram").trim().toLowerCase();
      if (container.hasAttribute("data-home-cluster-map")) {
        renderHomeClusterMap(container, payload, nodes);
        return;
      }

      var svg = container.querySelector("svg");
      if (!svg) {
        return;
      }

      var compact = Boolean(container.clientWidth && container.clientWidth < 700 && mode !== "tree-diagram" && mode !== "cluster-diagram");
      var depthGroups = {};
      var childrenByParent = {};
      var positionsById = {};
      var maxDepth = 0;

      nodes.forEach(function (node) {
        node.depth = parseInt(String(node.depth || 0), 10);
        if (!Number.isFinite(node.depth) || node.depth < 0) {
          node.depth = 0;
        }
        maxDepth = Math.max(maxDepth, node.depth);
        if (!depthGroups[node.depth]) {
          depthGroups[node.depth] = [];
        }
        depthGroups[node.depth].push(node);
        var parentId = String(node.parent_id || "").trim();
        if (parentId) {
          if (!childrenByParent[parentId]) {
            childrenByParent[parentId] = [];
          }
          childrenByParent[parentId].push(node);
        }
      });

      Object.keys(depthGroups).forEach(function (depthKey) {
        depthGroups[depthKey].sort(function (a, b) {
          var aSlot = parseInt(String(a.slot_index || 0), 10);
          var bSlot = parseInt(String(b.slot_index || 0), 10);
          if (Number.isFinite(aSlot) && Number.isFinite(bSlot) && aSlot !== bSlot) {
            return aSlot - bSlot;
          }
          return String(a.label || "").localeCompare(String(b.label || ""));
        });
      });

      clearSvg(svg);

      var depthOneCount = (depthGroups[1] || []).length;
      var width = Math.max(980, container.clientWidth || 980);
      if (mode === "tree-diagram") {
        width = Math.max(width, 260 + (depthOneCount * 190));
      } else {
        width = Math.max(width, 1040);
      }
      if (compact) {
        width = Math.max(container.clientWidth || 360, 360);
      }
      var rowGap = compact ? 112 : 126;
      var height = 140 + ((maxDepth + 1) * rowGap);
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);

      var margin = compact ? 28 : 80;
      var rootNodes = depthGroups[0] || [];
      if (rootNodes.length) {
        rootNodes[0].x = Math.round(width / 2);
        rootNodes[0].y = 64;
        positionsById[rootNodes[0].id] = { x: rootNodes[0].x, y: rootNodes[0].y };
      }

      var depthOneNodes = depthGroups[1] || [];
      var depthOnePositions = buildSpreadPositions(
        depthOneNodes.length,
        margin + 40,
        width - margin - 40,
        compact ? 188 : 206
      );
      for (var depthOneIndex = 0; depthOneIndex < depthOneNodes.length; depthOneIndex += 1) {
        depthOneNodes[depthOneIndex].x = depthOnePositions[depthOneIndex].x;
        depthOneNodes[depthOneIndex].y = depthOnePositions[depthOneIndex].y;
        positionsById[depthOneNodes[depthOneIndex].id] = {
          x: depthOneNodes[depthOneIndex].x,
          y: depthOneNodes[depthOneIndex].y
        };
      }

      var depthTwoNodes = depthGroups[2] || [];
      if (depthTwoNodes.length) {
        var segmentCount = Math.max(1, depthOneNodes.length || rootNodes.length || 1);
        var segmentWidth = Math.max(168, Math.floor((width - (margin * 2)) / segmentCount));
        var fallbackParent = depthOneNodes[0] || rootNodes[0] || null;
        depthTwoNodes.forEach(function (node) {
          var parentId = String(node.parent_id || "").trim();
          var parentNode = null;
          if (parentId) {
            parentNode = depthOneNodes.filter(function (candidate) {
              return candidate.id === parentId;
            })[0] || rootNodes.filter(function (candidate) {
              return candidate.id === parentId;
            })[0] || null;
          }
          if (!parentNode) {
            parentNode = fallbackParent;
          }
          var parentIndex = Math.max(0, depthOneNodes.indexOf(parentNode));
          var siblings = childrenByParent[parentNode ? parentNode.id : ""] || [node];
          var siblingIndex = Math.max(0, siblings.indexOf(node));
          var segmentStart = margin + (parentIndex * segmentWidth);
          var segmentEnd = segmentStart + segmentWidth;
          var childPositions = buildSpreadPositions(
            siblings.length,
            segmentStart + 18,
            segmentEnd - 18,
            compact ? 308 : 336
          );
          var position = childPositions[siblingIndex] || {
            x: Math.round((segmentStart + segmentEnd) / 2),
            y: compact ? 308 : 336
          };
          node.x = position.x;
          node.y = position.y;
          positionsById[node.id] = { x: node.x, y: node.y };
        });
      }

      (payload.edges || []).forEach(function (edge) {
        var from = positionsById[String((edge && edge.from) || "")];
        var to = positionsById[String((edge && edge.to) || "")];
        if (!from || !to) {
          return;
        }
        appendEdge(svg, from.x, from.y + 30, to.x, to.y - 30, "hierarchy-graph-edge-tree");
      });

      nodes.forEach(function (node) {
        if (!positionsById[node.id]) {
          return;
        }
        node.x = positionsById[node.id].x;
        node.y = positionsById[node.id].y;
        appendNode(svg, node, { compact: compact });
      });
    }

    Array.prototype.forEach.call(homeGraphContainers, renderHomeGraph);
    Array.prototype.forEach.call(articleGraphContainers, renderArticleGraph);
    document.addEventListener("phoenix-home-mode-changed", function () {
      window.setTimeout(function () {
        Array.prototype.forEach.call(homeGraphContainers, renderHomeGraph);
      }, 0);
    });
  }

  function slugify(text) {
    var slug = String(text || "")
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\\s-]/g, "")
      .replace(/\\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
    return slug || "section";
  }

  function markEndnotesAnchor(articleRoot) {
    if (!articleRoot) {
      return;
    }
    var candidates = articleRoot.querySelectorAll("h1, h2, h3, h4, h5, h6, p, strong");
    for (var i = 0; i < candidates.length; i += 1) {
      var node = candidates[i];
      var label = String(node.textContent || "").trim().toLowerCase();
      if (label === "endnotes" || label === "references" || label === "sources") {
        if (!node.id) {
          node.id = "endnotes";
        }
        node.classList.add("endnotes-marker");
        return;
      }
    }
  }

  function initEndnotesCollapsing() {
    var article = document.querySelector(".article-body");
    var root = document.documentElement;
    if (!article || !root) {
      return;
    }

    markEndnotesAnchor(article);

    var mode = String(root.getAttribute("data-endnotes-mode") || "auto").toLowerCase();
    if (mode !== "auto" && mode !== "expanded" && mode !== "collapsed") {
      mode = "auto";
    }
    if (mode === "expanded") {
      return;
    }

    var threshold = parseInt(root.getAttribute("data-endnotes-collapse-threshold"), 10);
    if (!Number.isFinite(threshold) || threshold < 1) {
      threshold = 15;
    }
    var initialVisible = parseInt(root.getAttribute("data-endnotes-initial-visible"), 10);
    if (!Number.isFinite(initialVisible) || initialVisible < 1) {
      initialVisible = 15;
    }

    var marker = article.querySelector(".endnotes-marker, #endnotes");
    if (!marker) {
      return;
    }

    var entries = [];
    var sections = [];
    var currentSection = {
      heading: null,
      refs: [],
      lists: []
    };
    sections.push(currentSection);
    var cursor = marker.nextElementSibling;
    while (cursor) {
      if (cursor.classList && cursor.classList.contains("further-reading-section")) {
        break;
      }
      var tag = String(cursor.tagName || "").toUpperCase();
      if (/^H[1-6]$/.test(tag) && !cursor.classList.contains("endnotes-marker")) {
        var headingLabel = String(cursor.textContent || "").trim().toLowerCase();
        if (headingLabel === "additional references" || headingLabel === "additional sources") {
          cursor.classList.add("additional-references-marker");
          currentSection = {
            heading: cursor,
            refs: [],
            lists: []
          };
          sections.push(currentSection);
        } else {
          break;
        }
      }
      if (tag !== "SCRIPT" && tag !== "STYLE") {
        entries.push(cursor);
        if (tag === "OL" || tag === "UL") {
          currentSection.lists.push(cursor);
          var listItems = Array.prototype.filter.call(cursor.children, function (node) {
            return String((node && node.tagName) || "").toUpperCase() === "LI";
          });
          if (listItems.length) {
            cursor.classList.add("endnotes-entry-list");
            Array.prototype.forEach.call(listItems, function (item) {
              currentSection.refs.push({
                node: item,
                container: cursor
              });
            });
          } else {
            currentSection.refs.push({
              node: cursor,
              container: cursor
            });
          }
        } else if (!cursor.classList.contains("additional-references-marker")) {
          currentSection.refs.push({
            node: cursor,
            container: cursor
          });
        }
      }
      cursor = cursor.nextElementSibling;
    }

    if (!entries.length) {
      return;
    }

    var toggleTargets = [];
    Array.prototype.forEach.call(sections, function (section) {
      Array.prototype.forEach.call(section.refs, function (ref) {
        toggleTargets.push(ref);
      });
    });
    var summaryNoun = sections.length > 1 ? "references" : "endnotes";

    if (mode === "auto" && toggleTargets.length <= threshold) {
      return;
    }
    if (initialVisible >= toggleTargets.length) {
      return;
    }

    Array.prototype.forEach.call(toggleTargets, function (entry, index) {
      if (!entry || !entry.node) {
        return;
      }
      entry.node.classList.add("endnotes-entry");
      entry.node.classList.toggle("is-hidden-endnote", index >= initialVisible);
    });

    var controlGroups = [];
    var createControls = function (position) {
      var controls = document.createElement("div");
      controls.className = "endnotes-toggle-wrap";
      if (position === "bottom") {
        controls.classList.add("endnotes-toggle-wrap-bottom");
      }

      var summary = document.createElement("p");
      summary.className = "endnotes-toggle-summary";
      controls.appendChild(summary);

      var button = document.createElement("button");
      button.type = "button";
      button.className = "endnotes-toggle-button";
      controls.appendChild(button);

      controlGroups.push({ summary: summary, button: button });
      return controls;
    };

    var topControls = createControls("top");
    marker.insertAdjacentElement("afterend", topControls);

    var bottomControls = createControls("bottom");
    entries[entries.length - 1].insertAdjacentElement("afterend", bottomControls);

    var expanded = false;
    var setBlockHidden = function (node, hidden) {
      if (!node || !node.classList) {
        return;
      }
      node.classList.toggle("is-hidden-endnote-block", Boolean(hidden));
    };
    var applyControlState = function (summaryText, buttonText, ariaExpanded) {
      Array.prototype.forEach.call(controlGroups, function (group) {
        if (!group) {
          return;
        }
        group.summary.textContent = summaryText;
        group.button.textContent = buttonText;
        group.button.setAttribute("aria-expanded", ariaExpanded);
      });
    };
    var update = function () {
      Array.prototype.forEach.call(toggleTargets, function (entry, index) {
        if (!entry || !entry.node || !entry.node.classList) {
          return;
        }
        entry.node.classList.toggle("is-hidden-endnote", !expanded && index >= initialVisible);
      });
      Array.prototype.forEach.call(sections, function (section) {
        var visibleInSection = 0;
        Array.prototype.forEach.call(section.refs, function (entry) {
          if (!entry || !entry.node || !entry.node.classList) {
            return;
          }
          if (!entry.node.classList.contains("is-hidden-endnote")) {
            visibleInSection += 1;
          }
        });
        if (section.heading) {
          setBlockHidden(section.heading, !expanded && visibleInSection < 1);
        }
        Array.prototype.forEach.call(section.lists, function (listNode) {
          var listVisibleCount = 0;
          Array.prototype.forEach.call(section.refs, function (entry) {
            if (!entry || entry.container !== listNode || !entry.node || !entry.node.classList) {
              return;
            }
            if (!entry.node.classList.contains("is-hidden-endnote")) {
              listVisibleCount += 1;
            }
          });
          setBlockHidden(listNode, !expanded && listVisibleCount < 1);
        });
      });
      if (expanded) {
        applyControlState(
          "Showing all " + String(toggleTargets.length) + " " + summaryNoun + ".",
          "Show fewer references",
          "true"
        );
      } else {
        var hiddenCount = Math.max(0, toggleTargets.length - initialVisible);
        applyControlState(
          "Showing first " + String(initialVisible) + " of " + String(toggleTargets.length) + " " + summaryNoun + ".",
          "Show " + String(hiddenCount) + " more references",
          "false"
        );
      }
    };

    Array.prototype.forEach.call(controlGroups, function (group) {
      group.button.addEventListener("click", function () {
        expanded = !expanded;
        update();
      });
    });
    update();
  }

  function detectPseudoHeadings(article) {
    if (!article) {
      return;
    }
    var sourceLabelPattern = /\\b(?:academic|publishing|springer|wikipedia|researchgate|youtube|journal|press)\\b/i;
    var sourceLabelAliases = {
      "oup academic": true,
      "aip publishing": true,
      "wikipedia": true,
      "springer": true,
      "researchgate": true,
      "youtube": true,
      "academia": true,
      "academic": true
    };
    var blocks = article.querySelectorAll("p");
    Array.prototype.forEach.call(blocks, function (node) {
      if (!node || !node.parentElement) {
        return;
      }
      if (node.closest && node.closest(".related-reports")) {
        return;
      }
      if (node.classList.contains("pseudo-heading-level-2") || node.classList.contains("pseudo-heading-level-3")) {
        return;
      }
      var text = String(node.textContent || "").trim();
      if (!text || text.length < 3 || text.length > 110) {
        return;
      }
      if (/https?:\/\//i.test(text)) {
        return;
      }
      var childCount = node.children ? node.children.length : 0;
      if (childCount === 1) {
        var onlyChild = node.children[0];
        if (!onlyChild || !onlyChild.tagName) {
          return;
        }
        var tag = String(onlyChild.tagName || "").toLowerCase();
        if (["strong", "b", "em", "i"].indexOf(tag) === -1) {
          return;
        }
        var styledLevelClass = (tag === "em" || tag === "i") ? "pseudo-heading-level-3" : "pseudo-heading-level-2";
        node.classList.add(styledLevelClass);
        return;
      }
      if (childCount !== 0) {
        return;
      }

      var lower = text.toLowerCase();
      if (sourceLabelAliases[lower] || sourceLabelPattern.test(lower)) {
        if (text.split(/\\s+/).length <= 3) {
          return;
        }
      }
      if (/^[a-z0-9-]+(?:\\.[a-z0-9-]+)+$/.test(lower)) {
        return;
      }
      if (/^\\s*(?:\\[(?:\\d+)\\]|\\d+\\.)\\s+/.test(text)) {
        return;
      }
      if ((/[.!?]$/.test(text) && text.length > 42) || (text.indexOf(":") !== -1 && text.length > 70)) {
        return;
      }
      if (!/^[A-Z]/.test(text)) {
        return;
      }

      var prev = node.previousElementSibling;
      var prevIsHeading = false;
      if (prev && prev.tagName) {
        var prevTag = String(prev.tagName || "").toUpperCase();
        prevIsHeading = prevTag === "H2" || prevTag === "H3" || prevTag === "H4"
          || prev.classList.contains("pseudo-heading-level-2")
          || prev.classList.contains("pseudo-heading-level-3");
      }
      var levelClass = prevIsHeading ? "pseudo-heading-level-3" : "pseudo-heading-level-2";
      node.classList.add(levelClass);
    });
  }

  function buildPageToc() {
    var tocRoots = document.querySelectorAll("[data-page-toc], [data-mobile-page-toc]");
    var article = document.querySelector(".article-body");
    if (!tocRoots.length || !article) {
      return;
    }
    document.documentElement.setAttribute("data-page-toc-count", "0");

    markEndnotesAnchor(article);
    var realHeadings = article.querySelectorAll("h2, h3, h4");
    if (realHeadings.length < 2) {
      detectPseudoHeadings(article);
    }

    function shouldIncludeTocHeading(heading, text) {
      var label = String(text || "").trim();
      if (!label) {
        return false;
      }
      if (/^showing first \d+ of \d+ endnotes\.?$/i.test(label)) {
        return false;
      }
      if (/^showing first \d+ of \d+ additional sources\.?$/i.test(label)) {
        return false;
      }
      if (/^show \d+ more sources\.?$/i.test(label) || /^show fewer sources\.?$/i.test(label)) {
        return false;
      }
      if (/^additional references?$/i.test(label) || /^additional sources?$/i.test(label)) {
        return false;
      }
      if (/et al\.?$/i.test(label) && label.length < 90 && label.indexOf(":") === -1) {
        return false;
      }
      if (/^[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}(?:,\s*[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})+(?:\s+et al\.)?$/.test(label)) {
        return false;
      }
      if (heading && heading.classList && heading.classList.contains("endnotes-marker")) {
        return false;
      }
      return true;
    }

    var headings = article.querySelectorAll("h2, h3, h4, p.pseudo-heading-level-2, p.pseudo-heading-level-3");
    var dispatchState = function (hasHeadings) {
      try {
        document.dispatchEvent(
          new CustomEvent("phoenix-page-toc-built", {
            detail: { hasHeadings: Boolean(hasHeadings) }
          })
        );
      } catch (err) {
        // Ignore custom event failures.
      }
    };
    var renderEmptyState = function () {
      Array.prototype.forEach.call(tocRoots, function (rootNode) {
        rootNode.innerHTML = "<p class=\"page-toc-empty\">No section headings detected.</p>";
      });
      dispatchState(false);
    };
    if (!headings.length) {
      renderEmptyState();
      return;
    }

    var usedIds = {};
    var headingList = [];
    var tocEntries = [];
    var linkGroups = [];
    var lastActiveId = "";
    var forcedActiveId = "";
    var forcedActiveExpiresAt = 0;

    Array.prototype.forEach.call(headings, function (heading) {
      if (heading.closest && heading.closest(".related-reports, .further-reading-section, [data-page-toc-exclude]")) {
        return;
      }
      var text = String(heading.textContent || "").trim();
      text = text.replace(/^\\s*(?:#+\\s*)+/, "").trim();
      if (!shouldIncludeTocHeading(heading, text)) {
        return;
      }
      var baseId = heading.id || slugify(text);
      var nextId = baseId;
      var suffix = 2;
      while (usedIds[nextId]) {
        nextId = baseId + "-" + String(suffix);
        suffix += 1;
      }
      usedIds[nextId] = true;
      if (!heading.id) {
        heading.id = nextId;
      }

      headingList.push(heading);
    });

    if (!headingList.length) {
      renderEmptyState();
      return;
    }

    var activeTopLevelEntry = null;
    Array.prototype.forEach.call(headingList, function (heading) {
      var text = String(heading.textContent || "").trim().replace(/^\s*(?:#+\s*)+/, "").trim();
      var tagName = String(heading.tagName || "").toUpperCase();
      var isDepth3 = (
        tagName === "H3"
        || tagName === "H4"
        || heading.classList.contains("pseudo-heading-level-3")
      );
      var entry = {
        id: heading.id,
        heading: heading,
        text: text,
        depth: isDepth3 ? 3 : 2,
        children: []
      };
      if (entry.depth === 2 || !activeTopLevelEntry) {
        tocEntries.push(entry);
        activeTopLevelEntry = entry.depth === 2 ? entry : activeTopLevelEntry;
        if (entry.depth === 2) {
          activeTopLevelEntry = entry;
        }
      } else {
        activeTopLevelEntry.children.push(entry);
      }
    });

    var topLevelEntriesWithChildren = tocEntries.filter(function (entry) {
      return Boolean(entry.children && entry.children.length);
    });
    var hasNestedGroups = Boolean(topLevelEntriesWithChildren.length);
    var flatTocMode = !hasNestedGroups && tocEntries.length >= 3;
    var balancedSingleBranch = (
      tocEntries.length >= 5
      && topLevelEntriesWithChildren.length === 1
      && topLevelEntriesWithChildren[0].children.length >= 4
    );
    var pageTocMode = balancedSingleBranch ? "balanced-single-branch" : (flatTocMode ? "flat" : "default");

    Array.prototype.forEach.call(tocRoots, function (rootNode) {
      var tocList = document.createElement("ul");
      var linksById = {};
      var flatVisualIndex = 0;
      var setTocItemExpanded = function (item, isExpanded) {
        if (!item || !item.classList || !item.classList.contains("has-children")) {
          return;
        }
        item.classList.toggle("is-collapsed", !isExpanded);
        var toggle = item.querySelector(":scope > .page-toc-row > [data-page-toc-toggle]");
        if (!toggle) {
          return;
        }
        toggle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
        toggle.setAttribute("title", isExpanded ? "Collapse subsections" : "Expand subsections");
        toggle.textContent = isExpanded ? "-" : "+";
      };
      var setAllTocItemsExpanded = function (isExpanded) {
        Array.prototype.forEach.call(rootNode.querySelectorAll(".page-toc-item.has-children"), function (item) {
          setTocItemExpanded(item, isExpanded);
        });
      };
      var buildTocItem = function (entry, parentItem) {
        var li = document.createElement("li");
        li.className = "page-toc-item " + (entry.depth === 3 ? "toc-depth-3" : "toc-depth-2");
        var row = document.createElement("div");
        row.className = "page-toc-row";
        var hasChildren = Boolean(entry.children && entry.children.length);
        if (hasChildren) {
          li.classList.add("has-children");
          if (balancedSingleBranch) {
            li.classList.add("is-primary-group");
          }
          var toggle = document.createElement("button");
          toggle.type = "button";
          toggle.className = "page-toc-toggle";
          toggle.setAttribute("data-page-toc-toggle", "");
          toggle.setAttribute("aria-label", "Collapse subsections under " + entry.text);
          row.appendChild(toggle);
        }
        var link = document.createElement("a");
        link.href = "#" + entry.id;
        var isFlatPrimaryLink = flatTocMode && !parentItem;
        if (isFlatPrimaryLink) {
          flatVisualIndex += 1;
          li.classList.add("is-flat-link");
          var index = document.createElement("span");
          index.className = "page-toc-link-index";
          index.textContent = String(flatVisualIndex).padStart(2, "0");
          index.setAttribute("aria-hidden", "true");
          link.appendChild(index);
        }
        var label = document.createElement("span");
        label.className = "page-toc-link-label";
        label.textContent = entry.text;
        link.appendChild(label);
        if (isFlatPrimaryLink) {
          var cue = document.createElement("span");
          cue.className = "page-toc-link-cue";
          cue.textContent = "Jump";
          cue.setAttribute("aria-hidden", "true");
          link.appendChild(cue);
        }
        row.appendChild(link);
        li.appendChild(row);
        linksById[entry.id] = {
          link: link,
          item: li,
          parentItem: parentItem || null
        };
        if (hasChildren) {
          var childList = document.createElement("ul");
          childList.className = "page-toc-children";
          if (balancedSingleBranch) {
            childList.classList.add("page-toc-children-balanced");
          }
          Array.prototype.forEach.call(entry.children, function (childEntry) {
            childList.appendChild(buildTocItem(childEntry, li));
          });
          li.appendChild(childList);
          setTocItemExpanded(li, true);
          var toggleButton = row.querySelector("[data-page-toc-toggle]");
          if (toggleButton) {
            toggleButton.addEventListener("click", function () {
              var shouldExpand = li.classList.contains("is-collapsed");
              setTocItemExpanded(li, shouldExpand);
            });
          }
        }
        return li;
      };
      Array.prototype.forEach.call(tocEntries, function (entry) {
        tocList.appendChild(buildTocItem(entry, null));
      });
      rootNode.innerHTML = "";
      rootNode.classList.toggle("page-toc-balanced", balancedSingleBranch);
      rootNode.classList.toggle("page-toc-flat", flatTocMode);
      rootNode.setAttribute("data-page-toc-mode", pageTocMode);
      rootNode.appendChild(tocList);
      var controlsRoot = rootNode.parentElement || rootNode;
      var actionsRoot = controlsRoot.querySelector(".page-toc-actions, .mobile-page-toc-actions");
      if (actionsRoot) {
        actionsRoot.hidden = !hasNestedGroups;
      }
      var expandAllButton = controlsRoot.querySelector("[data-page-toc-expand-all]");
      if (expandAllButton) {
        expandAllButton.hidden = !hasNestedGroups;
        expandAllButton.disabled = !hasNestedGroups;
        expandAllButton.onclick = function () {
          setAllTocItemsExpanded(true);
        };
      }
      var collapseAllButton = controlsRoot.querySelector("[data-page-toc-collapse-all]");
      if (collapseAllButton) {
        collapseAllButton.hidden = !hasNestedGroups;
        collapseAllButton.disabled = !hasNestedGroups;
        collapseAllButton.onclick = function () {
          setAllTocItemsExpanded(false);
        };
      }
      linkGroups.push({
        rootNode: rootNode,
        linksById: linksById
      });
    });
    document.documentElement.setAttribute("data-page-toc-count", String(headingList.length));

    var scrollTocActiveLinkIntoView = function (rootNode, activeLink) {
      if (!rootNode || !activeLink || !rootNode.closest || !activeLink.getBoundingClientRect) {
        return;
      }
      var scrollContainer = rootNode.closest("[data-page-tools]")
        || rootNode.closest(".mobile-page-tools-body")
        || rootNode.closest("[data-mobile-page-tools]")
        || rootNode;
      if (!scrollContainer || !scrollContainer.getBoundingClientRect) {
        return;
      }
      if (scrollContainer.scrollHeight <= scrollContainer.clientHeight + 6) {
        return;
      }
      var containerRect = scrollContainer.getBoundingClientRect();
      var linkRect = activeLink.getBoundingClientRect();
      var pad = Math.max(18, Math.round(scrollContainer.clientHeight * 0.16));
      var upperBound = containerRect.top + pad;
      var lowerBound = containerRect.bottom - pad;
      if (linkRect.top >= upperBound && linkRect.bottom <= lowerBound) {
        return;
      }
      var targetTop = scrollContainer.scrollTop
        + (linkRect.top - containerRect.top)
        - Math.round(scrollContainer.clientHeight * 0.28);
      var maxTop = Math.max(0, scrollContainer.scrollHeight - scrollContainer.clientHeight);
      var nextTop = Math.max(0, Math.min(targetTop, maxTop));
      if (Math.abs(nextTop - scrollContainer.scrollTop) < 6) {
        return;
      }
      var prefersReducedMotion = false;
      try {
        prefersReducedMotion = Boolean(
          window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches
        );
      } catch (err) {
        prefersReducedMotion = false;
      }
      if (typeof scrollContainer.scrollTo === "function") {
        try {
          scrollContainer.scrollTo({ top: nextTop, behavior: prefersReducedMotion ? "auto" : "smooth" });
          return;
        } catch (err) {
          // Fall through to direct assignment.
        }
      }
      scrollContainer.scrollTop = nextTop;
    };

    var setForcedActiveId = function (nextId) {
      var normalizedId = String(nextId || "").replace(/^#/, "").trim();
      if (!normalizedId) {
        forcedActiveId = "";
        forcedActiveExpiresAt = 0;
        return;
      }
      forcedActiveId = normalizedId;
      forcedActiveExpiresAt = Date.now() + 1600;
    };

    var resolveForcedActiveId = function () {
      if (!forcedActiveId) {
        return "";
      }
      var targetHeading = null;
      for (var i = 0; i < headingList.length; i += 1) {
        if (headingList[i].id === forcedActiveId) {
          targetHeading = headingList[i];
          break;
        }
      }
      if (!targetHeading) {
        forcedActiveId = "";
        forcedActiveExpiresAt = 0;
        return "";
      }
      if (Date.now() > forcedActiveExpiresAt) {
        var releaseMarker = window.scrollY + Math.max(120, getAnchorOffsetPixels() + 72);
        if (targetHeading.offsetTop > releaseMarker + 12) {
          return forcedActiveId;
        }
        forcedActiveId = "";
        forcedActiveExpiresAt = 0;
        return "";
      }
      return forcedActiveId;
    };

    var updateActiveLink = function () {
      var activeId = headingList[0] ? headingList[0].id : "";
      var marker = window.scrollY + Math.max(120, getAnchorOffsetPixels() + 48);
      for (var i = 0; i < headingList.length; i += 1) {
        if (headingList[i].offsetTop <= marker) {
          activeId = headingList[i].id;
        }
      }
      var forcedId = resolveForcedActiveId();
      if (forcedId) {
        activeId = forcedId;
      }
      var activeChanged = activeId !== lastActiveId;
      lastActiveId = activeId;
      Array.prototype.forEach.call(linkGroups, function (group) {
        var currentLink = null;
        Object.keys(group.linksById).forEach(function (id) {
          var record = group.linksById[id];
          var link = record.link;
          var isActive = id === activeId;
          link.classList.toggle("is-active", isActive);
          if (isActive) {
            currentLink = link;
            if (record.parentItem && record.parentItem.classList.contains("is-collapsed")) {
              record.parentItem.classList.remove("is-collapsed");
              var toggle = record.parentItem.querySelector(":scope > .page-toc-row > [data-page-toc-toggle]");
              if (toggle) {
                toggle.setAttribute("aria-expanded", "true");
                toggle.setAttribute("title", "Collapse subsections");
                toggle.textContent = "-";
              }
            }
            link.setAttribute("aria-current", "location");
          } else {
            link.removeAttribute("aria-current");
          }
        });
        if (activeChanged && currentLink) {
          scrollTocActiveLinkIntoView(group.rootNode, currentLink);
        }
      });
    };

    Array.prototype.forEach.call(linkGroups, function (group) {
      Object.keys(group.linksById).forEach(function (id) {
        var record = group.linksById[id];
        var link = record && record.link;
        if (!link || typeof link.addEventListener !== "function") {
          return;
        }
        link.addEventListener("click", function () {
          setForcedActiveId(id);
          window.setTimeout(updateActiveLink, 0);
          window.setTimeout(updateActiveLink, 220);
        });
      });
    });

    window.addEventListener("hashchange", function () {
      setForcedActiveId(window.location.hash);
      updateActiveLink();
      window.setTimeout(updateActiveLink, 220);
    });

    window.addEventListener("scroll", updateActiveLink, { passive: true });
    updateActiveLink();
    dispatchState(true);
  }

  function initBackToTop() {
    var buttons = document.querySelectorAll("[data-back-to-top], [data-mobile-back-to-top], [data-footer-back-to-top]");
    if (!buttons.length) {
      return;
    }
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function () {
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
  }

  function createPageActionToast() {
    var toast = document.querySelector(".page-action-toast");
    if (toast) {
      return toast;
    }
    toast = document.createElement("div");
    toast.className = "page-action-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
    return toast;
  }

  var pageActionToastTimer = 0;

  function showPageActionToast(message) {
    if (!message || !document.body) {
      return;
    }
    var toast = createPageActionToast();
    if (!toast) {
      return;
    }
    toast.textContent = String(message);
    toast.classList.add("is-visible");
    window.clearTimeout(pageActionToastTimer);
    pageActionToastTimer = window.setTimeout(function () {
      toast.classList.remove("is-visible");
    }, 2200);
  }

  function copyTextToClipboard(text) {
    var value = String(text || "");
    if (!value) {
      return Promise.reject(new Error("Nothing to copy."));
    }
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      return navigator.clipboard.writeText(value);
    }
    return new Promise(function (resolve, reject) {
      var helper = document.createElement("textarea");
      helper.value = value;
      helper.setAttribute("readonly", "readonly");
      helper.style.position = "fixed";
      helper.style.top = "-9999px";
      helper.style.left = "-9999px";
      document.body.appendChild(helper);
      helper.focus();
      helper.select();
      try {
        var copied = document.execCommand("copy");
        document.body.removeChild(helper);
        if (copied) {
          resolve();
          return;
        }
      } catch (err) {
        document.body.removeChild(helper);
        reject(err);
        return;
      }
      reject(new Error("Copy command failed."));
    });
  }

  function createActionIcon(kind) {
    if (kind === "download") {
      return ""
        + "<svg viewBox=\"0 0 24 24\" focusable=\"false\" aria-hidden=\"true\">"
        + "<path d=\"M12 3v11\"></path>"
        + "<path d=\"m7 11 5 5 5-5\"></path>"
        + "<path d=\"M5 20h14\"></path>"
        + "</svg>";
    }
    return ""
      + "<svg viewBox=\"0 0 24 24\" focusable=\"false\" aria-hidden=\"true\">"
      + "<path d=\"M15 8a3 3 0 1 0-2.83-4\"></path>"
      + "<path d=\"M6 14a3 3 0 1 0 2.83 4\"></path>"
      + "<path d=\"M18 21a3 3 0 1 0 0-6\"></path>"
      + "<path d=\"m8.59 15.51 6.83 3.98\"></path>"
      + "<path d=\"m15.41 4.51-6.82 3.98\"></path>"
      + "</svg>";
  }

  function createActionButton(kind, label, options) {
    var settings = options || {};
    var button = document.createElement("button");
    button.type = "button";
    button.className = "page-action-button";
    if (settings.iconOnly) {
      button.classList.add("page-action-button-icon");
    }
    if (settings.title) {
      button.title = settings.title;
      button.setAttribute("aria-label", settings.title);
    } else if (label) {
      button.setAttribute("aria-label", label);
    }
    button.innerHTML = ""
      + "<span class=\"page-action-icon\" aria-hidden=\"true\">"
      + createActionIcon(kind)
      + "</span>"
      + "<span class=\"page-action-label\">"
      + String(label || "")
      + "</span>";
    return button;
  }

  function buildAssetSharePayload(assetData) {
    var fallbackTitle = String(document.title || "Infographic").trim();
    var label = String((assetData && assetData.label) || "").trim();
    return {
      title: label || fallbackTitle,
      text: label || fallbackTitle,
      url: String((assetData && assetData.url) || window.location.href)
    };
  }

  function getFileNameFromUrl(rawUrl, fallbackName) {
    var fallback = String(fallbackName || "download").trim() || "download";
    try {
      var parsed = new URL(String(rawUrl || ""), window.location.href);
      var segments = parsed.pathname.split("/");
      var lastSegment = decodeURIComponent(String(segments.pop() || "").trim());
      return lastSegment || fallback;
    } catch (err) {
      return fallback;
    }
  }

  function isDownloadableAssetUrl(rawUrl) {
    return /\.(?:svg|png|jpe?g|webp|gif|pdf)(?:[?#].*)?$/i.test(String(rawUrl || ""));
  }

  function resolvePrimaryAssetUrl(imageNode) {
    if (!imageNode) {
      return "";
    }
    var parentLink = imageNode.closest("a");
    var linkHref = parentLink ? String(parentLink.getAttribute("href") || "").trim() : "";
    if (linkHref && isDownloadableAssetUrl(linkHref)) {
      return new URL(linkHref, window.location.href).href;
    }
    var source = String(imageNode.currentSrc || imageNode.getAttribute("src") || "").trim();
    return source ? new URL(source, window.location.href).href : "";
  }

  function isPipelineActionableAssetUrl(rawUrl) {
    try {
      var parsed = new URL(String(rawUrl || ""), window.location.href);
      var pathname = decodeURIComponent(String(parsed.pathname || ""));
      if (pathname.indexOf("/assets/images/") === -1) {
        return false;
      }
      return /(?:-overview\.(?:png|jpe?g|webp)|-image1\.(?:png|jpe?g|webp)|-Illustration-[123]\.(?:svg|png|jpe?g|webp))$/i.test(pathname);
    } catch (err) {
      return false;
    }
  }

  function getImageActionHost(imageNode, article) {
    if (!imageNode || !article) {
      return null;
    }
    var galleryItem = imageNode.closest(".svg-gallery-item");
    if (galleryItem && article.contains(galleryItem)) {
      return galleryItem;
    }
    var figure = imageNode.closest("figure");
    if (figure && article.contains(figure)) {
      return figure;
    }

    var parent = imageNode.parentElement;
    if (parent && parent.tagName === "A") {
      return parent;
    }
    return imageNode;
  }

  function ensureMediaActionHost(hostNode) {
    if (!hostNode) {
      return null;
    }
    if (hostNode.classList && hostNode.classList.contains("article-hero-media")) {
      return hostNode;
    }
    if (hostNode.classList && hostNode.classList.contains("page-media-action-shell")) {
      return hostNode;
    }
    var tagName = String(hostNode.tagName || "").toUpperCase();
    if (tagName === "IMG" || tagName === "A") {
      var wrapper = document.createElement("div");
      wrapper.className = "page-media-action-shell page-media-action-shell-direct";
      hostNode.parentNode.insertBefore(wrapper, hostNode);
      wrapper.appendChild(hostNode);
      return wrapper;
    }
    hostNode.classList.add("page-media-action-shell");
    return hostNode;
  }

  function triggerFileDownload(downloadUrl, filename) {
    if (!downloadUrl) {
      return false;
    }
    var link = document.createElement("a");
    link.href = downloadUrl;
    link.download = filename || "";
    link.rel = "noopener";
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    return true;
  }

  function getArticleAssets(article) {
    if (!article) {
      return [];
    }
    var assets = [];
    var images = article.querySelectorAll("img");
    Array.prototype.forEach.call(images, function (imageNode) {
      if (!imageNode) {
        return;
      }
      if (imageNode.closest(".related-reports, .image-lightbox, .topic-card-media")) {
        return;
      }
      var assetUrl = resolvePrimaryAssetUrl(imageNode);
      if (!assetUrl || !isPipelineActionableAssetUrl(assetUrl)) {
        return;
      }
      assets.push({
        image: imageNode,
        host: getImageActionHost(imageNode, article),
        url: assetUrl,
        downloadName: getFileNameFromUrl(assetUrl, "image"),
        label: String(imageNode.getAttribute("alt") || document.title || "Infographic").trim()
      });
    });
    return assets;
  }

  function getHeroPreviewAsset() {
    var heroMedia = document.querySelector(".article-hero-media");
    if (!heroMedia) {
      return null;
    }
    var heroImage = heroMedia.querySelector("img");
    if (!heroImage) {
      return null;
    }
    var assetUrl = resolvePrimaryAssetUrl(heroImage);
    if (!assetUrl || !isPipelineActionableAssetUrl(assetUrl)) {
      return null;
    }
    return {
      image: heroImage,
      host: heroMedia,
      url: assetUrl,
      downloadName: getFileNameFromUrl(assetUrl, "image"),
          label: String(heroImage.getAttribute("alt") || document.title || "Page preview").trim()
    };
  }

  function isSvgAssetUrl(rawUrl) {
    try {
      var parsed = new URL(String(rawUrl || ""), window.location.href);
      return /\.svg$/i.test(String(parsed.pathname || ""));
    } catch (err) {
      return false;
    }
  }

  function getResolvedImageDisplayUrl(imageNode) {
    if (!imageNode) {
      return "";
    }
    var current = String(imageNode.currentSrc || imageNode.getAttribute("src") || "").trim();
    if (!current) {
      return "";
    }
    try {
      return new URL(current, window.location.href).href;
    } catch (err) {
      return "";
    }
  }

  function canExpandImageAsset(asset) {
    if (!asset || !asset.image) {
      return false;
    }
    var assetUrl = String(asset.url || "").trim();
    if (!assetUrl) {
      return false;
    }
    if (isSvgAssetUrl(assetUrl)) {
      return true;
    }
    var displayedUrl = getResolvedImageDisplayUrl(asset.image);
    if (displayedUrl && displayedUrl !== assetUrl) {
      return true;
    }
    var renderedWidth = 0;
    var renderedHeight = 0;
    if (asset.image.getBoundingClientRect) {
      var rect = asset.image.getBoundingClientRect();
      renderedWidth = Number(rect.width || 0);
      renderedHeight = Number(rect.height || 0);
    }
    var naturalWidth = Number(asset.image.naturalWidth || 0);
    var naturalHeight = Number(asset.image.naturalHeight || 0);
    if (!(naturalWidth > 0 && naturalHeight > 0 && renderedWidth > 0 && renderedHeight > 0)) {
      return false;
    }
    return naturalWidth > renderedWidth * 1.12 || naturalHeight > renderedHeight * 1.12;
  }

  function initPageActionButtons() {
    return;
  }

  function initImageLightbox() {
    var body = document.body;
    var article = document.querySelector(".article-body");
    if (!article || !body || body.classList.contains("page-home")) {
      return;
    }

    var actionableAssets = getArticleAssets(article);
    var heroPreviewAsset = getHeroPreviewAsset();
    if (heroPreviewAsset) {
      actionableAssets.unshift(heroPreviewAsset);
    }
    if (!actionableAssets.length) {
      return;
    }

    var overlay = document.createElement("div");
    overlay.className = "image-lightbox";
    overlay.setAttribute("hidden", "hidden");
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML = ""
      + "<button type=\"button\" class=\"image-lightbox-close\" aria-label=\"Close image viewer\">Close</button>"
      + "<img class=\"image-lightbox-image\" alt=\"\">"
      + "<p class=\"image-lightbox-caption\"></p>";
    document.body.appendChild(overlay);

    var closeButton = overlay.querySelector(".image-lightbox-close");
    var stageImage = overlay.querySelector(".image-lightbox-image");
    var stageCaption = overlay.querySelector(".image-lightbox-caption");
    var previousOverflow = "";

    function closeOverlay() {
      overlay.setAttribute("hidden", "hidden");
      overlay.setAttribute("aria-hidden", "true");
      stageImage.removeAttribute("src");
      stageImage.alt = "";
      if (stageCaption) {
        stageCaption.textContent = "";
      }
      document.body.style.overflow = previousOverflow || "";
    }

    function openOverlay(asset) {
      if (!asset || !asset.image) {
        return;
      }
      var src = String(asset.url || "").trim();
      if (!src) {
        return;
      }
      var alt = String(asset.label || asset.image.getAttribute("alt") || "").trim();
      previousOverflow = document.body.style.overflow || "";
      stageImage.src = src;
      stageImage.alt = alt;
      if (stageCaption) {
        stageCaption.textContent = alt;
      }
      overlay.removeAttribute("hidden");
      overlay.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    }

    function attachImageHandler(asset) {
      if (!asset || !asset.image) {
        return;
      }
      var imageNode = asset.image;
      if (imageNode.classList.contains("zoomable-image")) {
        return;
      }
      var hostNode = ensureMediaActionHost(asset.host || getImageActionHost(imageNode, article));
        if (hostNode && hostNode.classList) {
          hostNode.classList.add("has-lightbox-affordance");
          if (!hostNode.querySelector("[data-lightbox-affordance]")) {
            var affordance = document.createElement("span");
            affordance.className = "image-lightbox-affordance";
            affordance.setAttribute("data-lightbox-affordance", "true");
            affordance.innerHTML = '<span class="image-lightbox-affordance-icon" aria-hidden="true">+</span><span class="image-lightbox-affordance-label">View Large</span>';
            hostNode.appendChild(affordance);
          }
        }
      imageNode.classList.add("zoomable-image");
      imageNode.setAttribute("tabindex", "0");
      imageNode.setAttribute("role", "button");
      if (!imageNode.getAttribute("aria-label")) {
        var altText = String(imageNode.getAttribute("alt") || "").trim();
        imageNode.setAttribute("aria-label", altText ? ("Expand image: " + altText) : "Expand image");
      }

      imageNode.addEventListener("click", function (event) {
        event.preventDefault();
        openOverlay(asset);
      });

      imageNode.addEventListener("keydown", function (event) {
        var key = String(event.key || "");
        if (key === "Enter" || key === " ") {
          event.preventDefault();
          openOverlay(asset);
        }
      });

      var parentLink = imageNode.closest("a");
      if (parentLink) {
        parentLink.addEventListener("click", function (event) {
          event.preventDefault();
          openOverlay(asset);
        });
      }
    }

    Array.prototype.forEach.call(actionableAssets, function (asset) {
      if (!asset || !asset.image) {
        return;
      }
      var evaluateExpandability = function () {
        if (canExpandImageAsset(asset)) {
          attachImageHandler(asset);
        }
      };
      if (asset.image.complete) {
        evaluateExpandability();
        return;
      }
      asset.image.addEventListener("load", evaluateExpandability, { once: true });
    });

    if (closeButton) {
      closeButton.addEventListener("click", function () {
        closeOverlay();
      });
    }

    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) {
        closeOverlay();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !overlay.hasAttribute("hidden")) {
        closeOverlay();
      }
    });
  }

  function initScrollAnimations() {
    var animElements = document.querySelectorAll(
      ".topic-card, .home-featured, .home-hero, .home-hierarchy-band, .home-detailed-catalog, .article-hero, .article-branch-map, .article-body > figure, .article-body > .page-media-action-shell-direct, .article-body > .youtube-embed-container, .article-body > .svg-gallery, .site-footer"
    );
    if (!animElements.length || !("IntersectionObserver" in window)) {
      var revealFallback = function() {
        for (var i = 0; i < animElements.length; i++) {
          animElements[i].classList.add("is-visible");
        }
      };
      revealFallback();
      return;
    }
    var observer = new IntersectionObserver(function(entries, obs) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        }
      });
    }, {
      root: null,
      rootMargin: "0px",
      threshold: 0.1
    });

    Array.prototype.forEach.call(animElements, function(el, index) {
      el.classList.add("animate-on-scroll");
      el.style.setProperty("--reveal-delay", String(Math.min(index * 36, 220)) + "ms");
      observer.observe(el);
    });
  }

  function initOptionalHeroMedia() {
    var heroImages = document.querySelectorAll(".article-hero-media img");
    Array.prototype.forEach.call(heroImages, function (image) {
      var media = image.closest(".article-hero-media");
      var grid = image.closest(".article-hero-grid");
      if (!media || !grid) {
        return;
      }

      var collapseMedia = function () {
        media.setAttribute("hidden", "hidden");
        grid.classList.remove("has-visual");
      };

      if (image.complete && image.naturalWidth === 0) {
        collapseMedia();
        return;
      }

      image.addEventListener("error", collapseMedia, { once: true });
    });
  }

  function initOptionalCardMedia() {
    var cardImages = document.querySelectorAll(".topic-card-media img");
    Array.prototype.forEach.call(cardImages, function (image) {
      var media = image.closest(".topic-card-media");
      if (!media) {
        return;
      }

      var applyFallback = function () {
        if (media.getAttribute("data-media-fallback") === "true") {
          return;
        }
        media.setAttribute("data-media-fallback", "true");
        media.classList.add("topic-card-placeholder", "is-fallback");
        image.remove();
        if (!media.querySelector(".topic-card-initial")) {
          var card = media.closest(".topic-card");
          var titleNode = card ? card.querySelector("h3 a, h3") : null;
          var label = String(
            (titleNode && titleNode.textContent) ||
            media.getAttribute("title") ||
            "?"
          ).trim();
          var initial = document.createElement("span");
          initial.className = "topic-card-initial";
          initial.textContent = (label.charAt(0) || "?").toUpperCase();
          media.appendChild(initial);
        }
      };

      if (image.complete && image.naturalWidth === 0) {
        applyFallback();
        return;
      }

      image.addEventListener("error", applyFallback, { once: true });
    });
  }

  function init() {
    var sidebarReady = initSidebarHydration();
    initScrollAnimations();
    initOptionalHeroMedia();
    initOptionalCardMedia();
    initAnchorOffsetSync();
    buildPageToc();
    initMobilePageTools();
    initMobileSidebarMode();
    initMobileQuickNav();
    initSidebarDocking();
    initHomeResponsiveDisclosures();
    initHomeModeSwitcher();
    initHomeFilter();
    initArchiveSearch();
    initHomeCardNavigation();
    initHierarchyGraphs();
    initEndnotesCollapsing();
    initPageActionButtons();
    initBackToTop();
    initImageLightbox();

    sidebarReady.finally(function () {
      markActiveSidebarLink();
      initSidebarCollapsing();
      initSidebarFilter();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
