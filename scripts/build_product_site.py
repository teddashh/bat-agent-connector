import argparse
from html import escape
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "site"
repo = "https://github.com/teddashh/bat-agent-connector"


def bi(en, zh, tag="span", cls=""):
    attr = f' class="{cls}"' if cls else ""
    return f'<{tag}{attr}><span class="lang-en">{en}</span><span class="lang-zh" lang="zh-Hant">{zh}</span></{tag}>'


def link(path, en, zh, cls=""):
    return f'<a href="{path}"' + (f' class="{cls}"' if cls else "") + ">" + bi(en, zh) + "</a>"


def heading(kicker, kicker_zh, en, zh, desc="", desc_zh=""):
    return (
        '<div class="section-heading">'
        + bi(kicker, kicker_zh, "p", "eyebrow")
        + bi(en, zh, "h2")
        + (bi(desc, desc_zh, "p", "lede") if desc else "")
        + "</div>"
    )


nav = "".join(
    link("#" + i, e, z)
    for i, e, z in [
        ("product", "Product", "產品"),
        ("workflow", "Workflow", "流程"),
        ("architecture", "Architecture", "架構"),
        ("windows", "Windows Fleet", "Windows Fleet"),
        ("start", "Get started", "開始使用"),
        ("docs", "Docs", "文件"),
    ]
)
header = f'''<a class="skip-link" href="#main">{bi("Skip to content", "跳到主要內容")}</a>
<header class="site-header"><div class="header-inner">
<a class="brand" href="#top"><img src="logo.svg" width="32" height="32" alt=""><span>Better Agent<span class="brand-sub">Dashboard</span></span></a>
<button class="menu-button" type="button" aria-expanded="false" aria-controls="site-navigation">{bi("Menu", "選單")}</button>
<nav class="site-nav" id="site-navigation" aria-label="Navigation / 導覽">{nav}
<div class="language-switch" role="group" aria-label="Language / 語言"><button type="button" data-language="en" aria-pressed="true">EN</button><button type="button" data-language="zh" aria-pressed="false">繁中</button></div>
<a href="{repo}" class="source-link">GitHub <span aria-hidden="true">↗</span></a></nav></div></header>'''
parts = [header, '<main id="main">']
parts.append('<section class="hero section" id="top"><div class="hero-grid"><div>')
parts.append(bi("BAT connections, agents and delivery", "BAT 連線、Agent 與交付", "p", "eyebrow"))
parts.append(bi("Many agents.<br>One path to delivery.", "多個 Agent，<br>一條交付流程。", "h1"))
parts.append(
    bi(
        "Connect the fleet, dispatch agents and follow their results. Windows manages local connections and BAT startup; the shared Web and Tauri Dashboard follows work on your BAT hosts.",
        "連起主機、派出 Agent、追到成果。Windows 管理本機連線與 BAT 啟動，Web／Tauri 共用 Dashboard 追蹤 BAT 主機上的工作；你照常在 BAT 裡 coding。",
        "p",
        "hero-description",
    )
)
parts.append(
    '<div class="actions">'
    + link("#product", "Explore the Dashboard", "看看 Dashboard", "button primary")
    + link("#start", "Installation &amp; first use", "安裝與首次使用", "text-link")
    + "</div>"
)
parts.append(
    bi(
        "Open source · Web + Tauri · English / 繁體中文",
        "開源 · Web + Tauri · English / 繁體中文",
        "p",
        "hero-meta",
    )
)
parts.append('</div><aside class="hero-aside" aria-label="Product focus / 產品重點">')
for n, en, zh, desc, dz in [
    (
        "01",
        "Connect & start",
        "連線與啟動",
        "Windows Fleet, SSH routes and selected BAT profiles.",
        "Windows Fleet、SSH 路由與選定的 BAT profiles。",
    ),
    (
        "02",
        "Give work a destination",
        "每份工作都有去向",
        "Project → host → session → result.",
        "專案 → 主機 → 工作階段 → 成果。",
    ),
    (
        "03",
        "Follow through to delivery",
        "追到實際交付",
        "A commit, a PR, a deployed version and a history.",
        "固定 commit、PR、部署版本與保留下來的歷史。",
    ),
]:
    parts.append(
        f'<div class="focus-row"><span class="index">{n}</span><div>'
        + bi(en, zh, "h2")
        + bi(desc, dz, "p")
        + "</div></div>"
    )
