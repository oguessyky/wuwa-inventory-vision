import Link from 'next/link';
import { address, downloads, firstSteps, guideSteps, packages, version, type Lang } from '@/lib/content';
import { BASE, Frame, REPO } from './Doc';
import { Icons } from './Icons';
import { SetupPicker, type Pack } from './SetupPicker';
import { ld, NAME, SITE } from '@/lib/seo';

// The help site's landing page (D214). The user, 2026-10-27: "the help site should have a good
// landing page". What the program is for, in one look: the bag scrolled once, read off the screen,
// and what to farm next -- then which way to set it up, the pages, and why it is safe. The app's own
// colours; system fonts, so a visit asks nothing of anyone else. D289: after the hero, what it
// answers that the game does not, and each thing it does as a row with its picture at size.

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
    waysH: '你该下载哪个？', waysSub: '点两下：画出你的装法，要下载的包和装好的每一步都在下面。',
    whyH: '游戏不告诉你的，它告诉你',
    whySub: '背包几百格、几十种材料、几十位共鸣者。下面这些，以前全靠自己记、自己算。',
    why: [
      ['还缺什么？', '有多少、每位共鸣者和武器还差什么，一次扫描全部对照好，合成也算进去。'],
      ['先刷哪个？', '这轮该刷什么、商店该买什么，总览直接列出来。'],
      ['到底打多少？', '游戏不显示的伤害、治疗和护盾，每一下都算出来；离毕业差在哪，一眼就知道。'],
      ['换不换？', '换哪把武器、先换哪个声骸、整队一轮打多少，都算给你看。'],
    ],
    featH: '它替你做的事', featSub: '每一项都按你扫描到的东西来算，不用一格一格手填。',
    feats: [
      { pics: ['planner'], tag: '规划', link: 'pages', h: '从现在到目标，还差多少',
        p: '给共鸣者或武器定一个目标：等级、技能、突破。它从现在的进度算起，扣掉库存，告诉你还缺什么、还要刷几次。',
        ticks: ['合成自动算进去', '几个目标一起算，材料不会重复算', '手机上也能看'] },
      { pics: ['calc-grade'], tag: '计算', link: 'calc', h: '游戏里看不到的伤害，算给你看',
        p: '每个技能每一下打多少，暴击和期望都算出来。再和这位共鸣者自己的最好配置比：是小毕业还是大毕业，差在哪一条属性。',
        ticks: ['按扫描到的配置算，不用手填', '每条属性离毕业还差多少', '试算改过的数值会标出来，一键还原'] },
      { pics: ['calc-weapons', 'calc-echoes'], tag: '计算', link: 'calc', h: '换哪把武器？先换哪个声骸？',
        p: '同一套配置，每把武器都算一遍：五星按精1，四星和三星按精5，也能只看自己有的。每个声骸的副属性贡献多少，放在同一把尺子上比较。',
        ticks: ['四星精5 也可能胜过五星', '最弱的声骸标出来，先换它', '再来一条满值副属性，哪条最值'] },
      { pics: ['calc-team'], tag: '配队', link: 'calc', h: '整队一轮，各人占多少',
        p: '最多三位，每人按自己的配置算。延奏、固有技能、共鸣链、武器给队友的增益自动加上；排好出场顺序和技能，就能看到一轮的总伤害。',
        ticks: ['延奏的增益给下一位登场的角色', '用不到的增益可以关掉', '常用的队伍可以保存'] },
    ],
    more: '了解更多',
    stripH: '还有这些页面',
    shots: [
      ['inventory', '库存', '跨扫描合并的全部物品，数量可以直接改。'],
      ['materials', '材料', '每种养成材料对照完整配置。'],
      ['resonators', '共鸣者', '有谁、练到哪、还要什么。'],
      ['shops', '商店', '货架、限购和价格。'],
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
    waysH: 'Which one do you need?', waysSub: 'Two taps: your setup drawn, with the packages to download and every step to set them up.',
    whyH: 'What the game does not tell you, it does',
    whySub: 'Hundreds of tiles, dozens of materials, dozens of resonators. All of this used to be kept in your head, or worked out by hand.',
    why: [
      ['What is short?', 'What you own against what each resonator and weapon still needs, from one scan, synthesis counted.'],
      ['What to farm first?', 'What to farm this round and what to buy in the shops, listed on the overview.'],
      ['How hard does it hit?', 'The damage, heals and shields the game never shows, every hit; and what keeps a build from 毕业.'],
      ['Swap it or not?', 'Which weapon, which echo first, and what the whole team does in a rotation, worked out.'],
    ],
    featH: 'What it does for you', featSub: 'Each one worked out from what you scanned: nothing to type in, one tile at a time.',
    feats: [
      { pics: ['planner'], tag: 'Planner', link: 'pages', h: 'From where you are to the target',
        p: 'Give a resonator or weapon a target: level, skills, ascension. It counts from where they are, takes off what you own, and says what is short and how many runs that is.',
        ticks: ['Synthesis counted for you', 'Several targets at once, nothing counted twice', 'On your phone too'] },
      { pics: ['calc-grade'], tag: 'Calculator', link: 'calc', h: 'The damage the game does not show',
        p: 'Every hit of every skill, with crit and the expected value. Then against the same resonator at their best: 小毕业 or 大毕业, and which stat keeps them short.',
        ticks: ['On the build you scanned, nothing typed in', 'How far each stat is from 毕业', 'What you try out is marked, and goes back in one tap'] },
      { pics: ['calc-weapons', 'calc-echoes'], tag: 'Calculator', link: 'calc', h: 'Which weapon? Which echo first?',
        p: 'The same build with every weapon in turn: a 5★ at R1, a 4★ or 3★ at R5, or only the ones you own. What each echo\'s substats add, all on one scale.',
        ticks: ['A 4★ at R5 can beat a 5★', 'The weakest echo marked, to replace first', 'Which substat to roll for next'] },
      { pics: ['calc-team'], tag: 'Team', link: 'calc', h: 'A team\'s rotation, and each one\'s share',
        p: 'Up to three, each on their own build. Outros, inherent skills, chains and weapons given to the team are added for you; set the order and the skills, and see the rotation\'s damage.',
        ticks: ['An outro goes to the next one on', 'Switch off what a fight would not give', 'Keep the teams you use'] },
    ],
    more: 'Read more',
    stripH: 'And these pages',
    shots: [
      ['inventory', 'Inventory', 'Everything you own, merged across scans; fix a count in place.'],
      ['materials', 'Materials', 'Every build material against a full build.'],
      ['resonators', 'Resonators', 'Who you have, how far each is, what each needs.'],
      ['shops', 'Shops', 'Every shelf, its limits and prices.'],
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
  // shown as WebP, made while the site is built (D230); the PNG stays for the share card
  const pic = (name: string) => `${BASE}/screens/${lang === 'en' ? 'en/' : ''}${name}.webp`;
  // each package as the picker's answer shows it (D228): its zip, its guide, its guide's steps
  const zips = downloads();
  const packs: Record<string, Pack> = Object.fromEntries(packages().map(p => [p.kind, {
    kind: p.kind, name: p[lang], for: lang === 'en' ? p.for_en : p.for_zh,
    url: zips[p.kind].url, file: zips[p.kind].file, guide: `${BASE}/guides/${p.kind}.html`,
    // the setting up only: the server's guide goes on to updating, a second server, moving it --
    // and connecting a scanner, which the scanner's card has (as the server page shows it, D219)
    steps: guideSteps(p.kind, lang).filter(st => p.kind !== 'server' || st.n <= 5)
      .map(st => st.title.replace(/<[^>]+>/g, '')),
    // the pop-up after its download (D267): from the zip to the first double-click
    first: { lang, file: zips[p.kind].file, guide: `${BASE}/guides/${p.kind}.html`, steps: firstSteps(p.kind, lang) },
  }]));
  const hrefs = { install: address(lang, 'install'), server: address(lang, 'server'), mac: address(lang, 'mac') };
  const icons = [Icons.bag, Icons.tiles, Icons.plan];
  const safeIcons = [Icons.pixels, Icons.shield, Icons.idWiped, Icons.home];
  const trustIcons = [Icons.pixels, Icons.home, Icons.phone];
  const whyIcons = [Icons.bag, Icons.plan, Icons.calc, Icons.weapons];
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
              <a className="btn gold dlb" href="#setup">{Icons.download}{w.download(v)}</a>
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

        {/* what it answers that the game does not (D289) */}
        <section className="band why">
          <h2>{w.whyH}</h2>
          <p className="sub">{w.whySub}</p>
          <ul className="why-g">
            {w.why.map(([h, p], i) => (
              <li key={h}><span className="ic">{whyIcons[i]}</span><b>{h}</b><p>{p}</p></li>
            ))}
          </ul>
        </section>

        {/* each thing it does, a row of its own: the words beside a picture at size (D289) */}
        <section className="band features">
          <h2>{w.featH}</h2>
          <p className="sub">{w.featSub}</p>
          {w.feats.map((f, i) => (
            <article key={f.h} className="feat" data-flip={String(i % 2 === 1)} data-pics={f.pics.length}>
              <div className="feat-t">
                <span className="tag">{f.tag}</span>
                <h3>{f.h}</h3>
                <p>{f.p}</p>
                <ul className="ticks">{f.ticks.map(t => <li key={t}>{t}</li>)}</ul>
                <Link className="feat-go" href={address(lang, f.link)}>{w.more} ›</Link>
              </div>
              <div className="feat-v">
                {f.pics.map(name => (
                  <figure key={name} className="shot"><img src={pic(name)} alt={f.h} loading="lazy" /></figure>
                ))}
              </div>
            </article>
          ))}
          <div className="strip">
            <h3>{w.stripH}</h3>
            <div className="strip-g">
              {w.shots.map(([name, h, p]) => (
                <figure key={name}>
                  <img src={pic(name)} alt={h} loading="lazy" width={1400} height={880} />
                  <figcaption><b>{h}</b>{p}</figcaption>
                </figure>
              ))}
            </div>
            <p className="more"><Link href={address(lang, 'pages')}>{w.allPages} ›</Link></p>
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
          {/* the download list was here: an old link to #download lands on the picker (D228) */}
          <span id="download" className="anchor" aria-hidden="true" />
          <h2>{w.waysH}</h2>
          <p className="sub">{w.waysSub}</p>
          <SetupPicker lang={lang} packs={packs} hrefs={hrefs}
                       all={`${REPO}/releases/tag/v${v}`} sums={`${REPO}/releases/download/v${v}/SHA256SUMS.txt`} />
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
            <a className="btn gold dlb" href="#setup">{Icons.download}{w.download(v)}</a>
            <a className="btn line" href="#setup">{Icons.guide}{w.how}</a>
          </div>
        </section>
      </main>
    </Frame>
  );
}
