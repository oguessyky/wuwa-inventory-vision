'use client';

import Link from 'next/link';
import { useState } from 'react';
import type { Download, Lang } from '@/lib/content';
import { DownloadLink } from './Download';
import { Icon } from './Icons';

// Which package (D219). The user, 2026-10-27: "decision of getting full, scanner or server
// version it is so hard to know how". Two questions with a tap each -- what you play on, and
// whether a phone should see it with the PC off -- and the answer is a picture of that setup,
// the packages it takes with their downloads, and the page with its steps.

type Computer = 'windows' | 'mac';
type Home = 'alone' | 'home';

const W = {
  zh: {
    q1: '你在什么电脑上玩？', windows: 'Windows 电脑', mac: 'Mac',
    q2: '想在手机上随时看吗？电脑关着也能看？', alone: '不用，一台电脑就够', home: '要，我有 NAS 或一直开着的机器',
    pc: '这台电脑', pcSays: '扫描 + 全部页面', scanner: '玩游戏的电脑', scannerSays: '扫描，发给主机',
    nas: '主机（NAS）', nasSays: '保存数据、提供页面', phone: '手机', phoneSays: '随时打开',
    youNeed: '你要的', steps: '一步一步装', homeSteps: '主机怎么装', and: '+',
  },
  en: {
    q1: 'What do you play on?', windows: 'A Windows PC', mac: 'A Mac',
    q2: 'See it on your phone anytime, even with the PC off?', alone: 'No, one computer is enough', home: 'Yes, I have a NAS or an always-on box',
    pc: 'This computer', pcSays: 'scans and shows every page', scanner: 'The PC with the game', scannerSays: 'scans, sends it home',
    nas: 'The home (NAS)', nasSays: 'keeps the data, shows the pages', phone: 'Your phone', phoneSays: 'opens it anytime',
    youNeed: 'You need', steps: 'Step by step', homeSteps: 'Setting up the home', and: '+',
  },
};

const NEEDS: Record<Computer, Record<Home, string[]>> = {
  windows: { alone: ['full'], home: ['scanner', 'home'] },
  mac: { alone: ['mac-full'], home: ['mac-scanner', 'home'] },
};
const PAGE: Record<Computer, Record<Home, string>> = {
  windows: { alone: 'install', home: 'home' },
  mac: { alone: 'mac', home: 'mac' },
};

export function SetupPicker({ lang, zips, hrefs }: {
  lang: Lang;
  zips: Record<string, Download>;
  /** each page's address in this language: install, home, mac */
  hrefs: Record<string, string>;
}) {
  const w = W[lang];
  const [computer, setComputer] = useState<Computer>('windows');
  const [home, setHome] = useState<Home>('alone');
  const device = computer === 'mac' ? 'laptop' : 'pc';
  const needs = NEEDS[computer][home];
  const choice = <T extends string>(value: T, now: T, set: (v: T) => void, icon: string, label: string) => (
    <button type="button" className={`choice${value === now ? ' on' : ''}`} aria-pressed={value === now} onClick={() => set(value)}>
      <Icon name={value === now ? `${icon}-on` : icon} /><span>{label}</span>
    </button>
  );
  return (
    <div className="picker">
      <div className="questions">
        <div className="q-row">
          <p className="q">{w.q1}</p>
          <div className="choices">
            {choice<Computer>('windows', computer, setComputer, 'pc', w.windows)}
            {choice<Computer>('mac', computer, setComputer, 'laptop', w.mac)}
          </div>
        </div>
        <div className="q-row">
          <p className="q">{w.q2}</p>
          <div className="choices">
            {choice<Home>('alone', home, setHome, device, w.alone)}
            {choice<Home>('home', home, setHome, 'nas', w.home)}
          </div>
        </div>
      </div>

      <div className="answer" aria-live="polite">
        <div className={`diagram ${home}`}>
          {home === 'alone' ? (
            <figure className="node main"><Icon name={`${device}-on`} /><b>{w.pc}</b><small>{w.pcSays}</small></figure>
          ) : (
            <>
              <figure className="node"><Icon name={device} /><b>{w.scanner}</b><small>{w.scannerSays}</small></figure>
              <span className="link" aria-hidden="true" />
              <figure className="node main"><Icon name="nas-on" /><b>{w.nas}</b><small>{w.nasSays}</small></figure>
              <span className="link back" aria-hidden="true" />
              <figure className="node"><Icon name="phone" /><b>{w.phone}</b><small>{w.phoneSays}</small></figure>
            </>
          )}
        </div>
        <div className="need">
          <span className="need-h">{w.youNeed}</span>
          {needs.map((kind, i) => (
            <span key={kind} className="need-k">
              {i ? <i>{w.and}</i> : null}
              <DownloadLink className="btn gold" href={zips[kind].url}><code>{kind}</code></DownloadLink>
            </span>
          ))}
        </div>
        <div className="go">
          <Link className="btn line" href={hrefs[PAGE[computer][home]]}><Icon name="planner" />{w.steps} ›</Link>
          {computer === 'mac' && home === 'home'
            ? <Link className="btn line" href={hrefs.home}><Icon name="nas" />{w.homeSteps} ›</Link> : null}
        </div>
      </div>
    </div>
  );
}