parts.append(
    '</aside></div><div class="release-note">'
    + bi("Development preview", "開發預覽", "strong")
    + bi(
        "The shared Dashboard is available for configured trials. Automatic environment setup in the desktop installer is still in development.",
        "共用 Dashboard 可在已配置環境試用；桌面安裝包自動建立環境的流程仍在開發。",
    )
    + link("#status", "See readiness", "查看交付現況")
    + "</div></section>"
)
parts.append(
    '<section class="section" id="product">'
    + heading(
        "Inside the product",
        "介面導覽",
        "See what needs your attention.",
        "看清狀態，再決定下一步。",
        "Read the situation before you act. Keep questions, completion review and operation recovery in their own lanes.",
        "先理解現況再操作。待回答、完成待審與操作復原各有明確的位置。",
    )
)
parts.append(
    '<div class="tour-controls" role="group" aria-label="Screenshot view / 介面展示">'
    + bi("View:", "檢視：", "span", "tour-label")
)
for k, en, zh in [
    ("attention", "Attention & review", "待處理與審閱"),
    ("dispatch", "Project dispatch", "專案派工"),
]:
    parts.append(
        f'<button type="button" data-view="{k}" aria-pressed="'
        + ("true" if k == "attention" else "false")
        + '" aria-controls="view-'
        + k
        + '">'
        + bi(en, zh)
        + "</button>"
    )
parts.append("</div>")
for key, en, zh in [
    (
        "attention",
        "Pending replies, review decisions and uncertain operations appear separately.",
        "待回答、審閱決策與結果未知的操作分開顯示。",
    ),
    (
        "dispatch",
        "Choose an explicit project destination and review the published source before starting work.",
        "先選專案的明確目的地，檢視已發布來源，再開始工作。",
    ),
]:
    parts.append(f'<figure class="product-shot" id="view-{key}">')
    for lang, alt in [("en", en), ("zh", zh)]:
        parts.append(
            f'<a class="lang-{lang} image-link" href="images/{key}-{lang}.png" aria-label="{escape(alt)}"><img src="images/{key}-{lang}.png" width="1240" height="820" loading="lazy" alt="{escape(alt)}"></a>'
        )
    parts.append(
        "<figcaption>"
        + bi(en, zh)
        + bi(
            "Actual UI · synthetic demo data · click image for full size",
            "實際介面 · 合成展示資料 · 點圖看原尺寸",
            "span",
            "caption-meta",
        )
        + "</figcaption></figure>"
    )
parts.append('<div class="principles">')
for en, zh, d, dz in [
    (
        "Activity is not completion",
        "活動不等於完成",
        "No output may mean waiting, idle or missing observations.",
        "沒有輸出可能是等待、閒置，或缺少觀測。",
    ),
    (
        "Review is not deployment",
        "審閱不等於部署",
        "Accepting work, merging a PR and verifying a deployment have separate receipts.",
        "接受成果、合併 PR 和驗證部署，各有自己的回執。",
    ),
    (
        "Reopen the same work",
        "重開後找回原工作",
        "Saved operation identities let you recover without guessing or dispatching twice.",
        "保存操作身分，先查回結果，避免猜測或重複派工。",
    ),
]:
    parts.append("<div>" + bi(en, zh, "h3") + bi(d, dz, "p") + "</div>")
parts.append("</div></section>")
parts.append(
    '<section class="section" id="workflow">'
    + heading(
        "From request to result",
        "從需求到成果",
        "Every step stays connected.",
        "每一步，都接得回原來的工作。",
        "Keep the intent, execution and delivery together. Work stays on the selected BAT host, whichever client you use.",
        "需求、執行與交付保留關聯。無論從哪個入口操作，工作留在你選定的 BAT 主機。",
    )
    + '<ol class="workflow">'
)
steps = [
    (
        "Organize",
        "整理專案",
        "Record the original request, acceptance criteria and explicitly associated repository.",
        "保留原始需求、驗收條件，明確連結 repository。",
    ),
    (
        "Dispatch",
        "派出工作",
        "Choose the host and workspace. Review a fixed branch commit, then add instructions, a model and exact attachments.",
        "選主機與工作區，檢視分支的固定 commit，加入指示、模型與精確附件版本。",
    ),
    (
        "Observe",
        "跟進狀況",
        "Read the conversation, answer a pending question and find the session or worktree from its project.",
        "讀取對話、回答待處理問題，從原專案找回 session 與 worktree。",
    ),
    (
        "Integrate",
        "整合成果",
        "Review fixed candidate commits in a separate integration workspace and bring selected results into one PR.",
        "在獨立整合工作區檢視固定候選 commit，把選定成果送進同一個 PR。",
    ),
    (
        "Deliver",
        "確認交付",
        "Merge the reviewed PR scope. A configured deployment recipe checks the actual version and runtime evidence.",
        "合併已檢視的 PR 範圍；有部署 recipe 時，核對實際版本與 runtime 證據。",
    ),
    (
        "Retain & clean up",
        "保留與整理",
        "Preview eligible cleanup, see why resources are retained and keep their history available.",
        "先預覽可整理的資源、了解保留原因，整理後仍可查歷史。",
    ),
]
for i, (en, zh, d, dz) in enumerate(steps, 1):
    parts.append(
        f'<li><span class="step-number">0{i}</span><div>' + bi(en, zh, "h3") + bi(d, dz, "p") + "</div></li>"
    )
