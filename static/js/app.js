/* Tea Smart — progressive enhancement. Every page works without this file. */
(function () {
  "use strict";

  /* --- Search page: mobile filter disclosure ----------------------------- */
  const filterToggle = document.querySelector("[data-filter-toggle]");
  const filterForm = document.querySelector("[data-filter-form]");

  if (filterToggle && filterForm) {
    const isNarrow = () => window.matchMedia("(max-width: 900px)").matches;

    const sync = () => {
      if (isNarrow()) {
        filterForm.hidden = filterToggle.getAttribute("aria-expanded") !== "true";
      } else {
        filterForm.hidden = false;
      }
    };

    filterToggle.addEventListener("click", () => {
      const open = filterToggle.getAttribute("aria-expanded") === "true";
      filterToggle.setAttribute("aria-expanded", String(!open));
      sync();
    });

    window.addEventListener("resize", sync);
    sync();
  }

  /* --- Search page: type-ahead over a long checkbox list ----------------- */
  document.querySelectorAll("[data-list-filter]").forEach((input) => {
    const list = document.getElementById(input.getAttribute("data-list-filter"));
    if (!list) return;

    input.addEventListener("input", () => {
      const needle = input.value.trim().toLowerCase();
      list.querySelectorAll("[data-list-item]").forEach((item) => {
        const checked = item.querySelector("input")?.checked;
        const match = !needle || item.getAttribute("data-list-item").includes(needle);
        item.classList.toggle("is-hidden", !match && !checked);
      });
    });
  });

  /* --- Product page: ingredient hover widget ----------------------------- */
  /* Hover and focus are handled in CSS; JS only keeps the card on screen and
     adds tap support for touch devices, where :hover never fires. */
  const ingredients = document.querySelectorAll("[data-ingredient]");

  const place = (item) => {
    const card = item.querySelector(".herb-card");
    if (!card) return;

    card.classList.remove("align-left", "align-right", "flip-down");

    const anchor = item.getBoundingClientRect();
    const width = card.offsetWidth;
    const margin = 12;

    if (anchor.left + anchor.width / 2 - width / 2 < margin) {
      card.classList.add("align-left");
    } else if (anchor.left + anchor.width / 2 + width / 2 > window.innerWidth - margin) {
      card.classList.add("align-right");
    }

    if (anchor.top - card.offsetHeight - margin < 0) {
      card.classList.add("flip-down");
    }
  };

  const closeAll = (except) => {
    ingredients.forEach((item) => {
      if (item !== except) item.classList.remove("is-open");
    });
  };

  ingredients.forEach((item) => {
    item.addEventListener("pointerenter", () => place(item));
    item.addEventListener("focus", () => place(item));

    item.addEventListener("click", (event) => {
      // Only take over on touch/pen, so mouse hover keeps its natural feel.
      if (event.pointerType === "mouse") return;
      event.preventDefault();
      const open = item.classList.contains("is-open");
      closeAll(item);
      item.classList.toggle("is-open", !open);
      if (!open) place(item);
    });

    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const open = item.classList.contains("is-open");
        closeAll(item);
        item.classList.toggle("is-open", !open);
        if (!open) place(item);
      }
      if (event.key === "Escape") item.classList.remove("is-open");
    });
  });

  if (ingredients.length) {
    document.addEventListener("click", (event) => {
      if (!event.target.closest("[data-ingredient]")) closeAll(null);
    });
    window.addEventListener("scroll", () => closeAll(null), { passive: true });
  }
})();
