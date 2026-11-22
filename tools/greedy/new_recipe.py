#!/usr/bin/env python3
"""Create a recipe skeleton (metadata only, no strokes) for Claude's planner.
Usage: newrecipe.py <id>   (metadata below). Writes recipes/<id>.json if it has no strokes yet."""
import json, sys
import numpy as np
from PIL import Image

R = "/home/node/.openclaw/workspace/painting-cookbook/"
META = {
    "impression-sunrise": ("Impression, Sunrise", "Claude Monet", "1872", "Public domain", "https://commons.wikimedia.org/wiki/File:Monet_-_Impression,_Sunrise.jpg", "The harbour dissolves into mist around one orange sun."),
    "nocturne-battersea": ("Nocturne: Blue and Gold – Old Battersea Bridge", "James McNeill Whistler", "c. 1872–75", "Public domain", "https://commons.wikimedia.org/wiki/File:James_McNeill_Whistler_-_Nocturne_en_bleu_et_or.jpg", "A night river in blue-green, with one dark bridge pier."),
    "mondrian-1930": ("Composition with Red, Blue and Yellow", "Piet Mondrian", "1930", "Public domain", "https://commons.wikimedia.org/wiki/File:Piet_Mondriaan,_1930_-_Mondrian_Composition_II_in_Red,_Blue,_and_Yellow.jpg", "A measured grid of red, blue, yellow and white held by black bars."),
    "sudden-shower": ("Sudden Shower over Shin-Ōhashi Bridge", "Utagawa Hiroshige", "1857", "Public domain", "https://commons.wikimedia.org/wiki/File:Hiroshige,_Sudden_shower_over_Shin-%C5%8Chashi_bridge_and_Atake,_1857.jpg", "Travellers hurry across a bridge under slanting rain."),
    "composition-viii": ("Composition VIII", "Wassily Kandinsky", "1923", "CC0", "https://commons.wikimedia.org/wiki/File:Kandinsky_-_Composition_8,_July_1923.jpg", "Circles, lines and grids balanced like music."),
    "basket-of-apples": ("The Basket of Apples", "Paul Cézanne", "c. 1893", "Public domain", "https://commons.wikimedia.org/wiki/File:Le_panier_de_pommes,_par_Paul_C%C3%A9zanne.jpg", "Apples, a bottle and a cloth built from blocky planes of colour."),
    "red-fuji": ("Fine Wind, Clear Morning (Red Fuji)", "Katsushika Hokusai", "c. 1830–32", "Public domain", "https://commons.wikimedia.org/wiki/File:Katsushika_Hokusai_-_Fine_Wind,_Clear_Morning_(Gaif%C5%AB_kaisei)_-_Google_Art_Project.jpg", "Mount Fuji glows red at dawn under a sky of small clouds."),
    "the-dance": ("Dance", "Henri Matisse", "1910", "Public domain", "https://commons.wikimedia.org/wiki/File:Henri_Matisse_-_Dance_1910.jpg", "Five figures in a ring on flat blue and green."),
    "wheatfield-crows": ("Wheatfield with Crows", "Vincent van Gogh", "1890", "Public domain", "https://commons.wikimedia.org/wiki/File:Vincent_van_Gogh_-_Wheatfield_with_crows_-_Google_Art_Project.jpg", "A stormy sky over gold wheat, three paths and a flight of crows."),
    "whistlers-mother": ("Arrangement in Grey and Black (Whistler's Mother)", "James McNeill Whistler", "1871", "Public domain", "https://commons.wikimedia.org/wiki/File:Whistlers_Mother_high_res.jpg", "A seated figure in black, in profile against a grey wall."),
    "american-gothic": ("American Gothic", "Grant Wood", "1930", "Public domain", "https://commons.wikimedia.org/wiki/File:Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg", "A farmer and his daughter before a house with a Gothic window."),
}
pid = sys.argv[1]
title, artist, year, licence, url, description = META[pid]
ref = Image.open(f"{R}references/{pid}.jpg").convert("RGB")
W, H = ref.size
mean = np.asarray(ref, dtype=np.float32).reshape(-1, 3).mean(0)
ground = "#%02x%02x%02x" % tuple(int(v) for v in mean)
tips = ["Block in: big strokes, don't worry about edges.", "Build the large colour shapes.", "Refine edges and transitions.", "Finish with the few marks that matter most."]
labels = [("blocking", "Blocking in"), ("form", "Form and color"), ("refinement", "Refinement"), ("detail", "Fine details")]
recipe = {
    "id": pid, "title": title, "artist": artist, "year": year, "width": W, "height": H, "ground": ground,
    "reference": f"../references/{pid}.jpg", "description": description, "planner": "Claude greedy error-driven planner",
    "credit": {"author": artist, "licence": licence, "url": url, "source": "Wikimedia Commons"},
    "stages": [{"id": i, "label": l, "tip": t, "strokes": []} for (i, l), t in zip(labels, tips)], "strokeCount": 0,
}
json.dump(recipe, open(f"/home/node/.openclaw/workspace/_progress/claude-refine/out/{pid}-skeleton.json", "w"))
print(pid, W, H, ground)