parts.append(
    "</ol>"
    + bi(
        "Across hosts, code travels through an explicitly bound GitHub repository and a published commit. Human checkouts and unpublished workspaces are not silently moved.",
        "跨主機程式碼透過明確綁定的 GitHub repository 與已發布 commit 取得；不默默搬動人的 checkout 或未發布工作區。",
        "p",
        "section-note",
    )
    + "</section>"
)
parts.append(
    '<section class="section" id="features">'
    + heading(
        "The working surface",
        "日常工作所需",
        "More than a list of sessions.",
        "把工作整理起來，不只列出 sessions。",
    )
    + '<div class="feature-list">'
)
features = [
    (
        "Projects & work items",
        "專案與工作項目",
        "Hierarchy, pins, archive, original requests and acceptance criteria keep long-running work understandable.",
        "以階層、釘選、封存、原始需求和驗收條件，整理持續進行的工作。",
        "work-items.md",
    ),
    (
        "Conversation & control",
        "對話與控制",
        "Readable code and tables, copying, preserved reading position and authorized session actions.",
        "閱讀程式碼與表格、複製原文、保留閱讀位置，並執行已授權的 session 操作。",
        "shared-frontend.md",
    ),
    (
        "Artifacts & lineage",
        "附件與來源",
        "Capture and review immutable revisions; keep the operation or task that produced each result.",
        "擷取、審閱不可變版本，保留每份成果的 operation 或 task 來源。",
        "artifacts.md",
    ),
    (
        "Delivery & environments",
        "交付與環境",
        "Fixed integration previews, PR actions, deployment history, version checks and supported rollback recipes.",
        "固定整合預覽、PR 操作、部署歷史、版本驗證與已支援的 rollback recipe。",
        "delivery.md",
    ),
    (
        "History & recovery",
        "歷史與復原",
        "Stable IDs, resource relations and saved receipts retain context across refreshes and disconnects.",
        "以穩定 ID、資源關聯及回執，在刷新與斷線後保留脈絡。",
        "observation.md",
    ),
    (
        "Agent access",
        "Agent 存取",
        "CLI and MCP share central permissions. Hermes and Grokbot use adapters from the canonical skill.",
        "CLI 與 MCP 共用中央權限；Hermes／Grokbot 使用由共用 skill 產生的配接。",
        "../agent-skills.md",
    ),
]
for en, zh, d, dz, path in features:
    url = repo + "/blob/main/docs/" + ("agent-skills.md" if path.startswith("../") else "design/" + path)
    parts.append(
        "<article>"
        + bi(en, zh, "h3")
        + bi(d, dz, "p")
        + link(url, "Read the guide →", "閱讀說明 →")
        + "</article>"
    )
