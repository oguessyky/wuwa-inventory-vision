import Link from 'next/link';
import { address, downloads, packages, version, type Lang } from '@/lib/content';
import { BASE, Frame, REPO } from './Doc';
import { Icons } from './Icons';
import { DownloadLink } from './Download';
import { SetupPicker } from './SetupPicker';
import { ld, NAME, SITE } from '@/lib/seo';

// The help site's landing page (D214). The user, 2026-10-27: "the help site should have a good
// landing page". What the program is for, in one look: the bag scrolled once, read off the screen,
// and what to farm next -- then which way to set it up, the pages, and why it is safe. The app's own
// colours; system fonts, so a visit asks nothing of anyone else.

const W = {
  zh: {
    eyebrow: '鸣潮 · 背包识别 · 免费开源',
    title: ['滚一遍背包，', '剩下的', '交给它。'],
    lede: '在游戏里把背包从头到尾滚一遍，它就从屏幕上读出每样物品和数量，再告诉你：每个共鸣者和武器还差什么、哪些材料不够、下一步该刷什么、该买什么。',
    download: (v: string) => `下载 v${v}`, how: '怎么安装',
    trust: ['只读屏幕像素', '数据留在你自己的设备上', 'Windows · Mac · 手机'],
    shot: '总览：钱包、扫描进度、经验能养成多少、这轮去买什么',
    phone: '手机上的总览',
    stepsH: '三步，就这样', stepsSub: '不用手动数，也不用一格一格输入。',
    steps: [
      ['打开背包，滚一遍', '切到游戏，每个分页慢慢滚到底。扫完按 F9（Mac 上按 Ctrl+C）。'],
      ['它读出每一格', '名称、稀有度、数量；武器还有等级、谐振和装配在谁身上。游戏自己的格数告诉它扫全了没有。'],
      ['告诉你下一步', '每种材料对照每个共鸣者和武器的完整配置，合成也算进去：还缺多少、去哪刷、商店买什么。'],
    ],
    waysH: '你该下载哪个？', waysSub: '回答两个问题，就知道要哪个包、怎么装。',
    pagesH: '每一页都在帮你算', pagesSub: '中文、拼音、首字母、英文都能搜到。每一页都适配手机。',
    shots: [
      ['inventory', '库存', '跨扫描合并的全部物品：从哪来、用在哪，数量可以直接改。'],
      ['materials', '材料', '每种养成材料对照完整配置，合成算进去，也能设自己的目标。'],
      ['resonators', '共鸣者', '有谁、练到哪、还要什么、谁拿着哪把武器。'],
      ['shops', '商店', '每个商店的货架、限购和价格；少于底数的东西会出现在总览。'],
    ],
    allPages: '看全部页面',
    safeH: '它只看屏幕', safeSub: '不读内存、不改游戏文件、不抓网络包，也不会替你操作角色。',
    safe: [
      ['只读像素', '和你自己看屏幕一样：截取游戏窗口的画面，别的什么都不碰。'],
      ['不改你的账号', '不移动角色、不战斗、不使用或出售任何东西。'],
      ['玩家 ID 先抹掉', '每张图在保存或显示之前，先把特征码抹掉。'],
      ['数据在你这里', '只在你点了按钮的时候才联网：下载图鉴、更新程序。'],
    ],
    safeMore: '安全与隐私',
    dlH: '下载', dlSub: (v: string) => `v${v}，选你要的那个包，点一下就开始下载。每个包里都有图文指南 START-HERE。`,
    dlZip: '下载', dlGuide: '指南', dlAll: '所有版本和更新说明', dlSums: '校验文件 SHA256SUMS',
    dlUnblock: 'Windows：解压前右键压缩包 → 属性 → 勾选「解除锁定」。',
    endH: '现在就开始', endSub: '需要 Windows 10/11 或装了官方 Mac 客户端的 macOS，大约 6 GB 硬盘。有 NVIDIA 显卡会快很多，但不是必需的。',
  },
  en: {
    eyebrow: 'Wuthering Waves · free · open source',
    title: ['Scroll your bag once.', 'It does ', 'the counting.'],
    lede: 'Scroll through your in-game inventory once, and it reads every item and its count off the screen. Then it tells you what each resonator and weapon still needs, which materials are short, what to farm next and what to buy.',
    download: (v: string) => `Download v${v}`, how: 'How to install',
    trust: ['Screen pixels only', 'Your data stays on your devices', 'Windows · Mac · phone'],
    shot: 'Overview: your currency, scans, what your EXP can raise, what to buy this round',
    phone: 'The overview on a phone',
    stepsH: 'Three steps, that is all', stepsSub: 'No counting by hand, no typing in one tile at a time.',
    steps: [
      ['Open the bag, scroll it', 'Switch to the game and scroll each tab to the end. Press F9 when done (Ctrl+C on a Mac).'],
      ['It reads every tile', 'Name, rarity and count; for weapons also the level, refinement and who has it equipped. The game\'s own count says when a scan is complete.'],
      ['It tells you what is next', 'Every material against every resonator\'s and weapon\'s full build, synthesis counted: what is short, where to farm it, what to buy.'],
    ],
    waysH: 'Which one do you need?', waysSub: 'Two questions, and you know which package and how to set it up.',
    pagesH: 'Every page does the sums', pagesSub: 'Find anything by English, Chinese, pinyin or initials. Every page fits a phone.',
    shots: [
      ['inventory', 'Inventory', 'Everything you own, merged across scans: where it comes from, what uses it, counts you can fix.'],
      ['materials', 'Materials', 'Every build material against a full build, synthesis counted, with targets of your own.'],
      ['resonators', 'Resonators', 'Who you have, how far each is, what each still needs, who carries which weapon.'],
      ['shops', 'Shops', 'Every shop\'s shelf, limits and prices; what drops below your base shows on the overview.'],
    ],
    allPages: 'See every page',
    safeH: 'It only looks at the screen', safeSub: 'No memory reads, no changes to game files, no packet capture, and it never plays for you.',
    safe: [
      ['Pixels only', 'Like your own eyes on the screen: it captures the game window, and touches nothing else.'],
      ['Your account untouched', 'It never moves your character, fights, uses or sells anything.'],
      ['Player ID removed first', 'Every picture has the player ID wiped before it is saved or shown.'],
      ['Your data stays with you', 'It goes online only when you press the button: the catalogue, an update.'],
    ],
    safeMore: 'Safety and privacy',
    dlH: 'Download', dlSub: (v: string) => `v${v}. Pick your package; a click starts the download. Each one carries its picture guide, START-HERE.`,
    dlZip: 'Download', dlGuide: 'Guide', dlAll: 'Every version and its notes', dlSums: 'Checksums, SHA256SUMS',
    dlUnblock: 'Windows: before unzipping, right-click the zip → Properties → tick Unblock.',
    endH: 'Start now', endSub: 'Windows 10/11, or macOS with Kuro\'s own Mac client, and about 6 GB of disk. An NVIDIA graphics card makes it much faster, but it is not needed.',
  },
};

