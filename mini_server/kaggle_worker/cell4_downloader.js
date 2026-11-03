/**
 * =============================================================================
 * CELL 4 — Ultra-Optimized Puppeteer Downloader (DOM Pruning & Zero-Disk Cache)
 * =============================================================================
 */

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const { PDFDocument, StandardFonts, rgb, degrees, PDFName, PDFString } = require('pdf-lib');

puppeteer.use(StealthPlugin());

function addClickableWatermark(pdfDoc, pdfPage, font, botUsername = 'ScribdPdfDownloaderBot') {
  const { width, height } = pdfPage.getSize();
  const badgeWidth = 140;
  const badgeHeight = 22;
  const margin = 10;
  const x = width - badgeWidth - margin;
  const y = height - badgeHeight - margin;

  pdfPage.drawRectangle({
    x, y,
    width: badgeWidth,
    height: badgeHeight,
    color: rgb(0.04, 0.04, 0.06),
    opacity: 0.88,
    borderColor: rgb(0.95, 0.77, 0.06),
    borderWidth: 1.0,
  });

  pdfPage.drawText(`⚡ @${botUsername}`, {
    x: x + 8,
    y: y + 6,
    size: 9.5,
    font,
    color: rgb(0.95, 0.77, 0.06),
  });

  const linkUrl = `https://t.me/${botUsername}`;
  const linkAnnot = pdfDoc.context.obj({
    Type: 'Annot',
    Subtype: 'Link',
    Rect: [x, y, x + badgeWidth, y + badgeHeight],
    Border: [0, 0, 0],
    A: {
      Type: 'Action',
      S: 'URI',
      URI: PDFString.of(linkUrl)
    }
  });

  const annotsRef = pdfPage.node.Annots();
  if (annotsRef) {
    annotsRef.push(linkAnnot);
  } else {
    pdfPage.node.set(PDFName.of('Annots'), pdfDoc.context.obj([linkAnnot]));
  }
}