parts.append("</div></section>")
parts.append(
    '<section class="section" id="architecture">'
    + heading(
        "Connections, control and execution",
        "連線、中央控制與執行",
        "Fleet connects. Connector coordinates. BAT runs the work.",
        "Fleet 管連線，Connector 管派工，BAT 執行工作。",
        "Windows startup and native resources remain part of the product. Projects organize work across this system; they do not replace it.",
        "Windows 啟動與原生資源一直是產品的一部分。專案管理把這些工作整理起來，並沒有取代底下的系統。",
    )
)
parts.append(
    '<figure class="architecture"><div class="native-lane">'
    + bi("Windows Tauri → native Fleet", "Windows Tauri → 原生 Fleet", "h3")
    + bi(
        "Owns selected SSH tunnels, route/readiness checks, BAT profile windows and sign-in startup. Rust or the existing PowerShell backend; one proven owner. Provides connection paths to BAT / central and optional configured central bootstrap.",
        "管理選定 SSH tunnels、路由／就緒檢查、BAT profile 視窗與登入啟動。Rust 或既有 PowerShell backend 共用唯一 owner 規則；提供 BAT／中央連線，並支援已配置的中央 bootstrap。",
        "p",
    )
    + '</div><div class="client-row"><div>'
    + bi("Windows Tauri", "Windows Tauri", "strong")
    + bi("Dashboard + native Fleet above", "Dashboard ＋ 上方原生 Fleet", "small")
    + "</div><div>"
    + bi("Web / Mac Tauri", "Web／Mac Tauri", "strong")
    + bi("Same Dashboard; platform-specific native support", "同一 Dashboard；原生能力依平台提供", "small")
    + "</div><div>"
    + bi("Hermes / Grokbot", "Hermes／Grokbot", "strong")
    + bi("Scoped MCP / CLI entry", "有獨立權限的 MCP／CLI 入口", "small")
    + '</div></div><div class="central-node">'
    + bi("Python Connector / Task Service", "Python Connector／Task Service", "strong")
    + bi("Dispatch · identity · permissions · operations · task journal", "派工 · 身分 · 權限 · operations · task journal", "span")
    + '</div>'
    + bi("↓ bat-remote/v2 and governed operations ↓", "↓ bat-remote/v2 與受控操作 ↓", "p", "flow-label")
    + bi("BAT hosts / workspaces", "BAT 主機／workspaces", "h3", "bat-node")
    + '<div class="resource-row"><div>'
    + bi("Human sessions & worktrees", "人工 sessions／worktrees", "strong")
    + bi("You code through BAT desktop / mobile. Connector reads; continuation creates separate managed resources.", "你透過 BAT desktop／mobile coding。Connector 保持唯讀；接續時建立另一份 managed 資源。", "p")
    + "</div><div>"
    + bi("Agent-owned sessions & worktrees", "Agent 自有 sessions／worktrees", "strong")
    + bi("Central dispatches work into the selected host. Fixed results retain their session, worktree and operation links.", "中央派工到選定主機；固定成果保留 session、worktree 與 operation 關聯。", "p")
    + '</div></div><div class="delivery-node">'
    + bi("Managed results → GitHub PR → merge / deploy → reviewed cleanup", "Managed 成果 → GitHub PR → merge／deploy → 審閱後整理", "strong")
    + bi("Central governs each delivery step and retains receipts.", "每個交付步驟由中央管理並保存回執。", "p")
    + '</div><figcaption>'
    + bi(
        "Fleet handles local connectivity; Python remains the sole business authority. BAT profile launch opens desktop windows; mobile remains an independent BAT client. Project Hub contributes interaction references, with no runtime, backend or importer dependency.",
        "Fleet 負責本機連線，Python 仍是唯一中央業務後端。BAT profile 啟動開啟桌面視窗，mobile 是另一個 BAT client。Project Hub 僅供互動參考，沒有 runtime、後端或 importer 依賴。",
    )
    + "</figcaption></figure>"
)
parts.append(
    '<div class="two-column"><div>'
    + bi("One shared Dashboard.", "共用一份 Dashboard。", "h3")
    + bi(
        "Web and Tauri use desktop/src and the same central state. Windows-native Fleet stays on Windows; Mac Dashboard support is not a Fleet port. Drafts and conversation position remain local to each client.",
        "Web 與 Tauri 使用 desktop/src 及同一中央資料。Windows 原生 Fleet 保留在 Windows；支援 Mac Dashboard 不等於 Fleet 已移植。草稿與對話位置仍各入口獨立保存。",
        "p",
    )
    + "</div><div>"
    + bi("Keep the existing central identity.", "保留既有中央身分與工作。", "h3")
    + bi(
        "Today's Windows Fleet can reach a configured Linux central. Future managed installation must prepare the full environment while preserving ownership and history; a disconnected client must never invent a replacement central.",
        "現有 Windows Fleet 可連接已配置的 Linux 中央。完整自動安裝仍須補齊，並保留 ownership 與歷史；client 斷線不能自行另造一套中央。",
        "p",
    )
    + "</div></div></section>"
)
parts.append(
    '<section class="section" id="windows">'
    + heading(
        "Windows Fleet & resources",
        "Windows Fleet 與資源",
        "Choose what connects. Choose what opens.",
        "選要連的主機，選要開的視窗。",
        "These native controls are integrated today for configured Windows installations. Full automatic environment provisioning and live Fleet acceptance are separate remaining work.",
        "以下原生控制已整合，可用於已配置的 Windows 環境；完整自動建立環境與 Fleet 實機驗收，是另外仍須完成的工作。",
    )
    + '<div class="feature-list">'
)
for en, zh, desc, dz, path in [
    ("Connections & route recovery", "連線與路由復原",
     "Selected SSH tunnels, Tailscale status, configured route fallbacks and bounded recovery. Readiness checks TLS / BAT / central, not just an open port.",
     "選定 SSH tunnels、Tailscale 狀態、已配置的備援路由與有次數上限的復原；就緒檢查涵蓋 TLS／BAT／中央，不只看 port。", "fleet-routes.md"),
    ("BAT windows & Windows sign-in", "BAT 視窗與 Windows 登入",
     "Choose connections, BAT profiles and Dashboard independently. Preview prerequisites, keep the login picker or use saved launch choices.",
     "背景連線、BAT profiles 與 Dashboard 獨立選擇；預覽必要連線，保留登入選擇器或使用已保存的啟動選項。", "desktop-fleet-native.md"),
    ("Rust / PowerShell ownership", "Rust／PowerShell ownership",
     "Rust is wired into the native runtime. Legacy configuration defaults to PowerShell; migration proves the old owner stopped before the replacement starts.",
     "Rust 已接入原生 runtime；舊設定預設沿用 PowerShell。遷移須先證明舊 owner 已停止，再啟新 owner。", "fleet-migration.md"),
    ("Tailscale & central startup", "Tailscale 與中央啟動",
     "Open the installed Tailscale app for sign-in. A separately configured fixed SSH bootstrap recipe can query / start the selected central service.",
     "可開啟已安裝的 Tailscale 程式完成登入；另以已配置的固定 SSH bootstrap recipe 查詢／啟動指定中央服務。", "fleet-bootstrap.md"),
]:
    parts.append("<article>" + bi(en, zh, "h3") + bi(desc, dz, "p")
                 + link(repo + "/blob/main/docs/design/" + path, "Implementation guide →", "實作說明 →") + "</article>")
