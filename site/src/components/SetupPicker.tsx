'use client';

import Link from 'next/link';
import { useState } from 'react';
import type { Lang } from '@/lib/content';
import { DownloadLink } from './Download';
import { Icon } from './Icons';

// Which package (D219), and since D228 the downloads too. The user, 2026-10-27: "decision of
// getting full, scanner or server version it is so hard to know how"; and 2026-10-28, of the
// download list below it: "since you alr has 你该下载哪个？, so you still put 下载 section is a bit
// too many. and instead I feel like you should made the section 你该下载哪个？more interesting".
// Two questions with a tap each; the answer is the setup drawn, data moving along it, and each
// package it takes as a card -- what it is for, its download, its guide, and its steps.

/** One package, as the answer shows it: its zip, its guide, and its guide's steps in a line. */
export interface Pack { kind: string; name: string; for: string; url: string; file: string; guide: string; steps: string[] }

type Computer = 'windows' | 'mac';
type Where = 'alone' | 'server';

const W = {
  zh: {
    q1: '你在什么电脑上玩？', q2: '想在手机上随时看吗？电脑关着也能看？',
    windows: 'Windows 电脑', windowsSays: 'Windows 10 / 11', mac: 'Mac', macSays: '库洛官方 Mac 客户端',
    alone: '不用，一台电脑就够', aloneSays: '扫描和页面都在这台电脑上',
    server: '要，我有 NAS 或一直开着的机器', serverSays: '电脑扫描，服务器保存、提供页面',
    pc: '这台电脑', pcSays: '扫描 + 全部页面', scanner: '玩游戏的电脑', scannerSays: '扫描，发给服务器',
    nas: '服务器（NAS）', nasSays: '保存数据、提供页面', phone: '手机', phoneSays: '随时打开',
    youNeed: (n: number) => (n > 1 ? `你要下载这 ${n} 个` : '你要下载这一个'),
    download: '下载', guide: '图文指南', stepsIn: (n: number) => `${n} 步装好`,
    go: '一步一步装', goServer: '服务器怎么装',
    unblock: 'Windows：解压前右键压缩包 → 属性 → 勾选「解除锁定」。',
    all: '所有版本和更新说明', sums: '校验文件 SHA256SUMS',
  },
  en: {
    q1: 'What do you play on?', q2: 'See it on your phone anytime, even with the PC off?',
    windows: 'A Windows PC', windowsSays: 'Windows 10 / 11', mac: 'A Mac', macSays: "Kuro's own Mac client",
    alone: 'No, one computer is enough', aloneSays: 'scanning and pages on this computer',
    server: 'Yes, I have a NAS or an always-on box', serverSays: 'the PC scans, the server keeps it and shows it',
    pc: 'This computer', pcSays: 'scans and shows every page', scanner: 'The PC with the game', scannerSays: 'scans, sends it to the server',
    nas: 'The server (NAS)', nasSays: 'keeps the data, shows the pages', phone: 'Your phone', phoneSays: 'opens it anytime',
    youNeed: (n: number) => (n > 1 ? `You need these ${n}` : 'You need this one'),
    download: 'Download', guide: 'Picture guide', stepsIn: (n: number) => `${n} steps`,
    go: 'Step by step', goServer: 'Setting up the server',
    unblock: 'Windows: before unzipping, right-click the zip → Properties → tick Unblock.',
    all: 'Every version and its notes', sums: 'Checksums, SHA256SUMS',
  },
};

const NEEDS: Record<Computer, Record<Where, string[]>> = {
  windows: { alone: ['full'], server: ['scanner', 'server'] },
  mac: { alone: ['mac-full'], server: ['mac-scanner', 'server'] },
};
const PAGE: Record<Computer, Record<Where, string>> = {
  windows: { alone: 'install', server: 'server' },
  mac: { alone: 'mac', server: 'mac' },
};

