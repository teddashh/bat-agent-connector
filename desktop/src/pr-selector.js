import {h, t} from "./i18n.js";

// A component that fetches and shows a list of PRs
export function prSelector(api, repoInput, numInput, onSelect) {
  const container = h("div", { class: "pr-selector" });
  const stateSelect = h("select", { "aria-label": t("state") || "State", onchange: () => loadList() },
    h("option", { value: "open", selected: true }, "Open"),
    h("option", { value: "closed" }, "Closed"),
    h("option", { value: "all" }, "All")
  );
  
  const refreshBtn = h("button", { type: "button", class: "secondary", onclick: () => loadList() }, t("delivery_refresh_prs"));
  const listContainer = h("div", { class: "pr-list" });
  let currentPage = 1;

  const loadList = async (page = 1) => {
    currentPage = page;
    const repo = repoInput.value;
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
      listContainer.replaceChildren(h("p", { class: "muted" }, t("delivery_choose_pr")));
      return;
    }
    listContainer.replaceChildren(h("p", { class: "muted" }, "Loading..."));
    try {
      const state = stateSelect.value;
      const res = await api("GET", `/repositories/${repo}/pulls?state=${state}&page=${page}`);
      const pulls = res.pulls || [];
      if (pulls.length === 0) {
        listContainer.replaceChildren(h("p", { class: "muted" }, t("delivery_no_prs")));
        return;
      }
      const ul = h("ul", { class: "row-details", style: "list-style: none; padding: 0;" });
      for (const pr of pulls) {
        const li = h("li", { style: "margin-bottom: 8px;" }, 
          h("a", {
            href: "javascript:void(0)", 
            onclick: (e) => {
              e.preventDefault();
              numInput.value = pr.number;
              onSelect();
            }
          }, `#${pr.number} ${pr.title}`),
          " ", h("span", { class: "muted" }, pr.state, pr.draft ? " (draft)" : "")
        );
        ul.append(li);
      }
      const nav = h("div", { class: "actions" },
        h("button", { type: "button", class: "secondary", disabled: page <= 1, onclick: () => loadList(page - 1) }, "Previous"),
        h("button", { type: "button", class: "secondary", disabled: pulls.length < 100, onclick: () => loadList(page + 1) }, "Next")
      );
      listContainer.replaceChildren(ul, nav);
    } catch (e) {
      listContainer.replaceChildren(h("p", { class: "note warn" }, e.message || String(e)));
    }
  };

  container.append(
    h("div", { class: "filters" }, stateSelect, refreshBtn),
    listContainer
  );

  return { container, loadList };
}
