const puppeteer = require('puppeteer');
const GifEncoder = require('gif-encoder-2');
const Jimp = require('jimp');
const fs = require('fs');
const path = require('path');

// Mission-focused companion to capture_gif.js: instead of a calm three-tab
// overview, this captures one *complete* mission loop from the Moon and Mars
// tabs, sped up so each full narrative fits in a few seconds.
const WIDTH = 1000;
const HEIGHT = 560;
const FRAME_DELAY = 60;         // ms between frames (~16.7 fps; quantizes to 6 cs in the GIF)
// The 2× screenshot dominates each capture cycle, so SPEED sets frames-per-loop:
// lower is smoother but heavier. 3× balances full loops against a README-friendly size.
const SPEED = 3.0;
const SAFETY_CAP = 160;       // hard frame ceiling per tab if the wrap is never seen

async function main() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();
  // deviceScaleFactor: 2 renders the dashboard at 2× (the app caps setPixelRatio
  // at 2, solar_system.html:427); Jimp downscales to WIDTH×HEIGHT below for crisp,
  // less-banded frames.
  await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 2 });

  const htmlPath = path.resolve(__dirname, 'solar_system.html');
  await page.goto(`file://${htmlPath}`);

  // Wait for Three.js scene to initialize
  await new Promise(r => setTimeout(r, 2000));

  // Fast-forward so a full mission loop is captured in a few seconds of wall time.
  await page.evaluate(s => {
    const slider = document.getElementById('speed');
    slider.value = s;
    slider.dispatchEvent(new Event('input'));
  }, SPEED);

  const frames = [];
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const switchTo = view => page.evaluate(v => document.querySelector(`.tab[data-view="${v}"]`).click(), view);

  // Capture exactly one full mission loop: reset the view's 0→1 loop counter,
  // then grab frames until it wraps back past 0 (or we hit the safety cap).
  // `field` is the per-view phase variable — views.moon.missionT / views.mars.progress.
  async function grabLoop(label, viewKey, field) {
    await page.evaluate((k, f) => { views[k][f] = 0; }, viewKey, field);
    let prev = 0;
    for (let i = 0; i < SAFETY_CAP; i++) {
      frames.push(await page.screenshot({ type: 'png' }));
      const cur = await page.evaluate((k, f) => views[k][f], viewKey, field);
      process.stdout.write(`\r  ${label}: frame ${i + 1}  (phase ${cur.toFixed(2)})   `);
      // Wrapped past 1 → back near 0: one full loop captured.
      if (i > 2 && cur < prev) { console.log('\n  ...full loop captured'); break; }
      prev = cur;
      await sleep(FRAME_DELAY);
    }
    console.log();
  }

  // Moon — four-phase Starship lunar mission (LEO → refuel → TLI → lunar arrival).
  await switchTo('moon');
  await sleep(700);   // let the ~0.55s camera ease-in settle before the loop starts
  await grabLoop('moon', 'moon', 'missionT');

  // Mars — heliocentric Earth → Mars Starship Hohmann transfer (TMI → cruise → MOI).
  await switchTo('mars');
  await sleep(700);
  await grabLoop('mars', 'mars', 'progress');

  await browser.close();

  console.log('Encoding GIF...');
  const gif = new GifEncoder(WIDTH, HEIGHT, 'neuquant', true);
  gif.setDelay(FRAME_DELAY);
  gif.setRepeat(0);
  gif.start();

  for (const buf of frames) {
    const img = await Jimp.read(buf);
    // Downscale the 2× supersampled capture to WIDTH×HEIGHT — the anti-aliasing
    // win that also softens 256-color banding.
    img.resize(WIDTH, HEIGHT, Jimp.RESIZE_BICUBIC);
    gif.addFrame(img.bitmap.data);
  }

  gif.finish();

  const outPath = path.join(__dirname, 'preview-missions.gif');
  const data = gif.out.getData();
  fs.writeFileSync(outPath, data);

  const kb = (data.length / 1024).toFixed(0);
  console.log(`Done! Saved preview-missions.gif (${frames.length} frames, ${kb} KB)`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
