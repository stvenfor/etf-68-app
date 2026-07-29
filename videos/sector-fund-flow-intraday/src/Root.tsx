import React from 'react';
import {Composition} from 'remotion';
import {SectorFundFlowIntraday} from './SectorFundFlowIntraday';
import {CompositionPropsSchema, type CompositionProps} from './data/schema';
import raw from './data/sector-fund-flow-2026-07-28.json';

const defaultProps: CompositionProps = {
  data: CompositionPropsSchema.shape.data.parse(raw),
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
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