async function renderScribdDocument(docId, rawOutputPath, startPage = 1, endPage = null, proxyUrl = null) {
  const docUrl = `https://www.scribd.com/embeds/${docId}/content?start_page=${startPage}&view_mode=scroll&access_key=key-f2qib7rwhbehpnMSdt`;

  let proxyServerArg = '';
  let proxyAuth = null;
  if (proxyUrl) {
    try {
      const parsed = new URL(proxyUrl.startsWith('http') ? proxyUrl : `http://${proxyUrl}`);
      proxyServerArg = `--proxy-server=${parsed.protocol}//${parsed.hostname}:${parsed.port}`;
      if (parsed.username && parsed.password) {
        proxyAuth = {
          username: decodeURIComponent(parsed.username),
          password: decodeURIComponent(parsed.password)
        };
      }
    } catch (e) {
      proxyServerArg = `--proxy-server=${proxyUrl}`;
    }
  }

  // ⚡ INDUSTRIAL ULTRA-LIGHTWEIGHT CHROMIUM FLAGS
  const launchArgs = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-accelerated-2d-canvas',
    '--disable-background-networking',
    '--disable-extensions',
    '--disable-component-update',
    '--disable-default-apps',
    '--mute-audio',
    '--no-first-run',
    '--no-zygote',
    '--disable-application-cache',
    '--disk-cache-size=1',       // ZERO DISK CACHE: Stops writing images to /tmp!
    '--media-cache-size=1',      // ZERO MEDIA CACHE!
    '--js-flags=--max-old-space-size=512',
    '--window-size=1200,1600'
  ];

  if (proxyServerArg) {
    launchArgs.push(proxyServerArg);
  }

  // Detect pre-installed system Chrome on Kaggle or Linux
  let executablePath = null;
  const candidates = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium'
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) {
      executablePath = p;
      break;
    }
  }

  const launchOptions = {
    headless: 'new',
    protocolTimeout: 600000,
    args: launchArgs
  };
  if (executablePath) {
    launchOptions.executablePath = executablePath;
  }

  const browser = await puppeteer.launch(launchOptions);

  const tempChunks = [];
  const downloadsDir = path.dirname(rawOutputPath);

  try {
    let page = await browser.newPage();
    if (proxyAuth) {
      await page.authenticate(proxyAuth);
    }

    page.setDefaultNavigationTimeout(60000);
    page.setDefaultTimeout(60000);
    await page.setViewport({ width: 1250, height: 2200, deviceScaleFactor: 1.0 });
    await page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    );

    await page.goto(docUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await new Promise(r => setTimeout(r, 2500));

    // Real document title detection
    let docTitle = await page.evaluate(() => {
      const ogTitle = document.querySelector('meta[property="og:title"]');
      if (ogTitle && ogTitle.content && !ogTitle.content.toLowerCase().includes('client challenge')) {
        return ogTitle.content.replace(/Scribd/i, '').trim();
      }
      const titleEl = document.querySelector('.document_title') || document.querySelector('h1') || document.querySelector('title');
      if (titleEl && titleEl.textContent) {
        const t = titleEl.textContent.replace(/Scribd/i, '').trim();
        if (!t.toLowerCase().includes('client challenge') && !t.toLowerCase().includes('just a moment')) {
          return t;
        }
      }
      return '';
    });
    if (!docTitle) docTitle = `Scribd_Doc_${docId}`;

    // Total pages detection
    let detectedTotal = await page.evaluate(() => {
      const totalEl = document.querySelector('.total_pages') || document.querySelector('.page_count');
      if (totalEl) {
        const m = totalEl.textContent.match(/\d+/);
        if (m) return parseInt(m[0]);
      }
      if (window.Scribd && window.Scribd.current_doc && window.Scribd.current_doc.page_count) {
        return window.Scribd.current_doc.page_count;
      }
      if (window.docManager && window.docManager.pages) {
        const pCount = Object.keys(window.docManager.pages).length;
        if (pCount > 0) return pCount;
      }
      const pageElements = document.querySelectorAll('[id^="outer_page_"]');
      return pageElements.length || 1;
    });

    const effectiveStart = Math.max(1, parseInt(startPage, 10) || 1);
    const effectiveEnd = endPage ? Math.min(detectedTotal, parseInt(endPage, 10)) : detectedTotal;
    const totalToCapture = effectiveEnd - effectiveStart + 1;

    // Fast jump to start page
    if (effectiveStart > 1) {
      await page.evaluate((s) => {
        if (window.docManager && typeof window.docManager.goto_page === 'function') {
          window.docManager.goto_page(s);
        } else {
          const el = document.getElementById(`outer_page_${s}`);
          if (el) el.scrollIntoView({ block: 'start' });
        }
      }, effectiveStart);
      await new Promise(r => setTimeout(r, 1500));
    }

    const CHUNK_SIZE = 35;
    let currentChunkDoc = await PDFDocument.create();
    let currentChunkFont = await currentChunkDoc.embedFont(StandardFonts.HelveticaBold);
    let chunkCount = 0;
    let capturedCount = 0;

    for (let i = effectiveStart; i <= effectiveEnd; i++) {
      const pageIdx = i - effectiveStart + 1;
      const pct = Math.round((pageIdx / totalToCapture) * 100);

      // Emit JSON progress line to stdout
      console.log(JSON.stringify({
        stage: 'rendering',
        percent: pct,
        currentPage: i,
        totalPages: effectiveEnd,
        docTitle
      }));

      // Scroll to page
      await page.evaluate((idx) => {
        const scroller = document.querySelector('.document_scroller') || window;
        const el = document.getElementById(`outer_page_${idx}`);
        if (el) {
          el.scrollIntoView({ block: 'start' });
          if (scroller !== window) {
            scroller.dispatchEvent(new Event('scroll', { bubbles: true }));
          }
        }
      }, i);

      // Wait for content paint
      const waitStart = Date.now();
      while (Date.now() - waitStart < 7000) {
        const contentReady = await page.evaluate((idx) => {
          const el = document.getElementById(`outer_page_${idx}`);
          if (!el) return false;
          const img = el.querySelector('img');
          if (img && img.src && img.complete && img.naturalWidth > 20) return true;
          if (el.querySelector('canvas') || el.querySelector('svg')) return true;
          return false;
        }, i);
        if (contentReady) break;
        await new Promise(r => setTimeout(r, 120));
      }

      await new Promise(r => setTimeout(r, 350));

      const pageElement = await page.$(`#outer_page_${i}`);
      if (pageElement) {
        const imgBuffer = await pageElement.screenshot({ type: 'jpeg', quality: 78 });
        const embeddedImage = await currentChunkDoc.embedJpg(imgBuffer);
        const pdfPage = currentChunkDoc.addPage([embeddedImage.width, embeddedImage.height]);
        pdfPage.drawImage(embeddedImage, {
          x: 0, y: 0,
          width: embeddedImage.width,
          height: embeddedImage.height
        });
        addClickableWatermark(currentChunkDoc, pdfPage, currentChunkFont);
        capturedCount++;

        // 🧠 DOM PRUNING (VIRTUAL MEMORY EVICTION):
        // Wipes heavy images and canvas from past pages while fixing layout height!
        // Keeps Chromium RAM locked at ~200MB even across 1000 pages!
        await page.evaluate((idx) => {
          const el = document.getElementById(`outer_page_${idx}`);
          if (el) {
            el.style.minHeight = el.offsetHeight + 'px';
            el.innerHTML = ''; // Instantly frees GPU & RAM!
          }
          if (window.docManager && window.docManager.pages && window.docManager.pages[idx]) {
            try { window.docManager.pages[idx].unload(); } catch (e) {}
          }
        }, i);
      }

      // Save chunk
      if (pageIdx % CHUNK_SIZE === 0 || i === effectiveEnd) {
        if (currentChunkDoc.getPageCount() > 0) {
          chunkCount++;
          const chunkPath = path.join(downloadsDir, `temp_chunk_${docId}_${chunkCount}.pdf`);
          const chunkBytes = await currentChunkDoc.save();
          fs.writeFileSync(chunkPath, chunkBytes);
          tempChunks.push(chunkPath);
        }
        currentChunkDoc = null;
        if (i < effectiveEnd) {
          currentChunkDoc = await PDFDocument.create();
          currentChunkFont = await currentChunkDoc.embedFont(StandardFonts.HelveticaBold);
        }
      }
    }

    await browser.close();

    // Assemble final PDF
    if (tempChunks.length === 1) {
      fs.renameSync(tempChunks[0], rawOutputPath);
    } else {
      const finalPdf = await PDFDocument.create();
      for (const cp of tempChunks) {
        const cBytes = fs.readFileSync(cp);
        const loadedChunk = await PDFDocument.load(cBytes);
        const copied = await finalPdf.copyPages(loadedChunk, loadedChunk.getPageIndices());
        copied.forEach(p => finalPdf.addPage(p));
      }
      fs.writeFileSync(rawOutputPath, await finalPdf.save());
      for (const cp of tempChunks) {
        try { fs.unlinkSync(cp); } catch (e) {}
      }
    }

    return {
      success: true,
      pdfPath: rawOutputPath,
      title: docTitle,
      pageCount: capturedCount
    };

  } catch (err) {
    if (browser) await browser.close().catch(() => {});
    for (const cp of tempChunks) {
      try { fs.unlinkSync(cp); } catch (e) {}
    }
    throw err;
  }
}

// CLI Execution Entry Point
if (require.main === module) {
  const [,, docId, outputPath, startPage, endPage, proxyUrl] = process.argv;
  if (!docId || !outputPath) {
    console.error(JSON.stringify({ success: false, error: 'Usage: node downloader.js <docId> <outputPath> [start] [end] [proxy]' }));
    process.exit(1);
  }

  renderScribdDocument(docId, outputPath, startPage || 1, endPage || null, proxyUrl || null)
    .then(res => {
      console.log('__FINAL_RESULT__' + JSON.stringify(res));
      process.exit(0);
    })
    .catch(err => {
      console.error('__FINAL_ERROR__' + JSON.stringify({ success: false, error: err.message }));
      process.exit(1);
    });
}

module.exports = { renderScribdDocument };