parts.append(
    '</div><div class="actions">'
    + link(repo + "/blob/main/docs/windows.md", "Windows guide & resources", "Windows 使用與資源", "button secondary lang-en")
    + link(repo + "/blob/main/docs/windows.zh-TW.md", "Windows guide & resources", "Windows 使用與資源", "button secondary lang-zh")
    + link(repo + "/actions/workflows/desktop.yml", "NSIS validation packages →", "NSIS 驗證安裝包 →", "text-link")
    + link(repo + "/blob/main/desktop/fleet.example.json", "Fleet configuration example →", "Fleet 設定範例 →", "text-link")
    + "</div>"
    + bi("Credential Manager, native files and tray controls also remain. No private inventory or host configuration is published here.",
         "Credential Manager、原生檔案與系統匣控制也保留；這裡不公開私人 inventory 或主機設定。", "p", "section-note")
    + "</section>"
)
parts.append(
    '<section class="installation-band" id="start"><div class="section">'
    + heading(
        "The installation we are building",
        "正在完成的安裝體驗",
        "Install. Connect. Open Dashboard.",
        "安裝、連接，打開就能管理。",
        "The desktop package should prepare the environment. You should not have to install Python or understand an API actor before using the product.",
        "桌面包應替你準備好環境，不該要求你先裝 Python，或理解 API actor 才能使用。",
    )
    + '<ol class="install-steps">'
)
for en, zh, d, dz in [
    (
        "Install the package",
        "安裝桌面包",
        "A matching runtime, private data and personal identity, managed by the application.",
        "由程式管理相符 runtime、私人資料與個人身分。",
    ),
    (
        "Connect your environment",
        "接上你的環境",
        "Guided BAT access and GitHub authorization, with clear host and workspace choices.",
        "引導完成 BAT 存取與 GitHub 授權，明確選主機和工作區。",
    ),
    (
        "Keep it running",
        "讓它持續運作",
        "A background Connector that reconnects, with one click from the tray / menu bar to open the Web Dashboard.",
        "Connector 背景常駐並自動重連；從系統匣／選單列點一下開 Web Dashboard。",
    ),
]:
    parts.append("<li>" + bi(en, zh, "h3") + bi(d, dz, "p") + "</li>")
parts.append(
    '</ol><div class="install-current">'
    + bi("Available today: configured trials", "目前可用：已配置環境試用", "h3")
    + bi(
        "The current installers contain the desktop client, not the complete automatic setup above. An operator can prepare central for a supervised trial. Joining an existing central remains an advanced path.",
        "目前安裝包提供桌面 client，尚未完成上述自動設定。操作者可先準備中央進行有人監督的試用；加入既有中央保留為進階路徑。",
        "p",
    )
    + '<div class="actions">'
    + link(
        repo + "/blob/main/docs/getting-started.md",
        "Read the trial setup guide",
        "閱讀開發試用指南",
        "button light lang-en",
    )
    + link(
        repo + "/blob/main/docs/getting-started.zh-TW.md",
        "Read the trial setup guide",
        "閱讀開發試用指南",
        "button light lang-zh",
    )
    + link(
        repo + "/blob/main/docs/design/managed-installation.md",
        "Managed installation requirements →",
        "自動安裝的交付要求 →",
        "text-link",
    )
    + "</div></div></div></section>"
)
parts.append(
    '<section class="section" id="platforms">'
    + heading(
        "Choose your entry point",
        "選擇使用入口",
        "Windows. Mac. Your browser.",
        "Windows、Mac，或你的瀏覽器。",
        "Desktop validation packages and central platform support are different things.",
        "桌面驗證包與中央服務的平台支援，需要分開看。",
    )
    + '<div class="table-wrap" role="region" aria-label="Platform support / 平台支援" tabindex="0"><table><thead><tr>'
    + "".join(
        bi(e, z, "th")
        for e, z in [("Entry", "入口"), ("Available", "已有內容"), ("Current boundary", "目前界線")]
    )
    + "</tr></thead><tbody>"
)
platforms = [
    (
        "Web",
        "Web",
        "Responsive shared Dashboard",
        "共用響應式 Dashboard",
        "A configured central service and trusted access path.",
        "需要已配置的中央與可信連線路徑。",
    ),
    (
        "Windows x64",
        "Windows x64",
        "NSIS; Credential Manager; native Fleet, BAT profile and sign-in controls",
        "NSIS、Credential Manager、原生 Fleet／BAT profile／登入控制",
        "Unsigned; automatic local central provisioning is not included yet.",
        "尚未正式簽署；未包含本機中央自動建立。",
    ),
    (
        "Mac Apple Silicon / Intel",
        "Mac Apple Silicon／Intel",
        "DMGs, native WebView and Keychain checks",
        "DMG、原生 WebView 與 Keychain 驗證",
        "Ad-hoc signing; formal notarization / updates remain. No Windows Fleet parity claim.",
        "目前 ad-hoc 簽署；正式公證／更新待完成，不宣稱 Windows Fleet 同等支援。",
    ),
    (
        "Linux",
        "Linux",
        "Debian validation package",
        "Debian 驗證包",
        "Native credential source is currently memory-only.",
        "原生憑證目前只支援記憶體來源。",
    ),
    (
        "Central service",
        "中央服務",
        "Python 3.10–3.13 tests on Linux",
        "Linux 上 Python 3.10–3.13 測試",
        "POSIX implementation. Windows central is not implemented; Mac client tests do not establish Mac central acceptance.",
        "依賴 POSIX；Windows 中央未實作，Mac client 測試不代表 Mac 中央驗收。",
    ),
]
for e, z, a, az, c, cz in platforms:
    parts.append("<tr>" + bi(e, z, "th") + bi(a, az, "td") + bi(c, cz, "td") + "</tr>")
