const sortableTables = Array.from(document.querySelectorAll("table[data-sortable], table.sortable"));

const valueForCell = (cell) => {
  const raw = (cell.dataset.value || cell.textContent || "").trim();
  const numeric = Number(raw.replace(/,/g, ""));
  return Number.isFinite(numeric) && raw !== "" ? numeric : raw.toLocaleLowerCase();
};

const buildButton = (cell) => {
  const existingButton = cell.querySelector("button.sort-button");
  if (existingButton) {
    return existingButton;
  }

  const button = document.createElement("button");
  button.type = "button";
  button.className = "sort-button";
  button.innerHTML = cell.innerHTML.trim() || "Sort";
  cell.innerHTML = "";
  cell.appendChild(button);
  return button;
};

const ensureTableBody = (table) => {
  const body = table.tBodies[0];
  if (body) {
    return body;
  }

  const createdBody = document.createElement("tbody");
  const rows = Array.from(table.querySelectorAll("tr"));
  rows.slice(1).forEach((row) => createdBody.appendChild(row));
  table.appendChild(createdBody);
  return createdBody;
};

sortableTables.forEach((table) => {
  const headerRow = table.tHead?.rows[0] || table.rows[0];
  if (!headerRow) {
    return;
  }

  const tbody = ensureTableBody(table);
  let activeColumn = -1;
  let direction = 1;

  Array.from(headerRow.cells).forEach((cell, index) => {
    const button = buildButton(cell);

    button.addEventListener("click", () => {
      const rows = Array.from(tbody.rows);
      direction = activeColumn === index ? direction * -1 : 1;
      activeColumn = index;

      rows
        .sort((left, right) => {
          const leftValue = valueForCell(left.cells[index]);
          const rightValue = valueForCell(right.cells[index]);

          if (typeof leftValue === "number" && typeof rightValue === "number") {
            return (leftValue - rightValue) * direction;
          }

          return String(leftValue).localeCompare(String(rightValue), undefined, {
            numeric: true,
            sensitivity: "base",
          }) * direction;
        })
        .forEach((row) => tbody.appendChild(row));

      table.querySelectorAll(".sort-button").forEach((candidate) => {
        candidate.removeAttribute("data-sort-direction");
      });
      button.dataset.sortDirection = direction > 0 ? "asc" : "desc";
    });
  });
});
