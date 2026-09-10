void (async () => {
  'use strict';

  const EXPECTED_HOST = 'maimaidx-eng.com';
  const SEARCH_PATH = '/maimai-mobile/record/musicGenre/search/';
  const RATING_PATH = '/maimai-mobile/home/ratingTargetMusic/';
  const DIFFICULTIES = ['basic', 'advanced', 'expert', 'master', 'remaster'];

  if (location.hostname !== EXPECTED_HOST) {
    alert('MaiUp exporter: open the International maimai DX NET Song Scores page first.');
    return;
  }

  const existing = document.getElementById('maiup-export-status');
  if (existing) existing.remove();
  const status = document.createElement('div');
  status.id = 'maiup-export-status';
  Object.assign(status.style, {
    position: 'fixed',
    inset: '16px 16px auto 16px',
    zIndex: '2147483647',
    padding: '14px 18px',
    borderRadius: '14px',
    background: '#111827',
    color: '#cffafe',
    font: '600 14px/1.5 system-ui, sans-serif',
    boxShadow: '0 12px 40px rgba(0,0,0,.45)',
  });
  document.body.append(status);

  const iconStem = (image) => {
    const source = image.getAttribute('src') || '';
    return source.split('/').pop().split('?')[0];
  };
  const comboMap = { fc: 'FC', fcp: 'FC+', ap: 'AP', app: 'AP+' };
  const syncMap = { fs: 'FS', fsp: 'FS+', fsd: 'FSD', fsdp: 'FSD+' };

  function parseCard(card) {
    const images = [...card.querySelectorAll('img')].map(iconStem);
    const text = card.textContent || '';
    const achievement = text.match(/(\d{1,3}\.\d{4})%/);
    if (!achievement) return null;
    const difficultyFromIcon = images
      .find((name) => name.startsWith('diff_'))
      ?.match(/^diff_(.+)\.png$/)?.[1];
    const difficultyFromClass = [...card.classList]
      .find((name) => /^music_(basic|advanced|expert|master|remaster)_score_back$/.test(name))
      ?.match(/^music_(.+)_score_back$/)?.[1];
    const difficulty = difficultyFromIcon ?? difficultyFromClass;
    const title = card.querySelector('.music_name_block')?.textContent?.trim();
    if (!title || !difficulty) throw new Error('A score card uses an unknown page layout.');
    const imageSources = [...card.querySelectorAll('img')]
      .flatMap((image) =>
        ['src', 'data-src', 'data-original'].map(
          (attribute) => image.getAttribute(attribute) || '',
        ),
      )
      .join(' ');
    const rowId = card.id.toLowerCase();
    const chartType = rowId.includes('sta_') || /(?:music|kind)_standard/i.test(imageSources)
      ? 'std'
      : 'dx';
    const dxScore = text.match(/([\d,]+)\s*\/\s*([\d,]+)/);
    const comboKey = Object.keys(comboMap).find((key) =>
      images.includes(`music_icon_${key}.png`),
    );
    const syncKey = Object.keys(syncMap).find((key) =>
      images.includes(`music_icon_${key}.png`),
    );
    return {
      title,
      chartType,
      difficulty,
      achievement: achievement[1],
      fullCombo: comboKey ? comboMap[comboKey] : null,
      syncStatus: syncKey ? syncMap[syncKey] : null,
      dxScore: dxScore ? Number(dxScore[1].replaceAll(',', '')) : null,
      playedAt: null,
    };
  }

  try {
    const scores = [];
    for (const [difficultyIndex, difficulty] of DIFFICULTIES.entries()) {
      status.textContent = `MaiUp: reading ${difficulty.toUpperCase()} scores (${difficultyIndex + 1} / ${DIFFICULTIES.length})…`;
      const response = await fetch(
        `${location.origin}${SEARCH_PATH}?genre=99&diff=${difficultyIndex}`,
        {
          credentials: 'include',
          cache: 'no-store',
          headers: { Accept: 'text/html', 'X-Requested-With': 'XMLHttpRequest' },
        },
      );
      if (!response.ok) throw new Error(`DX NET returned HTTP ${response.status}.`);
      const html = await response.text();
      const page = new DOMParser().parseFromString(html, 'text/html');
      if (
        html.includes('Please agree to the following terms of service before log in.') ||
        !page.querySelector('.music_name_block')
      ) {
        throw new Error('The login session expired or the score page layout changed.');
      }
      const cards = [...page.querySelectorAll('div[class*="_score_back"]')];
      scores.push(...cards.map(parseCard).filter(Boolean));
      await new Promise((resolve) => setTimeout(resolve, 250));
    }

    status.textContent = 'MaiUp: reading the official B35 / B15 list…';
    const ratingResponse = await fetch(`${location.origin}${RATING_PATH}`, {
      credentials: 'include',
      cache: 'no-store',
      headers: { Accept: 'text/html', 'X-Requested-With': 'XMLHttpRequest' },
    });
    if (!ratingResponse.ok) {
      throw new Error(`DX NET Rating Target returned HTTP ${ratingResponse.status}.`);
    }
    const ratingHtml = await ratingResponse.text();
    const newIndex = ratingHtml.indexOf('Songs for Rating(New)');
    const othersIndex = ratingHtml.indexOf('Songs for Rating(Others)');
    const selectionIndex = ratingHtml.indexOf('Songs for Rating Selection');
    let officialBest50 = null;
    if (newIndex >= 0 && othersIndex > newIndex) {
      const endIndex = selectionIndex > othersIndex ? selectionIndex : ratingHtml.length;
      const parseSection = (html, bucket) => {
        const page = new DOMParser().parseFromString(html, 'text/html');
        return [...page.querySelectorAll('div[class*="_score_back"]')]
          .map(parseCard)
          .filter(Boolean)
          .map((score, index) => ({ ...score, bucket, position: index + 1 }));
      };
      const b15 = parseSection(ratingHtml.slice(newIndex, othersIndex), 'b15');
      const b35 = parseSection(ratingHtml.slice(othersIndex, endIndex), 'b35');
      if (b15.length === 15 && b35.length === 35) {
        officialBest50 = [...b35, ...b15];
      }
    }

    const payload = {
      schemaVersion: 1,
      sourceRegion: 'international',
      sourceName: 'maimai DX NET complete score export',
      exportedAt: new Date().toISOString(),
      scores,
      officialBest50,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json;charset=utf-8',
    });
    const link = document.createElement('a');
    const downloadUrl = URL.createObjectURL(blob);
    link.href = downloadUrl;
    link.download = `maiup-scores-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(link);
    link.click();
    setTimeout(() => {
      URL.revokeObjectURL(downloadUrl);
      link.remove();
    }, 1000);
    status.textContent = officialBest50
      ? `MaiUp: exported ${scores.length} played charts and the official B35 / B15.`
      : `MaiUp: exported ${scores.length} played charts; official B50 was unavailable.`;
    setTimeout(() => status.remove(), 8000);
  } catch (error) {
    status.style.color = '#fecdd3';
    const message = error instanceof Error ? error.message : String(error);
    status.textContent = `MaiUp export failed: ${message}`;
  }
})();
