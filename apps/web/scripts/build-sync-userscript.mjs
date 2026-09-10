import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export function buildSyncUserscript(source) {
  return `// ==UserScript==
// @name MaiUp official score sync
// @namespace https://github.com/Zephyruz/MaiUp
// @version 1.1.0
// @description Import your scores when you click sync in local MaiUp
// @match https://maimaidx-eng.com/maimai-mobile/home/*
// @run-at document-idle
// @grant none
// @noframes
// ==/UserScript==
if (new URLSearchParams(location.hash.slice(1)).get('maiupAuto') === '1') {
${source.replace(/\r\n/g, '\n')}
}
`;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const source = readFileSync(new URL('../public/maiup-sync.js', import.meta.url), 'utf8');
  writeFileSync(new URL('../public/maiup-sync.user.js', import.meta.url), buildSyncUserscript(source));
}
