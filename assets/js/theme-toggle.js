(function () {
  var ROOT = document.documentElement;
  var STORAGE_THEME_KEY = "phoenix-theme";
  var STORAGE_COLOR_MODE_KEY = "phoenix-color-mode";
  var STORAGE_TEXT_KEY = "phoenix-appearance-text";
  var STORAGE_WIDTH_KEY = "phoenix-appearance-width";
  var STORAGE_PANEL_COLLAPSED_KEY = "phoenix-appearance-panel-collapsed";

  function safeRead(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function safeWrite(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      // Ignore storage write failures.
    }
  }

  function toBool(value, fallback) {
    var token = String(value == null ? "" : value).trim().toLowerCase();
    if (!token) {
      return Boolean(fallback);
    }
    if (token === "1" || token === "true" || token === "yes" || token === "on") {
      return true;
    }
    if (token === "0" || token === "false" || token === "no" || token === "off") {
      return false;
    }
    return Boolean(fallback);
  }

  function rootDefault(attributeName, fallback) {
    if (!ROOT) {
      return fallback;
    }
    var value = ROOT.getAttribute(attributeName);
    if (value == null || String(value).trim() === "") {
      return fallback;
    }
    return String(value).trim();
  }

  function normalize(value, allowed, fallback) {
    var token = String(value || "").trim().toLowerCase();
    if (allowed.indexOf(token) !== -1) {
      return token;
    }
    return String(fallback || "").trim().toLowerCase();
  }

  function detectSystemTheme() {
    try {
      if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
      }
    } catch (err) {
      // Ignore matchMedia failures.
    }
    return "light";
  }

  function applyTheme(theme) {
    var normalized = theme === "dark" ? "dark" : "light";
    ROOT.setAttribute("data-theme", normalized);
    return normalized;
  }

  function currentTheme() {
    return ROOT.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function currentColorMode() {
    return normalize(ROOT.getAttribute("data-color-mode"), ["automatic", "light", "dark"], "automatic");
  }

  function syncRadio(selector, value) {
    var options = document.querySelectorAll(selector);
    if (!options.length) {
      return;
    }
    Array.prototype.forEach.call(options, function (option) {
      option.checked = String(option.value || "").toLowerCase() === String(value || "").toLowerCase();
    });
  }

  function updateThemeButtonState(theme, colorMode) {
    var button = document.querySelector("[data-theme-toggle]");
    if (!button) {
      return;
    }
    var nextTheme = theme === "dark" ? "light" : "dark";
    if (colorMode === "automatic") {
      button.setAttribute("aria-label", "Switch to manual " + nextTheme + " mode");
      button.setAttribute("title", "Switch to manual " + nextTheme + " mode");
    } else {
      button.setAttribute("aria-label", "Switch to " + nextTheme + " mode");
      button.setAttribute("title", "Switch to " + nextTheme + " mode");
    }
    button.setAttribute("aria-pressed", String(theme === "dark"));
  }

  function applyColorMode(mode, persist) {
    var defaultMode = normalize(rootDefault("data-appearance-color-default", "automatic"), ["automatic", "light", "dark"], "automatic");
    var normalizedMode = normalize(mode, ["automatic", "light", "dark"], defaultMode);
    ROOT.setAttribute("data-color-mode", normalizedMode);
    var resolvedTheme = normalizedMode === "automatic" ? detectSystemTheme() : normalizedMode;
    applyTheme(resolvedTheme);
    updateThemeButtonState(resolvedTheme, normalizedMode);
    syncRadio("[data-appearance-color]", normalizedMode);
    if (persist) {
      safeWrite(STORAGE_COLOR_MODE_KEY, normalizedMode);
      safeWrite(STORAGE_THEME_KEY, resolvedTheme);
    }
    return normalizedMode;
  }

  function applyTextSize(value, persist) {
    var defaultValue = normalize(rootDefault("data-appearance-text-default", "standard"), ["small", "standard", "large"], "standard");
    var normalized = normalize(value, ["small", "standard", "large"], defaultValue);
    ROOT.setAttribute("data-reading-text", normalized);
    syncRadio("[data-appearance-text]", normalized);
    if (persist) {
      safeWrite(STORAGE_TEXT_KEY, normalized);
    }
    return normalized;
  }

  function applyWidthMode(value, persist) {
    var defaultValue = normalize(rootDefault("data-appearance-width-default", "standard"), ["standard", "wide"], "standard");
    var normalized = normalize(value, ["standard", "wide"], defaultValue);
    ROOT.setAttribute("data-reading-width", normalized);
    syncRadio("[data-appearance-width]", normalized);
    if (persist) {
      safeWrite(STORAGE_WIDTH_KEY, normalized);
    }
    return normalized;
  }

  function applyStoredPreferences() {
    var storedColorMode = safeRead(STORAGE_COLOR_MODE_KEY);
    if (!storedColorMode) {
      var legacyTheme = safeRead(STORAGE_THEME_KEY);
      if (legacyTheme === "light" || legacyTheme === "dark") {
        storedColorMode = legacyTheme;
      }
    }
    applyColorMode(storedColorMode || rootDefault("data-appearance-color-default", "automatic"), false);
    applyTextSize(safeRead(STORAGE_TEXT_KEY) || rootDefault("data-appearance-text-default", "standard"), false);
    applyWidthMode(safeRead(STORAGE_WIDTH_KEY) || rootDefault("data-appearance-width-default", "standard"), false);
  }

  function bindThemeToggle() {
    var button = document.querySelector("[data-theme-toggle]");
    if (!button) {
      return;
    }
    button.addEventListener("click", function () {
      var nextTheme = currentTheme() === "dark" ? "light" : "dark";
      applyColorMode(nextTheme, true);
    });
    updateThemeButtonState(currentTheme(), currentColorMode());
  }

  function bindAppearanceRadios() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-appearance-text]"), function (input) {
      input.addEventListener("change", function () {
        applyTextSize(input.value, true);
      });
    });

    Array.prototype.forEach.call(document.querySelectorAll("[data-appearance-width]"), function (input) {
      input.addEventListener("change", function () {
        applyWidthMode(input.value, true);
      });
    });

    Array.prototype.forEach.call(document.querySelectorAll("[data-appearance-color]"), function (input) {
      input.addEventListener("change", function () {
        applyColorMode(input.value, true);
      });
    });
  }

  function bindSystemThemeSync() {
    if (!window.matchMedia) {
      return;
    }
    var mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    var handleChange = function () {
      if (currentColorMode() === "automatic") {
        applyColorMode("automatic", false);
      }
    };
    try {
      if (typeof mediaQuery.addEventListener === "function") {
        mediaQuery.addEventListener("change", handleChange);
      } else if (typeof mediaQuery.addListener === "function") {
        mediaQuery.addListener(handleChange);
      }
    } catch (err) {
      // Ignore listener registration failures.
    }
  }

  function setAppearancePanelOpen(panel, button, isOpen, persistState) {
    if (!panel || !button) {
      return;
    }
    panel.hidden = !isOpen;
    button.setAttribute("aria-expanded", isOpen ? "true" : "false");
    var nextLabel = isOpen ? "Hide appearance settings" : "Show appearance settings";
    button.setAttribute("title", nextLabel);
    button.setAttribute("aria-label", nextLabel);
    if (persistState) {
      safeWrite(STORAGE_PANEL_COLLAPSED_KEY, isOpen ? "0" : "1");
    }
  }

  function showAppearanceToast(toast, timeoutMs) {
    if (!toast) {
      return null;
    }
    toast.hidden = false;
    return window.setTimeout(function () {
      toast.hidden = true;
    }, Math.max(1000, Number(timeoutMs) || 5000));
  }

  function initAppearanceMenu() {
    var control = document.querySelector("[data-appearance-control]");
    if (!control) {
      return;
    }
    var enabled = toBool(rootDefault("data-appearance-enabled", "true"), true);
    if (!enabled) {
      control.hidden = true;
      return;
    }

    var button = control.querySelector("[data-appearance-button]");
    var panel = control.querySelector("[data-appearance-panel]");
    var hideButton = control.querySelector("[data-appearance-hide]");
    var toast = control.querySelector("[data-appearance-toast]");
    if (!button || !panel) {
      return;
    }

    var toastMs = parseInt(rootDefault("data-appearance-toast-ms", "5000"), 10);
    if (!Number.isFinite(toastMs) || toastMs < 1000) {
      toastMs = 5000;
    }
    var defaultOpen = toBool(rootDefault("data-appearance-default-open", "false"), false);
    var storedCollapsed = safeRead(STORAGE_PANEL_COLLAPSED_KEY);
    var shouldOpen = defaultOpen;
    if (storedCollapsed === "1") {
      shouldOpen = false;
    } else if (storedCollapsed === "0") {
      shouldOpen = true;
    }
    setAppearancePanelOpen(panel, button, shouldOpen, false);

    var toastTimer = null;
    button.addEventListener("click", function () {
      if (toastTimer) {
        window.clearTimeout(toastTimer);
        toastTimer = null;
      }
      if (toast) {
        toast.hidden = true;
      }
      setAppearancePanelOpen(panel, button, panel.hidden, true);
    });

    if (hideButton) {
      hideButton.addEventListener("click", function () {
        setAppearancePanelOpen(panel, button, false, true);
        if (toastTimer) {
          window.clearTimeout(toastTimer);
          toastTimer = null;
        }
        toastTimer = showAppearanceToast(toast, toastMs);
      });
    }
  }

  applyStoredPreferences();
  bindSystemThemeSync();

  function bindInteractiveControls() {
    bindThemeToggle();
    bindAppearanceRadios();
    initAppearanceMenu();
    applyColorMode(currentColorMode(), false);
    applyTextSize(
      ROOT.getAttribute("data-reading-text") || rootDefault("data-appearance-text-default", "standard"),
      false
    );
    applyWidthMode(
      ROOT.getAttribute("data-reading-width") || rootDefault("data-appearance-width-default", "standard"),
      false
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindInteractiveControls);
  } else {
    bindInteractiveControls();
  }
})();