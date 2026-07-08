const puppeteer = require('puppeteer');
const GifEncoder = require('gif-encoder-2');
const Jimp = require('jimp');
const fs = require('fs');
const path = require('path');

// Records the two guided Mission Plan sequences (Moon and Mars views) to
// half-size README tiles: moon-mission.gif + mars-mission.gif. Mirrors
// capture_gif.js — same puppeteer -> gif-encoder-2 -> jimp pipeline — but
// captures at the hero GIF's viewport and downscales 4x, so the pair stacks
// under dashboard.gif as a perfectly aligned 2-up row.

const VIEW_W = 1200;
const VIEW_H = 502;             // hero viewport — identical layout/UI to dashboard.gif
const OUT_W = 600;
const OUT_H = 251;              // half the hero: two tiles fit its width exactly
const FRAME_DELAY = 100;        // ms between capture ticks (~real cadence is measured)
const MAX_FRAMES = 600;         // safety cap if the director never reports done
const TAIL_FRAMES = 10;         // hold the "Sequence complete" state before looping

async function main() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();
  // 2x supersample like capture_gif.js; the 2400x1004 screenshots downscale to
  // 600x251 (4x) below — keeps the small tiles crisp.
  await page.setViewport({ width: VIEW_W, height: VIEW_H, deviceScaleFactor: 2 });

  const htmlPath = path.resolve(__dirname, 'solar_system.html');
  await page.goto(`file://${htmlPath}`);
  await new Promise(r => setTimeout(r, 2000));

  // Speed 2 -> director rate 1.45x (solar_system.html: rate = 0.55 + 0.45*min(speed,4))
  // — brisk enough to keep the GIFs short without rushing the phase captions.
  await page.evaluate(() => {
    const slider = document.getElementById('speed');
    slider.value = 2.0;
    slider.dispatchEvent(new Event('input'));
  });

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // Run one view's full plan sequence and return its frames + measured cadence.
  async function captureMission(view) {
    await page.evaluate(v => document.querySelector(`.tab[data-view="${v}"]`).click(), view);
    await sleep(900);           // let the tab-switch camera ease settle

    await page.evaluate(v => views[v].director.start(), view);

    const frames = [];
    const t0 = Date.now();
    let done = false;
    for (let i = 0; i < MAX_FRAMES; i++) {
      frames.push(await page.screenshot({ type: 'png' }));
      process.stdout.write(`\r  ${view}: frame ${frames.length}   `);
      if (done && frames.length >= MAX_FRAMES) break;
      if (!done) {
        done = await page.evaluate(v => views[v].director.done, view);
        if (done) {             // hold the finished timeline, then stop
          for (let k = 0; k < TAIL_FRAMES; k++) {
            await sleep(FRAME_DELAY);
            frames.push(await page.screenshot({ type: 'png' }));
            process.stdout.write(`\r  ${view}: frame ${frames.length} (tail)   `);
          }
          break;
        }
      }
      await sleep(FRAME_DELAY);
    }
    // Screenshot latency dominates the cadence — measure it so GIF playback
    // matches wall-clock (captions/timeline read at their true pace).
    const msPerFrame = (Date.now() - t0) / frames.length;
    console.log(`\n  ${view}: ${frames.length} frames, ~${msPerFrame.toFixed(0)} ms/frame`);
    return { frames, msPerFrame };
  }

  const moon = await captureMission('moon');
  const mars = await captureMission('mars');

  await browser.close();

  async function encode(name, { frames, msPerFrame }) {
    console.log(`Encoding ${name}...`);
    const gif = new GifEncoder(OUT_W, OUT_H, 'neuquant', true);
    gif.setDelay(Math.round(msPerFrame));
    gif.setRepeat(0);
    gif.start();
    for (const buf of frames) {
      const img = await Jimp.read(buf);
      img.resize(OUT_W, OUT_H, Jimp.RESIZE_BICUBIC);   // 4x supersample -> 1x
      gif.addFrame(img.bitmap.data);
    }
    gif.finish();
    const data = gif.out.getData();
    fs.writeFileSync(path.join(__dirname, name), data);
    console.log(`Done! Saved ${name} (${(data.length / 1024).toFixed(0)} KB)`);
  }

  await encode('moon-mission.gif', moon);
  await encode('mars-mission.gif', mars);

  console.log('Optimize with: gifsicle -O3 --lossy=60 -b moon-mission.gif mars-mission.gif');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
