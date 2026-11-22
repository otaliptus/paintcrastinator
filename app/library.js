const gallery = document.getElementById("gallery");
const MASTERWORKS = new Set(["mona-lisa", "girl-with-a-pearl-earring", "starry-night", "great-wave", "van-gogh-self-portrait"]);
const MODERN = new Set(["sunflowers", "the-snail", "mondrian-1930"]);

function creditText(credit) {
  return `${credit.licence === "CC BY-SA 4.0" ? "Photo by " : ""}${credit.author}, ${credit.licence}, via ${credit.source || "Wikimedia Commons"}${credit.note ? `. ${credit.note}` : ""}`;
}

function creditCaption(credit) {
  if (!credit) return "";
  const author = credit.licence === "CC BY-SA 4.0" ? `Photo by ${credit.author}` : credit.author;
  const licence = credit.licence === "CC BY-SA 4.0" ? `<a href="https://creativecommons.org/licenses/by-sa/4.0/">${credit.licence}</a>` : credit.licence;
  return `<p class="card-credit">${author}, ${licence}, <a href="${credit.url}">via ${credit.source || "Wikimedia Commons"}</a>${credit.note ? `. ${credit.note}` : ""}</p>`;
}

function card(recipe, index) {
  const article = document.createElement("article");
  article.className = "painting-card";
  const score = recipe.scores?.similarity ?? "—";
  article.innerHTML = `
    <div class="card-image-wrap"${recipe.credit ? ` title="${creditText(recipe.credit)}"` : ""}>
      <a class="card-image-link" href="recipe.html?id=${encodeURIComponent(recipe.id)}" aria-label="Open ${recipe.title} study">
        <img class="card-image" src="../recipes/${recipe.id}.png" alt="Soft-brush reconstruction of ${recipe.title}" loading="${index < 2 ? "eager" : "lazy"}">
      </a>
      <span class="card-score"><strong>${score}</strong> / 100</span>
    </div>
    <div class="card-info">
      <div><h3 class="card-title"><a href="recipe.html?id=${encodeURIComponent(recipe.id)}">${recipe.title}</a></h3><p class="card-artist">${recipe.artist} · ${recipe.year}<br>${recipe.strokeCount.toLocaleString()} stroke recipe</p></div>
      <a class="open-study" href="recipe.html?id=${encodeURIComponent(recipe.id)}" aria-label="Open ${recipe.title}">↗</a>
      <button class="original-toggle" type="button" aria-pressed="false">View original</button>
      ${creditCaption(recipe.credit)}
    </div>`;
  const button = article.querySelector(".original-toggle");
  const image = article.querySelector(".card-image");
  button.addEventListener("click", () => {
    const original = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(original));
    button.textContent = original ? "View brush study" : "View original";
    image.src = original ? `../references/${recipe.id}.jpg` : `../recipes/${recipe.id}.png`;
    image.alt = `${original ? "Original" : "Soft-brush reconstruction of"} ${recipe.title}`;
  });
  return article;
}

async function loadLibrary() {
  try {
    const response = await fetch("../recipes/manifest.json");
    if (!response.ok) throw new Error(`Collection returned ${response.status}`);
    const recipes = await response.json();
    const masterworks = recipes.filter((recipe) => MASTERWORKS.has(recipe.id));
    const modern = recipes.filter((recipe) => MODERN.has(recipe.id));
    const icons = recipes.filter((recipe) => !MASTERWORKS.has(recipe.id) && !MODERN.has(recipe.id));
    document.getElementById("masterworks-gallery").replaceChildren(...masterworks.map(card));
    document.getElementById("icons-gallery").replaceChildren(...icons.map(card));
    document.getElementById("modern-gallery").replaceChildren(...modern.map(card));
    document.getElementById("painting-count").textContent = recipes.length;
    document.getElementById("stroke-total").textContent = recipes.reduce((sum, recipe) => sum + recipe.strokeCount, 0).toLocaleString();
  } catch (error) {
    gallery.innerHTML = `<p class="gallery-error">The collection could not be loaded. Serve this folder over HTTP and try again.<br><small>${error.message}</small></p>`;
  }
}

loadLibrary();
