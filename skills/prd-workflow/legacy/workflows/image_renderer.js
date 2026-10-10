/**
 * 图片渲染服务 v2.0（主备自动切换版）
 *
 * 统一的图片渲染模块，支持：
 * - Mermaid → PNG：三级瀑布（主方案 mermaid-skill：A mmdc 本地 → B Kroki API；备方案 mermaid-flow：C mermaid_render.py 独立进程）
 * - HTML → PNG（使用 htmlPrototype 截图）
 * - 批量渲染
 * - 缓存管理
 *
 * v2.0 容错机制：
 * - 主方案连续失败达阈值 → 熔断（COOLDOWN_MS 内直接走备方案，不再重复等超时）
 * - 冷却期满 → 半开探测：下一次调用先试主方案，成功即切回，失败则继续熔断
 * - 全链路 JSONL 日志（channel / duration / error），输出目录 logs/render-fallback.jsonl
 * - 对上层完全透明：renderMermaid() 签名与返回结构不变，降级信息只进 result.fallback 附加字段与日志
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const os = require('os');

// ===== 容错配置（可被 options.failover 覆盖）=====
const FAILOVER_DEFAULTS = {
  FAILURE_THRESHOLD: 2,     // 主方案连续失败达此值触发熔断
  COOLDOWN_MS: 10 * 60 * 1000, // 熔断冷却时长（10 分钟）
  TIMEOUT_MS: 30000,        // 单通道超时
  KROKI_TIMEOUT_MS: 30000,  // Kroki API 超时
  KROKI_URL: 'https://kroki.io/mermaid/png'
};

class ImageRenderer {
  constructor(options = {}) {
    this.version = '2.0';
    this.outputDir = options.outputDir || './output/images';
    this.cacheDir = options.cacheDir || './output/.cache';
    this.verbose = options.verbose !== false;

    // 主备切换配置
    this.failover = { ...FAILOVER_DEFAULTS, ...(options.failover || {}) };
    this.fallbackLogPath = options.fallbackLogPath || path.join(this.cacheDir, '..', 'logs', 'render-fallback.jsonl');

    // 熔断器状态
    this.primaryFailures = 0;        // 主方案连续失败计数
    this.circuitOpenUntil = 0;       // 熔断截止时间戳（0 = 关闭）
    this.lastError = null;           // 最近一次主方案失败原因

    // 默认渲染配置
    this.config = {
      mermaid: {
        width: 1600,
        height: 1200,
        backgroundColor: 'white',
        theme: 'default'
      },
      html: {
        width: 1440,
        height: 900,
        format: 'png'
      }
    };

    // 初始化 Puppeteer 配置（使用系统 Chrome）
    this.puppeteerConfigPath = this.initPuppeteerConfig();
  }

  /**
   * 初始化 Puppeteer 配置文件（使用系统 Chrome）
   */
  initPuppeteerConfig() {
    const configDir = this.cacheDir;
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }

    const configPath = path.join(configDir, 'puppeteer-config.json');

    // 检测系统 Chrome 路径
    const chromePaths = this.getChromePaths();
    const chromePath = chromePaths.find(p => fs.existsSync(p));

    const config = {
      executablePath: chromePath || undefined,
      headless: true
    };

    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');

    if (this.verbose && chromePath) {
      console.log(`   🌐 使用系统 Chrome: ${chromePath}`);
    }

    return configPath;
  }

  /**
   * 获取可能的 Chrome 路径
   */
  getChromePaths() {
    const platform = os.platform();
    const homeDir = os.homedir();

    const paths = [];

    // Puppeteer 缓存目录中的 chrome-headless-shell（优先：与 GUI Chrome 完全隔离，避免 ConnectionClosed）
    const puppeteerCachePaths = [
      path.join(homeDir, '.cache', 'puppeteer', 'chrome-headless-shell'),
      path.join(homeDir, 'Library', 'Caches', 'puppeteer', 'chrome-headless-shell')
    ];

    for (const cachePath of puppeteerCachePaths) {
      if (fs.existsSync(cachePath)) {
        // 查找最新的版本目录
        const versions = fs.readdirSync(cachePath).filter(v =>
          v.startsWith('mac-') || v.startsWith('linux-') || v.startsWith('win-')
        );
        for (const version of versions) {
          const shellPath = path.join(cachePath, version, 'chrome-headless-shell');
          if (fs.existsSync(shellPath)) {
            paths.push(shellPath);
          }
          // 版本目录下可能还有一层 arch 目录（如 chrome-headless-shell-mac-arm64/chrome-headless-shell）
          try {
            const archDirs = fs.readdirSync(path.join(cachePath, version), { withFileTypes: true })
              .filter(d => d.isDirectory()).map(d => d.name);
            for (const arch of archDirs) {
              const nested = path.join(cachePath, version, arch, 'chrome-headless-shell');
              if (fs.existsSync(nested)) paths.push(nested);
              // macOS .app 格式
              const appPath = path.join(cachePath, version, arch, 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');
              if (fs.existsSync(appPath)) paths.push(appPath);
            }
          } catch { /* ignore */ }
          // macOS .app 格式（直接在版本目录下）
          const appPath = path.join(cachePath, version, 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');
          if (fs.existsSync(appPath)) {
            paths.push(appPath);
          }
        }
      }
    }

    // 系统 Chrome
    if (platform === 'darwin') {
      paths.push(
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
      );
    } else if (platform === 'win32') {
      paths.push(
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
      );
    } else {
      paths.push(
        '/usr/bin/google-chrome',
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium'
      );
    }

    return paths;
  }

  /**
   * 渲染 Mermaid 代码为 PNG（v2.0 主备自动切换）
   *
   * 瀑布顺序：
   *   主方案 mermaid-skill = [A: mmdc 本地, B: Kroki API]（熔断时整体跳过）
   *   备方案 mermaid-flow  = [C: mermaid_render.py 独立进程]
   *
   * 对上层透明：签名与返回结构与 v1.0 完全一致；
   * 降级信息仅出现在附加字段 result.fallback 与 JSONL 日志中。
   *
   * @param {string} mermaidCode - Mermaid 代码
   * @param {string} outputPath - 输出路径（不含扩展名）
   * @param {Object} options - 渲染选项
   * @returns {Object} - { success, path, error, fallback? }
   */
  renderMermaid(mermaidCode, outputPath, options = {}) {
    const config = { ...this.config.mermaid, ...options };
    const pngPath = outputPath.endsWith('.png') ? outputPath : `${outputPath}.png`;
    const startedAt = Date.now();
    const attempts = [];   // 每通道尝试记录

    const tryChannel = (channel, fn) => {
      const t0 = Date.now();
      try {
        const r = fn();
        attempts.push({ channel, ok: true, durationMs: Date.now() - t0 });
        return r;
      } catch (err) {
        attempts.push({
          channel, ok: false, durationMs: Date.now() - t0,
          error: String(err.message || err).slice(0, 500)
        });
        if (this.verbose) {
          console.warn(`   ⚠️  [${channel}] 失败：${String(err.message || err).slice(0, 160)}`);
        }
        return null;
      }
    };

    // ---- 判定主方案是否可用（熔断器：closed / open / half-open）----
    const now = Date.now();
    const circuitOpen = now < this.circuitOpenUntil;
    const halfOpen = this.circuitOpenUntil > 0 && now >= this.circuitOpenUntil;

    // ---- 主方案：通道 A（mmdc 本地）→ 通道 B（Kroki API）----
    let primaryResult = null;
    if (!circuitOpen) {
      // 通道 A：mmdc 本地渲染（mermaid-skill Option 1）
      primaryResult = tryChannel('A:mmdc-local', () => {
        if (!this.checkMmdc()) throw new Error('mermaid-cli (mmdc) 未安装');
        return this._renderViaMmdc(mermaidCode, pngPath, config);
      });

      // 通道 B：Kroki API（mermaid-skill Option 2，无需本地依赖）
      if (!primaryResult) {
        primaryResult = tryChannel('B:kroki-api', () => {
          return this._renderViaKroki(mermaidCode, pngPath, config);
        });
      }
    }

    if (primaryResult) {
      // 主方案成功：重置熔断器（half-open 探测通过 → 切回主方案）
      if (halfOpen || this.primaryFailures > 0) {
        this.logFallback({
          event: 'primary-recovered', halfOpen,
          attempts, totalMs: Date.now() - startedAt
        });
      }
      this.primaryFailures = 0;
      this.circuitOpenUntil = 0;
      return { success: true, path: pngPath };
    }

    // 主方案整体失败（或熔断中）→ 计数并开闸
    const failReason = attempts.length
      ? attempts[attempts.length - 1].error || 'unknown'
      : `circuit-open until ${new Date(this.circuitOpenUntil).toISOString()} (last: ${this.lastError || 'n/a'})`;
    if (!circuitOpen) {
      this.primaryFailures += 1;
      this.lastError = failReason;
      if (this.primaryFailures >= this.failover.FAILURE_THRESHOLD) {
        this.circuitOpenUntil = Date.now() + this.failover.COOLDOWN_MS;
        this.logFallback({
          event: 'circuit-opened', failures: this.primaryFailures,
          cooldownMs: this.failover.COOLDOWN_MS, reason: failReason, attempts
        });
      }
    }

    // ---- 备方案：通道 C（mermaid-flow mermaid_render.py 独立进程）----
    const backupResult = tryChannel('C:mermaid-flow', () => {
      return this._renderViaMermaidFlow(mermaidCode, pngPath, config);
    });

    if (backupResult) {
      this.logFallback({
        event: 'fallback-used', circuitOpen, reason: failReason,
        attempts, totalMs: Date.now() - startedAt
      });
      return { success: true, path: pngPath, fallback: { used: true, channel: 'C:mermaid-flow', reason: failReason } };
    }

    // ---- 全部失败 ----
    this.logFallback({
      event: 'all-channels-failed', circuitOpen, reason: failReason,
      attempts, totalMs: Date.now() - startedAt
    });
    return {
      success: false,
      error: `主备方案均失败。主方案最后错误：${failReason}；备方案最后错误：${attempts.length ? attempts[attempts.length - 1].error : 'n/a'}`
    };
  }

  /**
   * 通道 A：mmdc 本地渲染（mermaid-skill Option 1）
   * 抛错代表失败；返回 pngPath 代表成功
   */
  _renderViaMmdc(mermaidCode, pngPath, config) {
    const tempMmd = this.getTempPath('mermaid', '.mmd');
    fs.writeFileSync(tempMmd, mermaidCode, 'utf8');
    try {
      const cmd = `mmdc -i "${tempMmd}" -o "${pngPath}" ` +
        `-w ${config.width} -H ${config.height} ` +
        `-b "${config.backgroundColor}" -t ${config.theme} ` +
        `-p "${this.puppeteerConfigPath}"`;
      execSync(cmd, { stdio: 'pipe', timeout: this.failover.TIMEOUT_MS });
    } finally {
      this.cleanupTemp(tempMmd);
    }
    if (!fs.existsSync(pngPath) || fs.statSync(pngPath).size <= 100) {
      throw new Error('mmdc 输出文件无效（不存在或 ≤100B）');
    }
    return pngPath;
  }

  /**
   * 通道 B：Kroki API 渲染（mermaid-skill Option 2，零本地依赖）
   * 成功返回 pngPath；HTTP 非 200 或网络异常抛错
   */
  _renderViaKroki(mermaidCode, pngPath, config) {
    const tempMmd = this.getTempPath('mermaid', '.mmd');
    fs.writeFileSync(tempMmd, mermaidCode, 'utf8');
    const tmpPng = pngPath + '.kroki.tmp';
    try {
      const cmd = `curl -sS --fail -X POST -H "Content-Type: text/plain" ` +
        `--data-binary @"${tempMmd}" "${this.failover.KROKI_URL}" -o "${tmpPng}" ` +
        `--max-time ${Math.ceil(this.failover.KROKI_TIMEOUT_MS / 1000)}`;
      execSync(cmd, { stdio: 'pipe', timeout: this.failover.KROKI_TIMEOUT_MS });
      if (!fs.existsSync(tmpPng) || fs.statSync(tmpPng).size <= 100) {
        throw new Error('Kroki 返回内容无效（≤100B）');
      }
      fs.renameSync(tmpPng, pngPath);
      return pngPath;
    } catch (err) {
      // Kroki 对非法语法返回 400；把上游 body 提示带出来便于排查
      let detail = '';
      try {
        if (fs.existsSync(tmpPng)) detail = fs.readFileSync(tmpPng, 'utf8').slice(0, 200);
      } catch { /* ignore */ }
      throw new Error(`Kroki API 失败：${err.message}${detail ? `；响应：${detail}` : ''}`);
    } finally {
      this.cleanupTemp(tempMmd);
      this.cleanupTemp(tmpPng);
    }
  }

  /**
   * 通道 C：备方案 mermaid-flow（scripts/mermaid_render.py 独立进程）
   * 独立进程隔离：自带 Chrome 检测与 PUPPETEER_EXECUTABLE_PATH 环境注入，
   * 主进程的 puppeteer-config 损坏不影响此通道。
   */
  _renderViaMermaidFlow(mermaidCode, pngPath, config) {
    const scriptPath = path.join(__dirname, '..', 'skills', 'mermaid-flow', 'scripts', 'mermaid_render.py');
    if (!fs.existsSync(scriptPath)) {
      throw new Error(`备方案脚本不存在：${scriptPath}`);
    }
    const tempMmd = this.getTempPath('mermaid', '.mmd');
    fs.writeFileSync(tempMmd, mermaidCode, 'utf8');
    try {
      // 环境注入：沿用 mermaid-flow 的 Chrome 检测结果
      const env = { ...process.env };
      if (!env.PUPPETEER_EXECUTABLE_PATH) {
        const chrome = this.getChromePaths().find(p => fs.existsSync(p));
        if (chrome) env.PUPPETEER_EXECUTABLE_PATH = chrome;
      }
      const pyBin = env.MERMAID_FLOW_PYTHON || 'python3';
      const cmd = `"${pyBin}" "${scriptPath}" -i "${tempMmd}" -o "${pngPath}" -w ${config.width} -b ${config.backgroundColor}`;
      execSync(cmd, { stdio: 'pipe', timeout: this.failover.TIMEOUT_MS, env });
      if (!fs.existsSync(pngPath) || fs.statSync(pngPath).size <= 100) {
        throw new Error('mermaid_render.py 输出文件无效（不存在或 ≤100B）');
      }
      return pngPath;
    } finally {
      this.cleanupTemp(tempMmd);
    }
  }

  /**
   * 主备切换 JSONL 日志（append-only，便于排查）
   */
  logFallback(entry) {
    try {
      const logDir = path.dirname(this.fallbackLogPath);
      if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
      const line = JSON.stringify({
        ts: new Date().toISOString(),
        renderer: 'image_renderer@2.0',
        ...entry
      }) + '\n';
      fs.appendFileSync(this.fallbackLogPath, line, 'utf8');
    } catch {
      // 日志失败不影响主流程
    }
  }

  /**
   * 批量渲染 Mermaid 图表
   *
   * @param {Array} diagrams - [{ name, code }] 数组
   * @param {string} outputDir - 输出目录
   * @returns {Array} - 渲染结果数组
   */
  renderMermaidBatch(diagrams, outputDir) {
    const results = [];

    for (const diagram of diagrams) {
      const outputPath = path.join(outputDir, `${diagram.name}.png`);
      const result = this.renderMermaid(diagram.code, outputPath);
      results.push({
        name: diagram.name,
        ...result
      });
    }

    return results;
  }

  /**
   * 从 PRD Markdown 提取并渲染所有 Mermaid 图表
   *
   * @param {string} markdown - PRD Markdown 内容
   * @param {string} outputDir - 输出目录
   * @returns {Object} - { diagrams: [], images: [] }
   */
  renderPRDDiagrams(markdown, outputDir) {
    // 提取所有 Mermaid 代码块
    const mermaidBlocks = this.extractMermaidBlocks(markdown);

    if (mermaidBlocks.length === 0) {
      if (this.verbose) {
        console.log('   ℹ️  未找到 Mermaid 图表');
      }
      return { diagrams: [], images: [] };
    }

    // ⭐ 确保 outputDir 存在
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
      if (this.verbose) {
        console.log(`   ✅ 创建图片目录：${outputDir}`);
      }
    }

    if (this.verbose) {
      console.log(`   📊 发现 ${mermaidBlocks.length} 个 Mermaid 图表`);
    }

    // 渲染每个图表
    const images = [];
    for (let i = 0; i < mermaidBlocks.length; i++) {
      const block = mermaidBlocks[i];
      const name = block.title || `diagram_${i + 1}`;
      const outputPath = path.join(outputDir, `${name}.png`);

      const result = this.renderMermaid(block.code, outputPath);
      if (result.success) {
        images.push({
          name,
          path: result.path,
          title: block.title,
          section: block.section
        });
      }
    }

    return { diagrams: mermaidBlocks, images };
  }

  /**
   * 从 Markdown 提取 Mermaid 代码块
   *
   * @param {string} markdown - Markdown 内容
   * @returns {Array} - [{ code, title, section }]
   */
  extractMermaidBlocks(markdown) {
    const blocks = [];
    const lines = markdown.split('\n');

    let currentSection = '';
    let inMermaid = false;
    let mermaidCode = '';
    let mermaidTitle = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // 检测章节标题
      if (line.match(/^##+ /)) {
        currentSection = line.replace(/^##+ /, '').trim();
      }

      // 检测 Mermaid 开始
      if (line.trim() === '```mermaid') {
        inMermaid = true;
        mermaidCode = '';
        // 从前面的标题获取图表名称
        if (i > 0 && lines[i - 1].match(/^###+ /)) {
          mermaidTitle = lines[i - 1].replace(/^###+ /, '').trim();
        } else {
          mermaidTitle = `diagram_${blocks.length + 1}`;
        }
        continue;
      }

      // 检测 Mermaid 结束
      if (inMermaid && line.trim() === '```') {
        inMermaid = false;
        if (mermaidCode.trim()) {
          blocks.push({
            code: mermaidCode.trim(),
            title: this.sanitizeFilename(mermaidTitle),
            section: currentSection
          });
        }
        continue;
      }

      // 收集 Mermaid 代码
      if (inMermaid) {
        mermaidCode += line + '\n';
      }
    }

    return blocks;
  }

  /**
   * 检查 mmdc 是否可用
   */
  checkMmdc() {
    try {
      execSync('mmdc --version', { stdio: 'pipe' });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * 获取临时文件路径
   */
  getTempPath(prefix, ext) {
    const tempDir = this.cacheDir;
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }
    return path.join(tempDir, `${prefix}_${Date.now()}${ext}`);
  }

  /**
   * 清理临时文件
   */
  cleanupTemp(tempPath) {
    try {
      if (fs.existsSync(tempPath)) {
        fs.unlinkSync(tempPath);
      }
    } catch {
      // 忽略清理错误
    }
  }

  /**
   * 清理文件名（移除特殊字符）
   */
  sanitizeFilename(name) {
    return name
      .replace(/[^\w\u4e00-\u9fa5]/g, '_')  // 保留中文、字母、数字、下划线
      .replace(/_+/g, '_')                   // 合并连续下划线
      .replace(/^_|_$/, '')                  // 移除首尾下划线
      .toLowerCase()
      .slice(0, 50);                         // 限制长度
  }

  /**
   * 生成图片映射文件（用于 Word 导出）
   *
   * @param {Array} images - 图片数组
   * @param {string} outputPath - 输出路径
   */
  generateImageMap(images, outputPath) {
    const imageMap = {
      version: '1.0',
      generated: new Date().toISOString(),
      images: images.map(img => ({
        name: img.name,
        file: img.path,
        caption: img.title || img.name,
        section: img.section || ''
      }))
    };

    fs.writeFileSync(outputPath, JSON.stringify(imageMap, null, 2), 'utf8');
    if (this.verbose) {
      console.log(`   ✅ 图片映射已保存：${outputPath}`);
    }

    return imageMap;
  }

  /**
   * 替换 Markdown 中的 Mermaid 代码块为图片引用
   *
   * @param {string} markdown - Markdown 内容
   * @param {Array} images - 图片数组 [{ name, path, title }]
   * @returns {string} - 替换后的 Markdown
   */
  replaceMermaidWithImages(markdown, images) {
    let result = markdown;
    const blocks = this.extractMermaidBlocks(markdown);

    for (let i = 0; i < blocks.length; i++) {
      const block = blocks[i];
      const image = images.find(img => img.name === block.title || img.name === `diagram_${i + 1}`);

      if (image) {
        // 构建图片引用
        const imageRef = `\n![${image.title || block.title}](${image.path})\n`;

        // 替换 Mermaid 代码块
        const mermaidBlock = '```mermaid\n' + block.code + '\n```';
        result = result.replace(mermaidBlock, imageRef);
      }
    }

    return result;
  }
}

module.exports = { ImageRenderer };