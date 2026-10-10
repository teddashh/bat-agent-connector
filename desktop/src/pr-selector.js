// A component that fetches and shows a list of PRs
export function prSelector({ api, h, t, guard, repoInput, numInput, onSelect }) {
  const container = h("div", { class: "pr-selector" });
  const stateSelect = h("select", { "aria-label": t("state") || "State", onchange: () => loadList() },
    h("option", { value: "open", selected: true }, t("pr_state_open") || "Open"),
    h("option", { value: "closed" }, t("pr_state_closed") || "Closed"),
    h("option", { value: "all" }, t("pr_state_all") || "All")
  );
  
  const searchInput = h("input", { type: "text", placeholder: t("delivery_search_prs") || "Search PRs...", oninput: () => renderList() });
  const refreshBtn = h("button", { type: "button", class: "secondary", onclick: () => loadList() }, t("delivery_refresh_prs"));
  const listContainer = h("div", { class: "pr-list" });
  
  let currentPage = 1;
  let currentGeneration = 0;
  let cachedPulls = [];
  let cachedHasMore = false;
  let loadedScope = ""; // Track what we loaded

  const renderList = (errorMsg = null, isStale = false) => {
    if (errorMsg) {
      const errEl = h("p", { class: "note warn" }, errorMsg);
      if (isStale) {
        listContainer.prepend(errEl); // Keep old list but show warning
        listContainer.classList.add("stale");
      } else {
        listContainer.replaceChildren(errEl);
      }
      return;
    }
    
    listContainer.classList.remove("stale");
    if (cachedPulls.length === 0) {
      listContainer.replaceChildren(h("p", { class: "muted" }, t("delivery_no_prs")));
      return;
    }
    
    const query = searchInput.value.toLowerCase();
    const filtered = cachedPulls.filter(pr => pr.title.toLowerCase().includes(query) || String(pr.number).includes(query));
    
    const ul = h("ul", { class: "row-details", style: "list-style: none; padding: 0;" });
    for (const pr of filtered) {
      const li = h("li", { style: "margin-bottom: 8px;" }, 
        h("button", {
          type: "button",
          class: "link-button",
          style: "background: none; border: none; padding: 0; font: inherit; cursor: pointer; text-decoration: underline; color: var(--link-color, blue);",
          onclick: () => {
            // "selecting must set exact repo as well as PR number"
            repoInput.value = loadedScope; // Assign the exact repo that we loaded
            numInput.value = pr.number;
            onSelect();
          }
        }, `#${pr.number} ${pr.title}`),
        " ", h("span", { class: "muted" }, pr.state, pr.draft ? ` (${t("pr_draft") || "draft"})` : "")
      );
      ul.append(li);
    }
    
    const nav = h("div", { class: "actions" },
      h("button", { type: "button", class: "secondary", disabled: currentPage <= 1, onclick: () => loadList(currentPage - 1) }, t("pagination_prev") || "Previous"),
      h("button", { type: "button", class: "secondary", disabled: !cachedHasMore, onclick: () => loadList(currentPage + 1) }, t("pagination_next") || "Next")
    );
    listContainer.replaceChildren(ul, nav);
  };

  const loadList = async (page = 1) => {
    const mine = ++currentGeneration;
    const repo = repoInput.value;
    const state = stateSelect.value;
    
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
      cachedPulls = [];
      renderList(t("delivery_choose_pr"));
      return;
    }
    
    if (cachedPulls.length === 0 || page !== currentPage || loadedScope !== repo) {
        listContainer.replaceChildren(h("p", { class: "muted" }, t("loading") || "Loading..."));
    } else {
        // Optimistic UI, keep existing but we show loading indicator or so
    }
    
    try {
      const res = await api("GET", `/repositories/${repo}/pulls?state=${state}&page=${page}`);
      guard(); // assertView/connection epoch check
      if (mine !== currentGeneration) return; // Ignore stale response
      
      currentPage = page;
      loadedScope = res.loaded_scope || repo;
      cachedPulls = res.pulls || [];
      cachedHasMore = !!res.has_more;
      
      renderList();
    } catch (e) {
      guard();
      if (mine !== currentGeneration) return;
      // "Error should retain stale last list with clear stale/disabledselection, don't silently replace valid state"
      const msg = e.message || String(e);
      renderList(msg, cachedPulls.length > 0);
    }
  };

  container.append(
    h("div", { class: "filters" }, searchInput, stateSelect, refreshBtn),
    listContainer
  );

  return { container, loadList };
}
