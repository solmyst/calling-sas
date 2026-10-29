import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const svg=await fs.readFile('public/cursor.svg','utf8');
const browser=await chromium.launch(),page=await browser.newPage();
await page.setContent(`<style>body{margin:0;background:transparent}svg{display:block}</style>${svg}`);
await page.locator('svg').screenshot({path:'out/cursor-template.png',omitBackground:true});await browser.close();
