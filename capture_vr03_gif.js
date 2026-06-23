const puppeteer = require('puppeteer');
const GifEncoder = require('gif-encoder-2');
const Jimp = require('jimp');
const fs = require('fs');
const path = require('path');

// Renders the VR-03 orbit visual (vr03_orbit_capture.html) to a seamless looping
// GIF for the README footer. Mirrors capture_gif.js — same puppeteer ->
// gif-encoder-2 -> jimp -> (gifsicle) pipeline and 2x supersample/downscale.

const WIDTH = 512;
const HEIGHT = 320;             // 256x160 @2x — the portfolio orbit card's native aspect (8:5)
const FRAME_DELAY = 60;         // ms between frames (~16.7 fps), same cadence as capture_gif.js
const FRAMES = 50;              // one full pass = one spacecraft transit => seamless loop

async function main() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();
  // The card is 256x160 CSS; deviceScaleFactor: 2 captures the styled #c element
  // at WIDTH x HEIGHT (512x320), 1:1 with its 2x backing store — crisp, no rescale.
  await page.setViewport({ width: 360, height: 240, deviceScaleFactor: 2 });

  const htmlPath = path.resolve(__dirname, 'vr03_orbit_capture.html');
  await page.goto(`file://${htmlPath}`);
  await new Promise(r => setTimeout(r, 300));   // let fonts/canvas settle

  const card = await page.$('#c');              // screenshot the bordered card, not the page

  const frames = [];
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  for (let i = 0; i < FRAMES; i++) {
    await page.evaluate((idx, n) => window.renderFrame(idx, n), i, FRAMES);
    frames.push(await card.screenshot({ type: 'png' }));
    process.stdout.write(`\r  orbit: frame ${i + 1}/${FRAMES}   `);
    await sleep(20);
  }
  console.log();

  await browser.close();

  console.log('Encoding GIF...');
  const gif = new GifEncoder(WIDTH, HEIGHT, 'neuquant', true);
  gif.setDelay(FRAME_DELAY);
  gif.setRepeat(0);   // loop forever
  gif.start();

  for (const buf of frames) {
    const img = await Jimp.read(buf);
    img.resize(WIDTH, HEIGHT, Jimp.RESIZE_BICUBIC);   // 2x supersample -> 1x
    gif.addFrame(img.bitmap.data);
  }

  gif.finish();

  const outPath = path.join(__dirname, 'vr03-orbit.gif');
  const data = gif.out.getData();
  fs.writeFileSync(outPath, data);

  const kb = (data.length / 1024).toFixed(0);
  console.log(`Done! Saved vr03-orbit.gif (${kb} KB)`);
  console.log('Optimize with: gifsicle -O3 --lossy=60 -o vr03-orbit.gif vr03-orbit.gif');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
