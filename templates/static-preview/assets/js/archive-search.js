(function () {
  function normalizeText(value) {
    return String(value || "").toLowerCase();
  }

  function tokenize(query) {
    return normalizeText(query)
      .split(/[^a-z0-9]+/)
      .map(function (token) {
        return token.trim();
      })
      .filter(Boolean);
  }

  function matchesEntry(entry, query) {
    var haystack = normalizeText(entry && entry.search_text);
    var tokens = tokenize(query);
    if (!tokens.length) {
      return false;
    }
    return tokens.every(function (token) {
      return haystack.indexOf(token) !== -1;
    });
  }

  function scoreEntry(entry, query) {
    var normalizedQuery = normalizeText(query).trim();
    var tokens = tokenize(query);
    var title = normalizeText(entry && entry.title);
    var summary = normalizeText(entry && entry.summary);
    var section = normalizeText(entry && entry.section);
    var tags = Array.isArray(entry && entry.tags) ? entry.tags.map(normalizeText).join(" ") : "";
    var url = normalizeText(entry && entry.url);
    var haystack = normalizeText(entry && entry.search_text);
    var score = 0;

    tokens.forEach(function (token) {
      if (title.indexOf(token) !== -1) {
        score += 120;
      }
      if (url.indexOf(token) !== -1) {
        score += 90;
      }
      if (tags.indexOf(token) !== -1) {
        score += 70;
      }
      if (section.indexOf(token) !== -1) {
        score += 40;
      }
      if (summary.indexOf(token) !== -1) {
        score += 20;
      }
      if (haystack.indexOf(token) !== -1) {
        score += 4;
      }
    });

    if (normalizedQuery && title.indexOf(normalizedQuery) !== -1) {
      score += 300;
    }
    if (normalizedQuery && url.indexOf(normalizedQuery) !== -1) {
      score += 180;
    }
    if (entry && entry.kind === "page") {
      score += 12;
    }
    return score;
  }

  function setStatus(node, message, state) {
    if (!node) {
      return;
    }
    node.textContent = String(message || "");
    if (state) {
      node.setAttribute("data-state", state);
    } else {
      node.removeAttribute("data-state");
    }
  }

  function renderEmpty(resultsNode, message) {
    resultsNode.innerHTML = "";
    var empty = document.createElement("div");
    empty.className = "archive-search-empty";
    empty.textContent = message;
    resultsNode.appendChild(empty);
  }

  function renderResult(entry) {
    var card = document.createElement("article");
    card.className = "search-result-card";

    var kicker = document.createElement("p");
    kicker.className = "search-result-kicker";
    kicker.textContent = String((entry && entry.kicker) || "Page");
    card.appendChild(kicker);

    var title = document.createElement("h2");
    title.className = "search-result-title";
    var link = document.createElement("a");
    link.href = String((entry && entry.url) || "/search/");
    link.textContent = String((entry && entry.title) || "Untitled");
    title.appendChild(link);
    card.appendChild(title);

    if (entry && entry.summary) {
      var summary = document.createElement("p");
      summary.className = "search-result-summary";
      summary.textContent = String(entry.summary);
      card.appendChild(summary);
    }

    var metaBits = [];
    if (entry && entry.section) {
      metaBits.push(String(entry.section));
    }
    if (entry && entry.url) {
      metaBits.push(String(entry.url));
    }
    if (metaBits.length) {
      var meta = document.createElement("p");
      meta.className = "search-result-meta";
      meta.textContent = metaBits.join(" | ");
      card.appendChild(meta);
    }

    if (entry && Array.isArray(entry.tags) && entry.tags.length) {
      var tagList = document.createElement("div");
      tagList.className = "search-result-tags";
      entry.tags.slice(0, 6).forEach(function (tag) {
        var chip = document.createElement("span");
        chip.className = "search-tag";
        chip.textContent = String(tag);
        tagList.appendChild(chip);
      });
      card.appendChild(tagList);
    }

    return card;
  }

  function syncUrl(query) {
    if (!window.history || typeof window.history.replaceState !== "function") {
      return;
    }
    var url = new URL(window.location.href);
    if (query) {
      url.searchParams.set("q", query);
    } else {
      url.searchParams.delete("q");
    }
    window.history.replaceState({}, "", url.toString());
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
    var results = document.querySelector("[data-archive-search-results]");
    if (!source || !form || !input || !results) {
      return;
    }

    var loadedEntries = [];
    var loadPromise = null;
    var inputTimer = 0;

    function ensureLoaded() {
      if (loadPromise) {
        return loadPromise;
      }
      setStatus(status, "Loading search index...", "loading");
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
    }

    function applySearch() {
      var query = String(input.value || "").trim();
      syncUrl(query);
      if (clearButton) {
        clearButton.hidden = !query;
      }
      ensureLoaded()
        .then(function (entries) {
          if (!query) {
            setStatus(status, "Loaded " + String(entries.length) + " archive entries. Enter keywords to search the archive.", "default");
            renderEmpty(results, "Enter a keyword to search across titles, summaries, headings, tags, and section labels.");
            return;
          }

          var matches = entries
            .filter(function (entry) {
              return matchesEntry(entry, query);
            })
            .map(function (entry, index) {
              return { entry: entry, score: scoreEntry(entry, query), index: index };
            })
            .sort(function (left, right) {
              if (right.score !== left.score) {
                return right.score - left.score;
              }
              return left.index - right.index;
            });

          results.innerHTML = "";
          if (!matches.length) {
            setStatus(status, "No archive entries match \"" + query + "\".", "empty");
            renderEmpty(results, "No results for \"" + query + "\". Try a broader year, case, author, personality, place, or tag.");
            return;
          }

          matches.slice(0, pageSize).forEach(function (match) {
            results.appendChild(renderResult(match.entry));
          });
          if (matches.length > pageSize) {
            setStatus(status, "Showing " + String(pageSize) + " of " + String(matches.length) + " results for \"" + query + "\".", "active");
          } else {
            setStatus(status, "Showing " + String(matches.length) + " results for \"" + query + "\".", "active");
          }
        })
        .catch(function () {
          setStatus(status, "Search is temporarily unavailable because the archive index could not be loaded.", "empty");
          renderEmpty(results, "Search is temporarily unavailable because the archive index could not be loaded.");
        });
    }

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
        setStatus(status, "Search is temporarily unavailable because the archive index could not be loaded.", "empty");
        renderEmpty(results, "Search is temporarily unavailable because the archive index could not be loaded.");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initArchiveSearch);
  } else {
    initArchiveSearch();
  }
})();
