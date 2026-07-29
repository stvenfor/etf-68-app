import {z} from 'zod';

export const SectorItemSchema = z.object({
  rank: z.number(),
  code: z.string(),
  name: z.string(),
  netYi: z.number(),
});

export const FrameSchema = z.object({
  time: z.string(),
  stamp: z.string(),
  outflowTop: z.array(SectorItemSchema),
  inflowTop: z.array(SectorItemSchema),
  marketExitYi: z.number(),
});

export const SectorMetaSchema = z.object({
  code: z.string(),
  name: z.string(),
  side: z.enum(['outflow', 'inflow']),
  finalNetYi: z.number(),
});

export const FlowDataSchema = z.object({
  tradeDate: z.string(),
  dataCutoff: z.string(),
  fetchedAt: z.string(),
  timezone: z.string(),
  snapshotMode: z.string(),
  synthetic: z.boolean(),
  source: z.string(),
  sourceUrl: z.string(),
  unit: z.string(),
  classification: z.string(),
  fieldNote: z.string(),
  topN: z.number(),
  boardCount: z.number(),
  selectedCount: z.number(),
  sectors: z.array(SectorMetaSchema),
  frames: z.array(FrameSchema).min(10),
  disclaimer: z.string(),
});

export type FlowData = z.infer<typeof FlowDataSchema>;
export type FlowFrame = z.infer<typeof FrameSchema>;
export type SectorItem = z.infer<typeof SectorItemSchema>;

export const CompositionPropsSchema = z.object({
  data: FlowDataSchema,
});

export type CompositionProps = z.infer<typeof CompositionPropsSchema>;