export function SetupPicker({ lang, packs, hrefs, all, sums }: {
  lang: Lang;
  packs: Record<string, Pack>;
  /** each page's address in this language: install, server, mac */
  hrefs: Record<string, string>;
  /** this version's release page, and its checksums */
  all: string; sums: string;
}) {
  const w = W[lang];
  const [computer, setComputer] = useState<Computer>('windows');
  const [where, setWhere] = useState<Where>('alone');
  const device = computer === 'mac' ? 'laptop' : 'pc';
  const needs = NEEDS[computer][where].map(kind => packs[kind]);
  const choice = <T extends string>(value: T, now: T, set: (v: T) => void, icon: string, label: string, says: string) => (
    <button type="button" className={`choice${value === now ? ' on' : ''}`} aria-pressed={value === now} onClick={() => set(value)}>
      <Icon name={value === now ? `${icon}-on` : icon} /><span className="choice-t"><b>{label}</b><small>{says}</small></span>
    </button>
  );
  const node = (icon: string, name: string, says: string, main = false) => (
    <figure className={`node${main ? ' main' : ''}`}><span className="node-ic"><Icon name={icon} /></span><b>{name}</b><small>{says}</small></figure>
  );
  return (
    <div className="picker">
      <div className="questions">
        <div className="q-row">
          <p className="q"><span className="q-n">1</span>{w.q1}</p>
          <div className="choices">
            {choice<Computer>('windows', computer, setComputer, 'pc', w.windows, w.windowsSays)}
            {choice<Computer>('mac', computer, setComputer, 'laptop', w.mac, w.macSays)}
          </div>
        </div>
        <div className="q-row">
          <p className="q"><span className="q-n">2</span>{w.q2}</p>
          <div className="choices">
            {choice<Where>('alone', where, setWhere, device, w.alone, w.aloneSays)}
            {choice<Where>('server', where, setWhere, 'nas', w.server, w.serverSays)}
          </div>
        </div>
      </div>

      <div className="answer" aria-live="polite">
        <div className={`diagram ${where}`}>
          {where === 'alone' ? node(`${device}-on`, w.pc, w.pcSays, true) : (
            <>
              {node(device, w.scanner, w.scannerSays)}
              <span className="link" aria-hidden="true"><i /><i /><i /></span>
              {node('nas-on', w.nas, w.nasSays, true)}
              <span className="link" aria-hidden="true"><i /><i /><i /></span>
              {node('phone', w.phone, w.phoneSays)}
            </>
          )}
        </div>

        <p className="need-h">{w.youNeed(needs.length)}</p>
        <ul className={`packs n${needs.length}`}>
          {needs.map(p => (
            <li key={p.kind} className="pack">
              <div className="pack-h">
                <span className="pack-ic"><Icon name={p.kind === 'server' ? 'nas' : p.kind.startsWith('mac') ? 'laptop' : 'pc'} /></span>
                <span className="pack-t"><b>{p.name}</b><code>{p.kind}</code></span>
              </div>
              <p className="pack-for">{p.for}</p>
              <ol className="pack-steps" aria-label={w.stepsIn(p.steps.length)}>
                {p.steps.map((s, i) => <li key={i}><span>{i + 1}</span>{s}</li>)}
              </ol>
              <div className="pack-a">
                <DownloadLink className="btn gold" href={p.url}>{w.download}<small>.zip</small></DownloadLink>
                <a className="pack-g" href={p.guide}><Icon name="planner" />{w.guide}</a>
              </div>
            </li>
          ))}
        </ul>

        <div className="go">
          <Link className="btn line" href={hrefs[PAGE[computer][where]]}>{w.go} ›</Link>
          {computer === 'mac' && where === 'server'
            ? <Link className="btn line" href={hrefs.server}>{w.goServer} ›</Link> : null}
        </div>
        <div className="answer-foot">
          {computer === 'windows' ? <p>{w.unblock}</p> : null}
          <p><a href={all} target="_blank" rel="noopener noreferrer">{w.all} ›</a><a href={sums} download>{w.sums}</a></p>
        </div>
      </div>
    </div>
  );
}
