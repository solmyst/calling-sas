import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const source=await fs.readFile('scripts/instrument.js','utf8');
const svg=source.match(/cursor\.innerHTML='([^']+)'/)[1];
const browser=await chromium.launch(),page=await browser.newPage();
await page.setContent(`<style>body{margin:0;background:transparent}svg{display:block}</style>${svg}`);
await page.locator('svg').screenshot({path:'out/cursor-template.png',omitBackground:true});await browser.close();
