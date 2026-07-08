const puppeteer = require('puppeteer');
const GifEncoder = require('gif-encoder-2');
const Jimp = require('jimp');
const fs = require('fs');
const path = require('path');

const WIDTH = 1200;
const HEIGHT = 502;             // 1200x502 = 2.39:1 anamorphic "Scope" — cinematic widescreen
const FRAME_DELAY = 60;         // ms between frames (~16.7 fps; quantizes to 6 cs in the GIF)

async function main() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();
  // 2× supersample; Jimp downscales below for crisp, less-banded frames.
  await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 2 });

  const htmlPath = path.resolve(__dirname, 'solar_system.html');
  await page.goto(`file://${htmlPath}`);
  await new Promise(r => setTimeout(r, 2000));

  await page.evaluate(() => {
    const slider = document.getElementById('speed');
    slider.value = 1.0;
    slider.dispatchEvent(new Event('input'));
  });

  const frames = [];
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const switchTo = view => page.evaluate(v => document.querySelector(`.tab[data-view="${v}"]`).click(), view);

  // The first frames after a tab switch naturally include the ~0.55s camera ease-in.
  async function grab(label, count) {
    for (let i = 0; i < count; i++) {
      frames.push(await page.screenshot({ type: 'png' }));
      process.stdout.write(`\r  ${label}: frame ${i + 1}/${count}   `);
      await sleep(FRAME_DELAY);
    }
    console.log();
  }

  await switchTo('moon');
  await grab('moon', 22);

  // Overview with the BODIES rail, then focus Jupiter to show the docked data sheet.
  await switchTo('solar');
  await grab('solar (overview)', 14);
  await page.evaluate(() => views.solar.focusByName('Jupiter'));
  await sleep(700);   // let the ~0.55s camera ease-in settle before holding
  // Slow the turntable so the GIF optimizer can diff away unchanged pixels.
  await page.evaluate(() => { controls.autoRotateSpeed = 0.22; });
  await grab('solar (Jupiter)', 30);

  await switchTo('mars');
  await grab('mars', 18);

  await browser.close();

  console.log('Encoding GIF...');
  const gif = new GifEncoder(WIDTH, HEIGHT, 'neuquant', true);
  gif.setDelay(FRAME_DELAY);
  gif.setRepeat(0);
  gif.start();

  for (const buf of frames) {
    const img = await Jimp.read(buf);
    img.resize(WIDTH, HEIGHT, Jimp.RESIZE_BICUBIC);   // 2x supersample -> 1x
    gif.addFrame(img.bitmap.data);
  }

  gif.finish();

  const outPath = path.join(__dirname, 'dashboard.gif');
  const data = gif.out.getData();
  fs.writeFileSync(outPath, data);

  const kb = (data.length / 1024).toFixed(0);
  console.log(`Done! Saved dashboard.gif (${kb} KB)`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
