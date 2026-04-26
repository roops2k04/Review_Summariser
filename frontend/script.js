const API = "";   // same-origin: frontend served by FastAPI

let allPlaces   = [];
let selectedPlace = null;

/* ══════════════════════════════════════════
   STEP 1 — SEARCH
══════════════════════════════════════════ */
async function doSearch() {
  const query    = v("iQuery");
  const location = v("iLocation");
  if (!query || !location) return showErr("Please enter both a business name and a city.");

  setSearchLoading(true);
  clearErr();
  hide("outletsSection");
  hide("resultsSection");

  try {
    const data = await post("/api/search", { query, location });
    allPlaces = data.places || [];
    if (!allPlaces.length) throw new Error("No outlets found. Try a different search.");
    renderOutlets(allPlaces, data.search_term);
  } catch (e) {
    showErr(e.message);
  } finally {
    setSearchLoading(false);
  }
}

function renderOutlets(places, term) {
  id("outletsTitle").textContent = `${places.length} outlet${places.length > 1 ? "s" : ""} found`;
  id("outletsSub").textContent   = `Results for "${term}" — click one to analyze`;

  const grid = id("outletsList");
  grid.innerHTML = "";

  places.forEach((p, i) => {
    const card = document.createElement("div");
    card.className = "outlet-card fade-up";
    card.style.animationDelay = `${i * 55}ms`;

    const rcLabel = p.review_count
      ? `${Number(p.review_count).toLocaleString()}<small>Google reviews</small>`
      : `N/A<small>Google reviews</small>`;

    const rating = p.rating
      ? `<div class="rating-line"><span class="star">★</span> ${p.rating}</div>`
      : "";

    card.innerHTML = `
      <div>
        <div class="outlet-num"># ${i + 1}</div>
        <div class="outlet-name">${esc(p.name)}</div>
        <div class="outlet-addr">${esc(p.address)}</div>
      </div>
      <div class="outlet-right">
        <div class="review-pill">${rcLabel}</div>
        ${rating}
      </div>
      <div class="outlet-chevron">›</div>`;

    card.onclick = () => analyzePlace(p);
    grid.appendChild(card);
  });

  show("outletsSection");
  scrollTo(0, id("outletsSection").offsetTop - 20, "smooth");
}

/* ══════════════════════════════════════════
   STEP 2 — ANALYZE SELECTED OUTLET
══════════════════════════════════════════ */
async function analyzePlace(place) {
  selectedPlace = place;
  const question = v("iQuestion") || `What are the pros and cons of ${place.name}?`;

  showOverlay();

  try {
    step(1, "Scraping 100+ reviews…");
    const data = await post("/api/analyze", {
      cid:      place.cid     || "",
      location: v("iLocation"),
      name:     place.name,
      address:  place.address,
      snippet:  place.snippet || "",
      question,
    });

    step(2, "Chunking & embedding…");
    await wait(350);
    step(3, "RAG retrieval…");
    await wait(350);
    step(4, "Generating analysis…");
    await wait(450);

    hideOverlay();
    renderResults(data, place);
  } catch (e) {
    hideOverlay();
    showErr(e.message);
  }
}

function renderResults(d, place) {
  id("rName").textContent    = d.name;
  id("rAddress").textContent = d.address;

  /* stats — 4 boxes */
  id("sReviews").textContent       = fmt(d.total_reviews);
  id("sChunks").textContent        = fmt(d.total_chunks);
  id("sRetrieved").textContent     = fmt(d.chunks_retrieved);
  id("sGoogleReviews").textContent = place.review_count ? Number(place.review_count).toLocaleString() : "N/A";

  /* pros */
  const pros = (d.pros || []).slice(0, 5);
  id("prosList").innerHTML = pros.map(p => `<li>${esc(p)}</li>`).join("");

  /* cons */
  const cons = (d.cons || []).slice(0, 5);
  id("consList").innerHTML = cons.map(c => `<li>${esc(c)}</li>`).join("");

  /* summary */
  id("rSummary").textContent = d.summary || "—";

  /* excerpts */
  const ex = d.source_excerpts || [];
  id("excerptBadge").textContent = `${ex.length} chunks`;
  id("excerptsList").innerHTML   = ex.map(e => `<div class="excerpt">${esc(e)}</div>`).join("");

  hide("outletsSection");
  show("resultsSection");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ══════════════════════════════════════════
   NAV HELPERS
══════════════════════════════════════════ */
function backToOutlets()  { hide("resultsSection"); show("outletsSection"); window.scrollTo({top:0,behavior:"smooth"}); }
function resetToSearch()  { hide("outletsSection"); hide("resultsSection"); clearErr(); window.scrollTo({top:0,behavior:"smooth"}); }

/* ══════════════════════════════════════════
   OVERLAY STEPS
══════════════════════════════════════════ */
const stepMsgs = ["Scraping 100+ reviews…","Chunking & embedding…","RAG retrieval…","Generating 5 pros & 5 cons…"];
function showOverlay() {
  document.querySelectorAll(".ls").forEach(el => el.classList.remove("active","done"));
  id("loadMsg").textContent = stepMsgs[0];
  show("loadOverlay");
}
function hideOverlay()  { hide("loadOverlay"); }
function step(n, msg) {
  id("loadMsg").textContent = msg || stepMsgs[n-1] || "";
  document.querySelectorAll(".ls").forEach((el, i) => {
    el.classList.remove("active","done");
    if (i + 1 < n)  el.classList.add("done");
    if (i + 1 === n) el.classList.add("active");
  });
}

/* ══════════════════════════════════════════
   LOADING STATE FOR SEARCH BUTTON
══════════════════════════════════════════ */
function setSearchLoading(on) {
  id("searchBtn").disabled = on;
  id("searchTxt").textContent = on ? "Searching…" : "Search Outlets";
  id("searchArr").classList.toggle("hidden", on);
  id("searchSpin").classList.toggle("hidden", !on);
}

/* ══════════════════════════════════════════
   ERROR
══════════════════════════════════════════ */
function showErr(msg) {
  const el = id("errBox");
  el.textContent = "⚠  " + msg;
  el.classList.remove("hidden");
  el.scrollIntoView({ behavior:"smooth", block:"center" });
}
function clearErr() { id("errBox").classList.add("hidden"); }

/* ══════════════════════════════════════════
   UTILS
══════════════════════════════════════════ */
function id(x)    { return document.getElementById(x); }
function v(x)     { return (id(x)?.value || "").trim(); }
function show(x)  { id(x)?.classList.remove("hidden"); }
function hide(x)  { id(x)?.classList.add("hidden"); }
function wait(ms) { return new Promise(r => setTimeout(r, ms)); }
function fmt(n)   { return (n != null && n !== "") ? Number(n).toLocaleString() : "—"; }
function esc(s)   {
  return String(s||"")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}

async function post(url, body) {
  const res  = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `Server error ${res.status}`);
  return data;
}

/* Enter key */
document.addEventListener("DOMContentLoaded", () => {
  ["iQuery","iLocation","iQuestion"].forEach(xid => {
    id(xid)?.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
  });
});