parts.append(
    '</tbody></table></div><div class="actions">'
    + link(
        repo + "/actions/workflows/desktop.yml",
        "Find validation packages",
        "查看驗證安裝包",
        "button secondary",
    )
    + link(repo + "/releases", "Release history →", "正式發行紀錄 →", "text-link")
    + "</div>"
    + bi(
        "Packages are GitHub Actions artifacts: sign-in may be required and downloads expire. They are not a stable signed release / update channel. The setup guide explains how to identify the correct package and commit.",
        "目前套件是 GitHub Actions artifacts，可能需要登入且下載會到期，不是穩定的簽章發行／更新通道。指南說明如何核對套件與 commit。",
        "p",
        "section-note",
    )
    + "</section>"
)
parts.append(
    '<section class="section" id="decisions">'
    + heading(
        "Trust the information",
        "讓資訊值得信任",
        "Control follows ownership and evidence.",
        "依據歸屬與證據，決定能做什麼。",
    )
    + '<div class="two-column">'
)
for en, zh, d, dz in [
    (
        "Your own work stays yours",
        "人的工作保持唯讀",
        "Connector treats human-created sessions and worktrees as read-only. Continuation uses new managed resources; unknown ownership needs creation evidence.",
        "Connector 對人工 session 和 worktree 保持唯讀；接續使用新的 managed 資源，unknown 歸屬須有建立證據。",
    ),
    (
        "Every client has its own authority",
        "每個入口都有明確權限",
        "Host gates and API scopes both apply. MCP, CLI and Dashboard share central actions, version checks and audit records.",
        "Host 開關與 API scopes 同時生效；MCP、CLI、Dashboard 共用中央操作、版本檢查及稽核。",
    ),
    (
        "Lost replies keep their history",
        "回覆遺失，原操作仍在",
        "A timeout is not proof that nothing happened. Recover the original operation instead of clearing reservations or repeating an uncertain write.",
        "逾時不表示什麼都沒發生。查回原操作，不清掉 reservation 或重送結果未知的寫入。",
    ),
    (
        "Host isolation is a separate layer",
        "主機隔離是另一層保護",
        "Connector policy does not sandbox an agent process. Unattended use also needs verified host accounts, directory protection and confinement.",
        "Connector 政策不等於 Agent process 的 sandbox；無人值守還需驗證主機帳號、目錄保護與 confinement。",
    ),
]:
    parts.append("<article>" + bi(en, zh, "h3") + bi(d, dz, "p") + "</article>")
parts.append(
    "</div>"
    + link(repo + "/blob/main/SECURITY.md", "Read the security model →", "閱讀安全模型 →", "text-link")
    + "</section>"
)
parts.append(
    '<section class="section" id="status">'
    + heading(
        "Readiness, with evidence",
        "交付現況與證據",
        "Useful today. Clear about what remains.",
        "可以開始試用，也看得清還缺什麼。",
        "Baseline: 10 October 2026 · product source 15b2048 / PR #74.",
        "基準：2026 年 10 月 10 日 · 產品來源 15b2048／PR #74。",
    )
    + '<dl class="readiness">'
)
for label, lz, en, zh in [
    (
        "Implemented",
        "已實作",
        "Shared Web / Tauri workflows, project dispatch, managed resource controls, result lineage, PR integration, configured delivery and reviewed cleanup.",
        "共用 Web／Tauri 流程、專案派工、managed 資源控制、成果來源、PR 整合、已配置交付與審閱後整理。",
    ),
    (
        "Validated in controlled environments",
        "已在受控環境驗證",
        "Python 3.10–3.13 CI and desktop packages on Windows, both Mac architectures and Linux. Installed fixtures use loopback services and synthetic data; they do not prove a user’s full working day.",
        "Python 3.10–3.13 CI，以及 Windows、兩種 Mac、Linux 桌面包。安裝 fixture 使用 loopback 與合成資料，不等於使用者完整工作日驗收。",
    ),
    (
        "Still to deliver",
        "仍須交付",
        "Automatic managed installation; signed releases and updates; full unknown-ACK adjudication for native BAT worktree.merge; live startup-to-deploy acceptance on the selected hosts.",
        "自動 managed 安裝、正式簽署發行／更新、原生 BAT worktree.merge 的完整 unknown-ACK 裁決，以及指定主機從啟動到部署的實際驗收。",
    ),
]:
    parts.append("<div>" + bi(label, lz, "dt") + bi(en, zh, "dd") + "</div>")
