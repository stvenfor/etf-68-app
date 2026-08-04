import React from 'react';
import {Freeze} from 'remotion';
import type {CompositionProps} from './data/schema';
import {SectorFundFlowIntraday} from './SectorFundFlowIntraday';

/** Near-close frame so cover matches full-day rankings / hub stance. */
export const COVER_FRAME = 320;

/**
 * Cover reuses the full video look (lines, beads, hub, lists, stats).
 * Prefer `npm run cover` → `out/cover.jpg` (+ 竖/横 JPG variants).
 * This Freeze wrapper is a Studio / Still fallback.
 */
export const Cover: React.FC<CompositionProps> = (props) => {
  return (
    <Freeze frame={COVER_FRAME}>
      <SectorFundFlowIntraday {...props} />
    </Freeze>
  );
};
