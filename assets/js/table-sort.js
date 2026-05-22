(function () {
  function valueForCell(cell) {
    var raw = String((cell && (cell.dataset.value || cell.textContent)) || "").trim();
    var numeric = Number(raw.replace(/,/g, ""));
    return Number.isFinite(numeric) && raw !== "" ? numeric : raw.toLocaleLowerCase();
  }

  function buildButton(cell) {
    var existingButton = cell.querySelector("button.sort-button");
    if (existingButton) {
      return existingButton;
    }

    var button = document.createElement("button");
    button.type = "button";
    button.className = "sort-button";
    button.innerHTML = cell.innerHTML.trim() || "Sort";
    cell.innerHTML = "";
    cell.appendChild(button);
    return button;
  }

  function ensureTableBody(table) {
    var body = table.tBodies[0];
    if (body) {
      return body;
    }

    var createdBody = document.createElement("tbody");
    var rows = Array.from(table.querySelectorAll("tr"));
    rows.slice(1).forEach(function (row) {
      createdBody.appendChild(row);
    });
    table.appendChild(createdBody);
    return createdBody;
  }

  function ensureScrollableWrapper(table) {
    var parent = table.parentElement;
    if (!parent || parent.classList.contains("table-scroll")) {
      return;
    }
    var wrapper = document.createElement("div");
    wrapper.className = "table-scroll";
    parent.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  }

  function initSortableTable(table) {
    if (!table || table.dataset.sortEnhanced === "true") {
      return;
    }
    table.dataset.sortEnhanced = "true";
    ensureScrollableWrapper(table);

    var headerRow = (table.tHead && table.tHead.rows[0]) || table.rows[0];
    if (!headerRow) {
      return;
    }

    var tbody = ensureTableBody(table);
    var activeColumn = -1;
    var direction = 1;

    Array.from(headerRow.cells).forEach(function (cell, index) {
      var button = buildButton(cell);

      button.addEventListener("click", function () {
        var rows = Array.from(tbody.rows);
        direction = activeColumn === index ? direction * -1 : 1;
        activeColumn = index;

        rows.sort(function (left, right) {
          var leftValue = valueForCell(left.cells[index]);
          var rightValue = valueForCell(right.cells[index]);

          if (typeof leftValue === "number" && typeof rightValue === "number") {
            return (leftValue - rightValue) * direction;
          }

          return String(leftValue).localeCompare(String(rightValue), undefined, {
            numeric: true,
            sensitivity: "base"
          }) * direction;
        }).forEach(function (row) {
          tbody.appendChild(row);
        });

        table.querySelectorAll(".sort-button").forEach(function (candidate) {
          candidate.removeAttribute("data-sort-direction");
        });
        button.dataset.sortDirection = direction > 0 ? "asc" : "desc";
      });
    });
  }

  function initSortableTables() {
    var tables = document.querySelectorAll("table[data-sortable], table.sortable");
    Array.prototype.forEach.call(tables, initSortableTable);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSortableTables, { once: true });
  } else {
    initSortableTables();
  }
})();