/** A drawn bag: rows of tiles, some with a rarity bar, and the gold line of a scan going over. */
function Bag() {
  const tiles = Array.from({ length: 24 }, (_, i) => i);
  const rarity = ['#e8c95a', '#b07cf0', '#5aa0f0', '#5fd08f', ''];
  return (
    <div className="bag" aria-hidden="true">
      {tiles.map(i => <i key={i} style={{ ['--r' as string]: rarity[(i * 7 + 3) % 5] || 'transparent', ['--d' as string]: `${(i % 6) * 60 + Math.floor(i / 6) * 220}ms` }} />)}
      <b className="scanline" />
    </div>
  );
}


/** What the site is about, as structured data (D222): the program -- free, for Windows and macOS,
 * its version, where to get it -- and the site itself, in both languages. */
function about(lang: Lang, v: string) {
  const home = `${SITE}${address(lang, 'index')}`;
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'SoftwareApplication',
        name: NAME[lang],
        alternateName: lang === 'en' ? NAME.zh : NAME.en,
        description: W[lang].lede,
        url: home,
        applicationCategory: 'UtilitiesApplication',
        applicationSubCategory: 'Game companion',
        operatingSystem: 'Windows 10, Windows 11, macOS',
        softwareVersion: v,
        downloadUrl: `${REPO}/releases/latest`,
        screenshot: `${SITE}/screens/${lang === 'en' ? 'en/' : ''}dashboard.png`,
        license: 'https://www.apache.org/licenses/LICENSE-2.0',
        isAccessibleForFree: true,
        offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
        inLanguage: ['zh-CN', 'en'],
      },
      { '@type': 'WebSite', name: NAME[lang], url: home, inLanguage: lang === 'en' ? 'en' : 'zh-CN' },
    ],
  };
}

