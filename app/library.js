const gallery = document.getElementById("gallery");

// Difficulty levels, easiest first, by stroke count.
const LEVELS = [
  { name: "Lessons", max: 99 },
  { name: "Easy", max: 999 },
  { name: "Intermediate", max: 2999 },
  { name: "Masterpieces", max: Infinity },
];

const referencePath = (recipe) => `../${(recipe.reference || `references/${recipe.id}.jpg`).replace(/^(\.\.\/)+/, "")}`;
const renderPath = (recipe) => `../recipes/${recipe.id}.png`;
// Paint-along time at about 4 seconds per stroke.
function duration(count) {
  const min = Math.max(1, Math.round(count * 4 / 60));
  return min < 60 ? `${min} min` : `${Math.round(min / 60)} h`;
}

function creditText(credit) {
  if (!credit) return "";
  const author = credit.licence === "CC BY-SA 4.0" ? `Photo by ${credit.author}` : credit.author;
  return `${author}, ${credit.licence}${credit.source ? `, ${credit.source}` : ""}`;
}

function card(recipe) {
  const link = document.createElement("a");
  link.className = "painting-card";
  link.href = `recipe.html?id=${encodeURIComponent(recipe.id)}`;
  link.innerHTML = `
    <div class="card-image-wrap"${recipe.credit && !recipe.id.startsWith("lesson-") ? ` title="${creditText(recipe.credit).replace(/"/g, "&quot;")}"` : ""}>
      <img class="card-image" src="${renderPath(recipe)}" alt="${recipe.title}" loading="lazy">
      <img class="card-original" src="${referencePath(recipe)}" alt="" loading="lazy" aria-hidden="true">
    </div>
    <h3 class="card-title">${recipe.title}</h3>
    <p class="card-meta">${recipe.strokeCount.toLocaleString()} strokes · ≈ ${duration(recipe.strokeCount)}</p>`;
  return link;
}

async function loadLibrary() {
  try {
    const response = await fetch("../recipes/manifest.json");
    if (!response.ok) throw new Error(`Collection returned ${response.status}`);
    const recipes = (await response.json())
      // Easiest first: fewer strokes, then the closer the recipe matches its original.
      .sort((a, b) => a.strokeCount - b.strokeCount || (b.scores?.similarity ?? 0) - (a.scores?.similarity ?? 0));
    let min = 0;
    const sections = LEVELS.map((level) => {
      const items = recipes.filter((recipe) => recipe.strokeCount >= min && recipe.strokeCount <= level.max);
      min = level.max + 1;
      if (!items.length) return null;
      const section = document.createElement("section");
      section.className = "level";
      section.innerHTML = `<h2 class="level-title">${level.name}</h2><div class="card-grid"></div>`;
      section.querySelector(".card-grid").append(...items.map(card));
      return section;
    }).filter(Boolean);
    gallery.replaceChildren(...sections);
  } catch (error) {
    gallery.innerHTML = `<p class="loading">The collection could not be loaded. ${error.message}</p>`;
  }
}

loadLibrary();
