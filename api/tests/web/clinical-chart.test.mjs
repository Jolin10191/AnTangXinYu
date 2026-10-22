import assert from 'node:assert/strict';
import {test} from 'node:test';
import {glucoseValue,chartLayout} from '../../src/antang_api/clinical_web/chart.mjs';
test('glucose units preserve original reading',()=>{assert.equal(glucoseValue(90),5);assert.equal(glucoseValue(180,'mg'),180)});
test('curve preserves source and measurement gaps without mutating observations',()=>{
 const records=[{time:'2026-10-20T16:00:00Z',value:140,source:'manual'},{time:'2026-10-20T00:00:00Z',value:90,source:'manual'},{time:'2026-10-20T03:00:00Z',value:110,source:'manual'},{time:'2026-10-20T05:00:00Z',value:100,source:'report'}];
 const original=structuredClone(records);
 const result=chartLayout(records,'2026-10-20T00:00:00Z','2026-10-21T00:00:00Z');
 assert.deepEqual(result.segments.map(s=>s.length),[2,1,1]);assert.deepEqual(records,original);
});
test('empty observations stay empty and invalid data cannot form a curve',()=>{
 assert.equal(chartLayout([],'2026-10-20','2026-10-21').points.length,0);
 assert.throws(()=>chartLayout([{time:'invalid',value:100}],'2026-10-20','2026-10-21'));
 assert.throws(()=>chartLayout([{time:'2026-10-20',value:NaN}],'2026-10-20','2026-10-21'));
});
