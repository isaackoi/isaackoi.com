const table = document.querySelector("[data-sortable]");

if (table) {
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  let currentKey = "";
  let direction = 1;

  table.querySelectorAll("th button").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.sortKey;
      const index = Array.from(button.closest("tr").children).indexOf(button.closest("th"));

      direction = currentKey === key ? direction * -1 : 1;
      currentKey = key;

      rows
        .slice()
        .sort((a, b) => {
          const aValue = a.children[index].dataset.value || a.children[index].textContent.trim();
          const bValue = b.children[index].dataset.value || b.children[index].textContent.trim();
          return aValue.localeCompare(bValue, undefined, { sensitivity: "base" }) * direction;
        })
        .forEach((row) => tbody.appendChild(row));
    });
  });
}