parts.append(
    '</dl><div class="evidence-links">'
    + link(repo + "/actions/runs/38032723049", "Python candidate checks ↗", "Python 候選檢查 ↗")
    + link(repo + "/actions/runs/38032723037", "Native package evidence ↗", "原生套件證據 ↗")
    + link(repo + "/blob/main/docs/product/acceptance-v2.md", "Acceptance matrix ↗", "驗收矩陣 ↗")
    + "</div></section>"
)
parts.append(
    '<section class="section" id="docs">'
    + heading(
        "Read at the right depth",
        "依需要深入",
        "A guide for each part of the job.",
        "每一段工作，都有對應說明。",
    )
    + '<div class="doc-list">'
)
docs = [
    (
        "W",
        "Windows Fleet & resources",
        "Windows Fleet 與資源",
        "Connections, BAT profiles, login, Tailscale, backend migration and native resources.",
        "連線、BAT profiles、登入、Tailscale、backend 遷移與原生資源。",
        "docs/windows.md",
        "docs/windows.zh-TW.md",
    ),
    (
        "01",
        "Installation & first use",
        "安裝與首次使用",
        "Trial paths, credentials, desktop connection and troubleshooting.",
        "試用方式、憑證、桌面連線與排錯。",
        "docs/getting-started.md",
        "docs/getting-started.zh-TW.md",
    ),
    (
        "02",
        "Product & architecture",
        "產品與架構",
        "Shared decisions, Web / Tauri and the managed installation requirement.",
        "共用決策、Web／Tauri 與 managed 安裝要求。",
        "docs/product/realignment-v2.md",
        None,
    ),
    (
        "03",
        "Dispatch & results",
        "派工與成果",
        "Published commits, destinations, attachments and operation recovery.",
        "已發布 commit、目的地、附件及操作復原。",
        "docs/design/repository-sync.md",
        None,
    ),
    (
        "04",
        "PR & deployment",
        "PR 與部署",
        "Integration previews, merge scope, deployed versions and rollback limits.",
        "整合預覽、merge 範圍、部署版本與 rollback 限制。",
        "docs/design/delivery.md",
        None,
    ),
    (
        "05",
        "Agent integration",
        "Agent 整合",
        "Canonical skills and matching Hermes / Grokbot adapters.",
        "共用 skills 與同版 Hermes／Grokbot 配接。",
        "docs/agent-skills.md",
        None,
    ),
    (
        "06",
        "Source & contribution",
        "原始碼與參與開發",
        "Build the shared frontend, run checks and understand the repository.",
        "建置共用前端、執行檢查及了解 repo。",
        "README.md",
        "README.zh-TW.md",
    ),
]
for n, e, z, d, dz, path, zpath in docs:
    parts.append('<div><span class="index">' + n + "</span><div>")
    if zpath:
        parts.append(
            f'<a class="lang-en" href="{repo}/blob/main/{path}">{e} ↗</a><a class="lang-zh" lang="zh-Hant" href="{repo}/blob/main/{zpath}">{z} ↗</a>'
        )
    else:
        parts.append(link(repo + "/blob/main/" + path, e + " ↗", z + " ↗"))
    parts.append(bi(d, dz, "p") + "</div></div>")
