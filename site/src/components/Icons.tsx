import type { ReactNode } from 'react';
import sprite from './icons.svg';
import { DownloadIcon } from './Download';

// The site's icons (D214) are the app's own family (D139, D141): drawings asked of Gemini in the
// conversation that made the app's, traced shape for shape, every line at the family's weight.
// icons.svg holds the app's symbols the site uses -- tests/test_site.py keeps them identical to
// web/src/components/pages.svg -- and the five only the site needs (pc, nas, laptop, phone,
// idwiped). One file, fetched once; each icon takes the colour of the text around it.

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';

export function Icon({ name }: { name: string }) {
  return <svg className="i" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" data-ic={name.replace(/-on$/, '')}>
    <use href={`${sprite.src}#${name}`} /></svg>;
}

/** The app's own mark (D139): an eye whose iris is the bag's grid -- the inventory, seen. */
const Logo = () => <img className="i logo" src={`${BASE}/favicon.svg`} alt="" width={24} height={24} />;

export const Icons: Record<string, ReactNode> = {
  bag: <Icon name="inventory" />,
  tiles: <Logo />,
  plan: <Icon name="planner" />,
  pixels: <Logo />,
  shield: <Icon name="privacy" />,
  idWiped: <Icon name="idwiped" />,
  home: <Icon name="nas" />,
  pc: <Icon name="pc" />,
  pcHomePhone: <Icon name="nas" />,
  mac: <Icon name="laptop" />,
  download: <DownloadIcon />,
  guide: <Icon name="planner" />,
  lock: <Icon name="privacy" />,
  steps: null,
  phone: <Icon name="phone" />,
  search: null,
};