export function Landing({ lang }: { lang: Lang }) {
  const w = W[lang];
  const v = version();
  const pic = (name: string) => `${BASE}/screens/${lang === 'en' ? 'en/' : ''}${name}.png`;
  const guide = (kind: string) => (kind.startsWith('mac-')
    ? { href: `${lang === 'en' ? '/en' : ''}/guides/${kind}/`, inside: true }
    : { href: `${BASE}/guides/${kind}.html`, inside: false });
  const hrefs = { install: address(lang, 'install'), home: address(lang, 'home'), mac: address(lang, 'mac') };
  const zips = downloads();
  const icons = [Icons.bag, Icons.tiles, Icons.plan];
  const safeIcons = [Icons.pixels, Icons.shield, Icons.idWiped, Icons.home];
  const trustIcons = [Icons.pixels, Icons.home, Icons.phone];
  return (
    <Frame lang={lang}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld(about(lang, v)) }} />
      <main className="landing">
        <section className="hero">
          <div className="hero-t">
            <p className="eyebrow">{w.eyebrow}</p>
            <h1>{w.title[0]}<br />{w.title[1]}<em>{w.title[2]}</em></h1>
            <p className="lede">{w.lede}</p>
            <div className="ctas">
              <a className="btn gold dlb" href="#download">{Icons.download}{w.download(v)}</a>
              <a className="btn line" href="#setup">{Icons.guide}{w.how}</a>
            </div>
            <ul className="trust">{w.trust.map((t, i) => <li key={t}>{trustIcons[i]}{t}</li>)}</ul>
          </div>
          <div className="hero-v">
            <Bag />
            <figure className="desk">
              <div className="chrome" aria-hidden="true"><i /><i /><i /><span>127.0.0.1:4000</span></div>
              <img src={pic('dashboard')} alt={w.shot} width={1400} height={880} />
              <b className="sweep" aria-hidden="true" />
            </figure>
            <figure className="phone"><img src={pic('phone')} alt={w.phone} /></figure>
          </div>
        </section>

        <section className="band steps">
          <h2>{w.stepsH}</h2>
          <p className="sub">{w.stepsSub}</p>
          <ol>
            {w.steps.map(([h, p], i) => (
              <li key={h}><span className="n">{i + 1}</span><span className="ic">{icons[i]}</span><h3>{h}</h3><p>{p}</p></li>
            ))}
          </ol>
        </section>

        <section className="band ways" id="setup">
          <h2>{w.waysH}</h2>
          <p className="sub">{w.waysSub}</p>
          <SetupPicker lang={lang} zips={zips} hrefs={hrefs} />
        </section>

        <section className="band dl" id="download">
          <h2>{w.dlH}</h2>
          <p className="sub">{w.dlSub(v)}</p>
          <ul className="zips">
            {packages().map(p => {
              const z = zips[p.kind];
              const g = guide(p.kind);
              return (
                <li key={p.kind}>
                  <span className="ic">{p.kind.startsWith('mac') ? Icons.mac : p.kind === 'home' ? Icons.home : Icons.pc}</span>
                  <div className="z-t"><b>{p[lang]}</b><code>{p.kind}</code><p>{lang === 'en' ? p.for_en : p.for_zh}</p></div>
                  <div className="z-a">
                    {g.inside ? <Link className="z-g" href={g.href}>{Icons.guide}{w.dlGuide}</Link> : <a className="z-g" href={g.href}>{Icons.guide}{w.dlGuide}</a>}
                    <DownloadLink className="btn gold z-d" href={z.url}>{w.dlZip}<small>.zip</small></DownloadLink>
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="z-more">{w.dlUnblock}</p>
          <p className="z-more">
            <a href={`${REPO}/releases/tag/v${v}`} target="_blank" rel="noopener noreferrer">{w.dlAll} ›</a>
            <a href={`${REPO}/releases/download/v${v}/SHA256SUMS.txt`} download>{w.dlSums}</a>
          </p>
        </section>

        <section className="band shots">
          <h2>{w.pagesH}</h2>
          <p className="sub with-ic">{Icons.search}{w.pagesSub}</p>
          <div className="grid">
            {w.shots.map(([name, h, p]) => (
              <figure key={name}>
                <img src={pic(name)} alt={h} loading="lazy" width={1400} height={880} />
                <figcaption><b>{h}</b>{p}</figcaption>
              </figure>
            ))}
          </div>
          <p className="more"><Link href={address(lang, 'pages')}>{w.allPages} ›</Link></p>
        </section>

        <section className="band safe">
          <div className="safe-h">
            <h2>{w.safeH}</h2>
            <p className="sub">{w.safeSub}</p>
            <Link className="btn line" href={address(lang, 'safety')}>{Icons.lock}{w.safeMore}</Link>
          </div>
          <ul>
            {w.safe.map(([h, p], i) => <li key={h}><span className="ic">{safeIcons[i]}</span><b>{h}</b><p>{p}</p></li>)}
          </ul>
        </section>

        <section className="band end">
          <h2>{w.endH}</h2>
          <p className="sub">{w.endSub}</p>
          <div className="ctas">
            <a className="btn gold dlb" href="#download">{Icons.download}{w.download(v)}</a>
            <a className="btn line" href="#setup">{Icons.guide}{w.how}</a>
          </div>
        </section>
      </main>
    </Frame>
  );
}