parts.append("</div></section>")
parts.append(
    '<section class="section faq" id="faq">'
    + heading("A few practical questions", "常見問題", "Before you start.", "開始前，先說清楚。")
)
faqs = [
    (
        "Do I need both BAT and Dashboard on this computer?",
        "這台電腦必須同時裝 BAT 嗎？",
        "No. Dashboard can manage work on a configured remote BAT host. BAT remains where the coding sessions run. Local BAT launch and Fleet controls are optional platform capabilities.",
        "不必。Dashboard 可管理已配置遠端 BAT 主機的工作，coding sessions 留在 BAT。開本機 BAT 與 Fleet 控制是依平台提供的選用能力。",
    ),
    (
        "Does the current installer set everything up?",
        "現在安裝包會把環境全部建好嗎？",
        "Not yet. That is the required normal experience, including background service and one-click browser access. Current validation packages still need an operator-configured central service and identity.",
        "還不會。包含背景服務與一鍵開網頁的完整安裝，是正式產品要求；現有驗證包仍需操作者先配置中央與身分。",
    ),
    (
        "Can Web and Tauri stay open together?",
        "Web 和 Tauri 可以一起開著嗎？",
        "Yes. They use the same central state and frontend source. Local drafts are independent; native credentials, Fleet and window controls are platform-specific.",
        "可以。共用中央狀態與前端來源；草稿各自保存，原生憑證、Fleet 和視窗控制依平台提供。",
    ),
    (
        "Will installing Dashboard give agents access to my own checkout?",
        "裝上 Dashboard 就會讓 Agent 改我的 checkout 嗎？",
        "Connector operations keep human resources read-only and use managed work for agents. OS-level access is a separate host-account and confinement concern; the Dashboard is not itself an OS sandbox.",
        "Connector 操作對人工資源唯讀，Agent 使用 managed 工作區。OS 層的存取另由主機帳號與 confinement 決定，Dashboard 本身不是 OS sandbox。",
    ),
    (
        "Is this ready to run unattended all day?",
        "可以整天放著無人值守了嗎？",
        "The current recommendation is a supervised trial in a configured environment. Full host startup, interruption recovery, delivery and cleanup still need acceptance on the intended real setup.",
        "目前建議在已配置環境進行有人監督的試用；主機啟動、中斷恢復、交付與整理，仍需在預定的真實環境完整驗收。",
    ),
    (
        "Is this an official BAT product?",
        "這是 BAT 官方產品嗎？",
        "No. This is an unofficial MIT-licensed companion. Better Agent Terminal is by TonyQ and contributors. Project Hub informs selected UI patterns; no Hub importer or runtime dependency is included.",
        "不是。這是 MIT 授權的非官方 companion；BAT 由 TonyQ 與貢獻者開發。部分 UI 參考 Project Hub，沒有 Hub importer 或 runtime 依賴。",
    ),
]
for q, qz, a, az in faqs:
    parts.append("<details><summary>" + bi(q, qz) + "</summary>" + bi(a, az, "p") + "</details>")
parts.append("</section></main>")
parts.append(
    '<footer class="site-footer"><div class="section footer-inner"><div><a class="brand" href="#top"><img src="logo.svg" width="32" height="32" alt=""><span>Better Agent Dashboard</span></a>'
    + bi(
        "Built on bat-agent-connector. An unofficial companion to Better Agent Terminal.",
        "由 bat-agent-connector 提供中央服務，Better Agent Terminal 的非官方 companion。",
        "p",
    )
    + '</div><div class="footer-links">'
    + link(repo, "Source", "原始碼")
    + link("https://github.com/tony1223/better-agent-terminal", "BAT by TonyQ", "BAT／TonyQ")
    + link(repo + "/blob/main/LICENSE", "MIT license", "MIT 授權")
    + link("https://teddashh.github.io/", "More from Ted Huang", "Ted Huang 的其他專案")
    + "</div></div></footer>"
)
title = "Better Agent Dashboard · From agent work to reviewed delivery"
zt = "Better Agent Dashboard · 從 Agent 工作到成果交付"
desc = "Windows Fleet connects and starts BAT; Python Connector coordinates agents. Manage hosts, sessions, worktrees and GitHub delivery through the shared Web and Tauri Dashboard."
zd = "Windows Fleet 管理連線與 BAT 啟動，Python Connector 負責 Agent 派工；Web／Tauri 共用 Dashboard 追蹤主機、sessions、worktrees 與 GitHub 交付。"
head = f'''<!doctype html>
<!-- Generated by scripts/build_product_site.py. Edit the bilingual content there; see site/README.md. -->
<html lang="en" data-lang="en" data-title-en="{title}" data-title-zh="{zt}" data-desc-en="{desc}" data-desc-zh="{zd}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="theme-color" content="#eff2f6">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://teddashh.github.io/bat-agent-connector/">
<link rel="alternate" hreflang="en" href="https://teddashh.github.io/bat-agent-connector/">
<link rel="alternate" hreflang="zh-Hant" href="https://teddashh.github.io/bat-agent-connector/?lang=zh-TW">
<link rel="alternate" hreflang="x-default" href="https://teddashh.github.io/bat-agent-connector/">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://teddashh.github.io/bat-agent-connector/">
<meta property="og:image" content="https://teddashh.github.io/bat-agent-connector/images/attention-en.png">
<meta property="og:image:alt" content="Actual Dashboard UI with synthetic demonstration data">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="styles.css">
<script src="lang.js"></script>
<script src="app.js" defer></script>
</head>
<body>
'''
output = head + "\n".join(parts) + "\n</body>\n</html>\n"
parser = argparse.ArgumentParser(description="Build the bilingual static product website")
parser.add_argument("--check", action="store_true", help="refuse generated index drift")
args = parser.parse_args()
if args.check:
    if (root / "index.html").read_text() != output:
        raise SystemExit("site/index.html differs: run python3 scripts/build_product_site.py")
    print("Product site generated content is current.")
else:
    (root / "index.html").write_text(output)
