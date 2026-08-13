import React from 'react';
import {Composition, Still} from 'remotion';
import {Cover} from './Cover';
import {SectorFundFlowIntraday} from './SectorFundFlowIntraday';
import {CompositionPropsSchema, type CompositionProps} from './data/schema';
import raw from './data/sector-fund-flow-2026-08-13.json';

const defaultProps: CompositionProps = {
  data: CompositionPropsSchema.shape.data.parse(raw),
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Still
        id="SectorFundFlowCover"
        component={Cover}
        width={1080}
        height={1920}
        schema={CompositionPropsSchema}
        defaultProps={defaultProps}
      />
      {/* Douyin Feed 竖封面 3:4 — must match poster design, not a video freeze crop */}
      <Still
        id="SectorFundFlowCoverPortrait"
        component={Cover}
        width={1080}
        height={1440}
        schema={CompositionPropsSchema}
        defaultProps={defaultProps}
      />
      <Composition
        id="SectorFundFlowIntraday"
        component={SectorFundFlowIntraday}
        durationInFrames={390}
        fps={30}
        width={1080}
        height={1920}
        schema={CompositionPropsSchema}
        defaultProps={defaultProps}
      />
    </>
  );
};
